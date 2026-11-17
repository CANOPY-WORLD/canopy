"""Resumable 1 m SCALED inference; exact SouthKen tile/halo and 4³ reduction.
Each model step is decoded independently. No temporal or spatial interpolation.
"""
import argparse, hashlib, json, os, sys, time, shutil, zipfile
from pathlib import Path
import numpy as np

def write(p,v):
 p=Path(p);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(v,indent=2));t.replace(p)
def sha(p):
 with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def reduce4(a, maximum=False):
 z,y,x=a.shape[-3:];b=a.reshape(*a.shape[:-3],z//4,4,y//4,4,x//4,4)
 return b.max(axis=(-1,-3,-5)) if maximum else b.mean(axis=(-1,-3,-5))
def decode_coarse(latent,enc,k,solid):
 import torch
 import torch.nn.functional as F
 # Identical decode inputs, padding, cropping, and scaling to scaled_latent.decode_domain.
 tile=k.DEC_TILE_OUT//k.SCALE;expected=k.SCALE*(tile+2*k.DEC_HALO_LAT);trim=(expected-k.DEC_TILE_OUT)//2
 lp=F.pad(latent*10,(k.DEC_HALO_LAT,)*4+(0,0),mode='reflect')
 out=np.empty((3,*solid.shape),np.float32)
 with torch.inference_mode():
  for i in range(latent.shape[-2]//tile):
   for j in range(latent.shape[-1]//tile):
    sub=lp[:,:,:,i*tile:i*tile+tile+2*k.DEC_HALO_LAT,j*tile:j*tile+tile+2*k.DEC_HALO_LAT].to(k.device)
    dec=enc.decode(sub)
    fine=dec[0,:,:,trim:expected-trim,trim:expected-trim].float().cpu().numpy()*3.
    coarse=reduce4(fine).astype(np.float32);coarse[0]*=-1
    size=k.DEC_TILE_OUT//4;out[:,:,i*size:(i+1)*size,j*size:(j+1)*size]=coarse
    del sub,dec,fine,coarse
 out[:,solid]=0
 if not np.isfinite(out).all():raise ValueError('Nonfinite decoded vector')
 return out

def main():
 invocation_started=time.time()
 ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--pilot-only',action='store_true');ap.add_argument('--stop-after',type=int,default=100);a=ap.parse_args();c=json.load(open(a.config));out=Path(c['output']);out.mkdir(parents=True,exist_ok=True)
 sys.path[:0]=[c['scaled_repository'],str(Path(__file__).resolve().parents[2])]
 import torch
 from urban_flow.physics.wind import scaled_latent as k
 k.SCALED_REPO=Path(c['scaled_repository']);assert (k.TILE_PHYS,k.HALO_PHYS,k.TILE_LAT,k.HALO_LAT,k.DEC_TILE_OUT,k.DEC_HALO_LAT)==(256,8,256,4,256,4)
 source=Path(c['geometry']);gm=json.load(open(source.parent/'metadata.json'));assert list(gm.get('source_region_origin_xyz_m',gm.get('origin_xyz_m')))==c['origin_enu_m'];assert gm.get('spacing_xyz_m',[gm.get('cell_m')]*3)==[1,1,1];sourcehash=sha(source);identity={'geometry_sha256':sourcehash,'origin_enu_m':c['origin_enu_m'],'shape_zyx':c['shape_zyx'],'forced_ground_index':0,'runner_sha256':sha(__file__),'kernel_sha256':sha(k.__file__)}
 if (out/'identity.json').exists():assert json.load(open(out/'identity.json'))==identity
 else:write(out/'identity.json',identity)
 with zipfile.ZipFile(out/'source_snapshot.zip','w',zipfile.ZIP_DEFLATED) as archive:
  for f in (k.SCALED_REPO/'scaled').rglob('*.py'):archive.write(f,'scaled/'+str(f.relative_to(k.SCALED_REPO/'scaled')))
  archive.write(k.SCALED_REPO/'LICENSE','SCALED-LICENSE');archive.write(__file__,'scaled_scene028.py');archive.write(k.__file__,'scaled_latent.py');archive.write(a.config,'config.json')
 weights={}
 for name in ['compression.pth','inference.pth']:
  src=k.SCALED_REPO/'weight'/name;weights[name]=sha(src)
  if not (out/name).exists():shutil.copy2(src,out/name)
 write(out/'weights.json',weights)
 fine=np.load(source).astype(bool);assert list(fine.shape)==c['shape_zyx'];fine[0]=True
 coarse=reduce4(fine,True);np.save(out/'solid_coarse.npy',coarse)
 indices=c['sample_coarse_indices'];np.save(out/'sample_invalid.npy',coarse[indices].astype('u1'));write(out/'sample_heights.json',[(i+.5)*4 for i in indices]);write(out/'sample_times_s.json',[i*25 for i in range(1,101)]);write(out/'sample_model_steps.json',list(range(1,101)));write(out/'config.json',c)
 torch.manual_seed(c['seed']);torch.set_num_threads(4);torch.cuda.reset_peak_memory_stats();start=time.time();enc,net=k.load_models();timings=json.load(open(out/'timing.json')) if (out/'timing.json').exists() else []
 checkpoint=out/'checkpoint.pt'
 if checkpoint.exists():
  cp=torch.load(checkpoint,weights_only=True);latent=cp['latent'];done=cp['step'];geo=torch.load(out/'geometry_latent.pt',weights_only=True)
 elif (out/'initial_latent.pt').exists():
  latent=torch.load(out/'initial_latent.pt',weights_only=True);geo=torch.load(out/'geometry_latent.pt',weights_only=True);done=0
 else:
  t=time.time();l0,lbg=k.encode_domain(fine,enc);latent,geo=l0/10,lbg/10;del l0,lbg;torch.save(latent,out/'initial_latent.pt');torch.save(geo,out/'geometry_latent.pt');done=0;timings.append({'phase':'encode','seconds':time.time()-t});write(out/'timing.json',timings)
 del fine
 (out/'frames').mkdir(exist_ok=True)
 samplepath=out/'velocity_samples.npy';samples=np.lib.format.open_memmap(samplepath,mode='r+' if samplepath.exists() else 'w+',dtype='float32',shape=(100,3,len(indices),*coarse.shape[1:]))
 for step in range(done+1,101):
  t=time.time();latent=k.latent_step(latent,geo,net);assert torch.isfinite(latent).all();t1=time.time();uvw=decode_coarse(latent,enc,k,coarse);t2=time.time()
  frame=out/'frames'/f'velocity_{step:03d}.npy';tmp=frame.with_suffix('.tmp')
  with tmp.open('wb') as f:np.save(f,uvw)
  tmp.replace(frame);samples[step-1]=uvw[:,indices];samples.flush()
  cp={'step':step,'latent':latent};torch.save(cp,out/'checkpoint.tmp');(out/'checkpoint.tmp').replace(checkpoint)
  row={'step':step,'latent_seconds':t1-t,'decode_seconds':t2-t1,'seconds':time.time()-t,'peak_gpu_gib':torch.cuda.max_memory_allocated()/1024**3,'elapsed_invocation_including_geometry_weights_encode_s':time.time()-invocation_started,'frame_sha256':sha(frame),'finite':True,'solid_zero':bool((uvw[:,coarse]==0).all())};timings.append(row);write(out/'timing.json',timings);write(out/'progress.json',{'completed_steps':step,'required_steps':100,'last_frame':str(frame),'seconds_this_invocation':time.time()-start});print(json.dumps(row),flush=True)
  if a.pilot_only or (step>=a.stop_after and step<100):write(out/'pilot.json',row);return
 metadata={'complete':True,'solver':'SCALED 1m inference, exact SouthKen 4³ mean reduction','cell_m':4,'shape_zyx':list(coarse.shape),'origin_enu_m':c['origin_enu_m'],'sample_model_steps':list(range(1,101)),'sample_heights_m':[(i+.5)*4 for i in indices],'time_semantics':'25 interpreted seconds/modelstep; not calibrated physical time','geometry_sha256':sourcehash,'ground_semantics':'Fine index0 at0.5m solid; conservative4³ occupancy blocks output0–4m; first usable output band4–8m center6m.','limitations':c['limitations'],'peak_gpu_gib':torch.cuda.max_memory_allocated()/1024**3};write(out/'metadata.json',metadata)
if __name__=='__main__':main()
