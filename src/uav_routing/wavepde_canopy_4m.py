"""CANOPY adapter for the original WavePDE PyTorch solver; no graph-search routes.
Uses native solve + characteristic trace APIs, retaining raw arrival fields/status.
"""
import argparse,hashlib,json,math,time,sys,zipfile,subprocess
from pathlib import Path
from dataclasses import replace,asdict
import numpy as np
import torch
from scipy.ndimage import map_coordinates
from wavepde.torch_backend.config import WaveConfig
from wavepde.torch_backend.solver import build_static_fields,solve,waveform_samples
from wavepde.torch_backend.tracing import trace_paths
from wavepde.torch_backend.robust_tracing import trace_paths_robust
from wavepde.torch_backend.geometry import segment_free

def dump(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def flow_at(volume,p,ground):
 xy=(p[:,:2]+4096)/2-.5
 g=map_coordinates(ground,[xy[:,1],xy[:,0]],order=1,mode='nearest')
 coords=[(p[:,2]-g+2)/8-.5,(p[:,1]+4098)/8-.5,(p[:,0]+4098)/8-.5]
 return np.stack([map_coordinates(volume[k],coords,order=1,mode='nearest') for k in range(3)],axis=1)
def times_for(p,volume,ground,cfg):
 d=np.diff(p,axis=0);length=np.linalg.norm(d,axis=1);e=d/length[:,None];q=flow_at(volume,(p[:-1]+p[1:])*.5,ground);q[:,2]+=(cfg.cz_up-cfg.cz_down)/2
 inv=1/np.square([cfg.c0,cfg.c0,(cfg.cz_up+cfg.cz_down)/2]);aa=np.sum(e*e*inv,axis=1);bb=np.sum(e*q*inv,axis=1);cc=np.sum(q*q*inv,axis=1)-1
 disc=bb*bb-aa*cc
 if np.any(disc<=0):raise ValueError('Infeasible wind along segment')
 speed=(bb+np.sqrt(disc))/aa
 if np.any(speed<=0):raise ValueError('Nonpositive speed along segment')
 return np.r_[0,np.cumsum(length/speed)]
def audit(p,ground,top):
 samples=[]
 for a,b in zip(p[:-1],p[1:]):
  count=max(1,math.ceil(float(np.linalg.norm(b-a))/.5));samples.append(a+(b-a)*np.arange(count)[:,None]/count)
 dense=np.concatenate(samples+[p[-1:]]);idx=np.floor((dense[:,:2]+4096)/2).astype(int);x,y=idx[:,0],idx[:,1];inside=(idx>=0).all(1)&(idx<4096).all(1)
 if not inside.all():return {'passed':False,'reason':'outside domain'}
 g=ground[y,x];obstacle=top[y,x];agl=dense[:,2]-g;hits=(obstacle>g+.5)&(dense[:,2]<obstacle+3-1e-4)
 return {'passed':bool(not hits.any() and agl.min()>=-.02 and agl.max()<=25),'samples':len(dense),'max_agl_m':float(agl.max()),'min_agl_m':float(agl.min()),'obstacle_violations':int(hits.sum()),'sampling_m':.5,'collision_model':'2 m terrain/building/tree columns, with conservative 4x4x4 m planning voxels padded 4 m horizontally and 3 m vertically'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--wind',required=True);ap.add_argument('--pairs',required=True);ap.add_argument('--output',required=True);ap.add_argument('--sources',nargs='*');ap.add_argument('--steps',type=int,default=2800);ap.add_argument('--grid',type=int,default=256);ap.add_argument('--robust',action='store_true');ap.add_argument('--waveform',default='gaussian_short');args=ap.parse_args()
 torch.set_num_threads(4);torch.set_grad_enabled(False)
 root=Path(args.input);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
 a=np.load(root/'planner_inputs.npz');ground=a['ground'];top=a['top'];roof=a['blocked_top'];gmin=a['gmin'];stations=json.loads((root/'stations.json').read_text());byid={s['id']:s for s in stations};volume=np.load(args.wind,mmap_mode='r')
 old=json.loads(Path(args.pairs).read_text());pairs=[(r['from'],r['to']) for r in old['routes']];sources=list(dict.fromkeys(x for x,y in pairs))
 if args.sources:sources=args.sources
 cfg=WaveConfig(c0=15,cz_up=6,cz_down=4,dt=.1,n_steps=args.steps,pulse_t0_steps=120,pulse_tau_steps=16,source_sigma_cells=1.0,sponge_layers=4,min_peak_amp=1e-8,reg_low_factor=1)
 h=(4.,4.,4.);N=args.grid;NZ=32;oz=-8.
 solverroot=Path('/data/yl222/WavePde-UAV-Path-Model')
 identity={'solver':'wavepde.torch_backend.solver.solve + wavepde.torch_backend.tracing.trace_paths','robust':args.robust,'ceiling_agl_m':25,'planning_ceiling_agl_m':23,'wave':asdict(cfg),'spacing_m':h,'grid_policy':'per-source 4 m crop; width rounded to 128 cells with 68 m endpoint margins','grid_z':NZ,'waveform':args.waveform,'wind':{'source':args.wind,'sha256':sha(args.wind),'frame':'ENU','frozen_time_s':7500,'terrain_adapter':'Original flat-geometry wind sampled at local AGL; not recomputed on restored terrain'},'solver_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=solverroot,text=True).strip(),'solver_files':{str(p.relative_to(solverroot)):sha(p) for p in (solverroot/'src/wavepde/torch_backend').glob('*.py')},'runner_sha256':sha(__file__),'input_sha256':sha(root/'planner_inputs.npz'),'versions':{'torch':torch.__version__,'numpy':np.__version__},'trace_options':{'smoothing_m':8,'step_m':2,'terminal_m':24,'max_steps':4000,'extension':'local','boundary_projection':True,'max_step_halvings':2,'integrator':'euler'}}
 dump(out/'identity.json',identity)
 with zipfile.ZipFile(out/'source_snapshot.zip','w',zipfile.ZIP_DEFLATED) as archive:
  archive.write(__file__,'wavepde_canopy_demo.py')
  for p in (solverroot/'src/wavepde').rglob('*.py'):archive.write(p,str(p.relative_to(solverroot)))
 results=[];started=time.monotonic()
 for source in sources:
  checkpoint=out/(source+'.json')
  if checkpoint.exists():results+=json.loads(checkpoint.read_text())['routes'];continue
  destinations=[b for a,b in pairs if a==source]
  points=np.array([byid[v]['position_enu_m'] for v in [source]+destinations]);gates=points.copy();gates[:,2]+=12
  N=int(math.ceil((np.ptp(points[:,:2],axis=0).max()+136)/4/128)*128)
  centre=(points[:,:2].min(0)+points[:,:2].max(0))/2
  x0=int(np.clip(round((centre[0]+4096)/4-N/2),0,2048-N));y0=int(np.clip(round((centre[1]+4096)/4-N/2),0,2048-N));origin=np.array([-4096+x0*4,-4096+y0*4,oz]);local=gates-origin
  if np.any(local[:,:2]<64) or np.any(local[:,:2]>(N*4-64)):raise ValueError(f'{source}: crop too small for endpoints and padding')
  zlo=oz+np.arange(NZ)*4;zhi=zlo+4
  occupied=(zlo[None,None,:]<roof[y0:y0+N,x0:x0+N,None]+3)|(zhi[None,None,:]>gmin[y0:y0+N,x0:x0+N,None]+23)
  mask=torch.as_tensor(np.ascontiguousarray(occupied.transpose(1,0,2)),device='cuda')
  fields=build_static_fields(mask,h,cfg=cfg,device='cuda')
  xx,yy,zz=np.meshgrid(origin[0]+(np.arange(N)+.5)*4,origin[1]+(np.arange(N)+.5)*4,oz+(np.arange(NZ)+.5)*4,indexing='ij');coords=np.stack([xx.ravel(),yy.ravel(),zz.ravel()],axis=1)
  wind=flow_at(volume,coords,ground).T.reshape(3,N,N,NZ)
  drift=torch.as_tensor(np.ascontiguousarray(wind),device='cuda');bias=(cfg.cz_up-cfg.cz_down)/2
  fields=replace(fields,u=drift[0]*fields.free,v=drift[1]*fields.free,w=drift[2]*fields.free+bias)
  q=drift.clone();q[2]+=bias
  begin=time.monotonic();print(json.dumps({'source':source,'phase':'solve','queries':destinations,'grid':list(mask.shape)}),flush=True)
  wave=waveform_samples(args.waveform,cfg.dt,cfg.n_steps,device='cuda')
  arrival=solve(fields,local[0]/np.array(h)-.5,cfg,waveform=wave,execution='cuda_graph');torch.cuda.synchronize();solve_s=time.monotonic()-begin
  raw=arrival.cpu().numpy();np.savez_compressed(out/(source+'-arrival.npz'),arrival=raw,origin_enu_m=origin,spacing_m=h,mask=occupied.transpose(1,0,2))
  print(json.dumps({'source':source,'phase':'trace','solve_s':round(solve_s,2),'finite_free_fraction':float(np.isfinite(raw)[~occupied.transpose(1,0,2)].mean())}),flush=True)
  fn=trace_paths_robust if args.robust else trace_paths
  trace=fn(arrival,local[0],local[1:],mask,h,speeds=(15.,15.,5.),drift=(0.,0.,1.),drift_field=q,execution='cuda_graph',**identity['trace_options'])
  torch.cuda.synchronize();records=[]
  for k,dest in enumerate(destinations):
   path=trace.path(k);name=source+'-'+dest;status=trace.status_names()[k]
   closed=bool(segment_free(mask,path[:-1],path[1:],h,max_length=24).all()) if len(path)>1 else False
   p=path.cpu().numpy()+origin
   if trace.success[k]:p=np.vstack([points[0],p,points[k+1]])
   # Keep every failed partial; it is never exported as a flight.
   np.save(out/(name+'-path.npy'),p)
   check=audit(p,ground,top) if len(p)>1 else {'passed':False,'reason':'empty partial'}
   endpoint=bool(np.allclose(p[0],points[0],atol=.001) and np.allclose(p[-1],points[k+1],atol=.001))
   success=bool(trace.success[k] and closed and check['passed'] and endpoint)
   r={'id':name,'from':source,'to':dest,'status':status,'success':success,'closed_voxel_clear':closed,'endpoints':endpoint,'raw_pde_arrival_s':float(trace.arrivals[k]) if torch.isfinite(trace.arrivals[k]) else None,'audit':check,'projected_steps':int(trace.projected_steps[k]),'step_halvings':int(trace.step_halvings[k]),'path_file':name+'-path.npy'}
   if hasattr(trace,'raw_status'):r.update(raw_status=int(trace.raw_status[k]),visible_completion=bool(trace.visible_completions[k]),recovery_count=int(trace.recovery_counts[k]))
   if success:
    times=times_for(p,volume,ground,cfg);r.update(points_enu_m=p.round(4).tolist(),times_s=times.round(5).tolist(),wind_enu_mps=flow_at(volume,p,ground).round(4).tolist(),duration_s=float(times[-1]),distance_m=float(np.linalg.norm(np.diff(p,axis=0),axis=1).sum()))
   records.append(r)
  dump(checkpoint,{'source':source,'solve_s':solve_s,'total_s':time.monotonic()-begin,'origin_enu_m':origin.tolist(),'routes':records})
  results+=records;dump(out/'progress.json',{'completed_sources':len({r['from'] for r in results}),'sources':len(sources),'routes':len(results),'passed':sum(r['success'] for r in results),'elapsed_s':time.monotonic()-started})
  print(json.dumps({'source':source,'phase':'done','routes':[{k:r[k] for k in ['id','status','success']} for r in records],'total_s':round(time.monotonic()-begin,2)}),flush=True)
  del arrival,fields,drift,q,mask,trace;torch.cuda.empty_cache()
 dump(out/'summary.json',{'complete':True,'stations':stations,'routes':results,'successes':sum(r['success'] for r in results),'total':len(results),'wall_s':time.monotonic()-started,'identity':identity})
if __name__=='__main__':main()
