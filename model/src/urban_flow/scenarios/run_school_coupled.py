"""Run and retain exploratory outdoor/room/exposure school comparisons."""
import argparse,json,shutil,time
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from common.storage import Storage
from common.export import write,digest
from common.provenance import snapshot_sources
from common.contract import validate
from common.runs import promote
from .school_coupled import CASES,COMPONENTS,outdoor,indoor,exposure

def integrate_after(times,values,start):
    if start>=times[-1]:return np.zeros(values.shape[1])
    start=max(float(times[0]),start);keep=times>start;t=np.r_[start,times[keep]];v=np.vstack([[np.interp(start,times,values[:,j])for j in range(values.shape[1])],values[keep]])
    return np.sum((v[:-1]+v[1:])*.5*np.diff(t)[:,None],axis=0)

def run(config_path,school):
    cfg=json.loads(Path(config_path).read_text());storage=Storage.load();source=storage.run('tower_hamlets',cfg['source_runs'][school]);validate(source/'manifest.json');original=json.loads((source/'summary.json').read_text());oldmanifest=json.loads((source/'manifest.json').read_text())
    interiors=storage.run('tower_hamlets',cfg['interior_run']);layout=next(s for s in json.loads((interiors/'rooms.json').read_text())['schools']if s['school_id']==school)
    out=storage.scratch('tower_hamlets','school_coupled',cfg['run_prefix']+'_'+school);out.mkdir(parents=True,exist_ok=False);(out/'data').mkdir();(out/'provenance').mkdir()
    for name in ['site.json','frozen_wind_enu.npy','config.json']:shutil.copy2(source/'provenance'/name,out/'provenance'/name)
    write(out/'provenance/new_config.json',cfg);write(out/'provenance/interior_layout.json',layout);shutil.copy2(source/'manifest.json',out/'provenance/parent_manifest.json')
    mask=np.load(source/'data/invalid.npy').astype(bool);np.save(out/'data/invalid.npy',mask.astype('u1'));uv=np.load(source/'provenance/frozen_wind_enu.npy')
    support_files={'rolling':'source_baseline_rolling.npy','near':'source_baseline_idling.npy','peripheral':'source_peripheral_dropoff_idling.npy'};supports={}
    for key,file in support_files.items():shutil.copy2(source/'provenance'/file,out/'provenance'/file);supports[key]=np.load(out/'provenance'/file)
    bounds=original['bounds_enu_m'];origin=np.asarray(bounds[:2]);dx=cfg['cell_m'];rid=cfg['boundary_receptors'][school];receptor=original['receptors'][rid]
    if not receptor['cases']['baseline']['valid']:raise ValueError('Requested indoor boundary proxy is not outdoor air')
    point=receptor['definition']['enu_m'];ix,iy=np.floor((np.asarray(point)-origin)/dx).astype(int)
    if mask[iy,ix]:raise ValueError('Indoor boundary lies in mask')
    route=original['source_mapping']['plan']['pedestrian_route']['enu_xy'];layers=[];results={};start=time.monotonic()
    times=np.linspace(0,cfg['duration_s'],cfg['output_frames'])
    for wind in cfg['wind_variants']:
        results[wind['id']]={};baseline=None
        for case in CASES:
            key=wind['id']+'_'+case
            print(f'{school} {key}: starting',flush=True)
            _,components,diag=outdoor(uv*wind['speed_scale'],mask,supports,cfg,case,lambda k,n,steps:print(f'{school} {key}: {k+1}/{n} frames, {steps} internal steps',flush=True))
            total=components.sum(axis=0);np.save(out/f'data/{key}.npy',total)
            if case=='baseline':baseline=total.copy()
            metrics={'internal_steps':diag['internal_steps'],'outdoor_dt_limit_s':diag['dt_limit_s'],'mass_balance_error_au':diag['max_mass_balance_error_au'],'emitted_au':diag['emitted_au'],'outdoor_mean_au':total[:,~mask].mean(axis=1,dtype=np.float64).tolist(),'boundary_au':total[:,iy,ix].astype(float).tolist(),'boundary_components_au':{c:components[j,:,iy,ix].astype(float).tolist()for j,c in enumerate(COMPONENTS)},'max_au':float(total.max()),'difference_abs_max':float(np.abs(total-baseline).max()),'rooms':{},'exposure':{}}
            for suffix,array in [('',total),*[(f'_{c}',components[j])for j,c in enumerate(COMPONENTS)]]:
                name=key+suffix;np.save(out/f'data/{name}.npy',array)
                layers.append({'id':name,'kind':'scalar_field','format':'npy','asset':f'data/{name}.npy','sampling':'linear','field':{'name':name,'unit':'a.u.'},'encoding':{'coordinate_frame':'ENU','dtype':'<f4','shape':list(array.shape),'axes':'TYX','origin_m':[*origin.tolist(),2.],'spacing_m':[dx,dx],'sample_location':'cell_center','byte_order':'little','compression':'none','mask_asset':'data/invalid.npy','mask_dtype':'|u1','mask_semantics':'invalid_nonzero'},'display':{'widget':'scalar_field','capabilities':['pick','legend','opacity']}})
            for p in cfg['exposure_profiles']:
                metrics['exposure'][p['id']]=exposure(total,times,route,point,origin,dx,mask,p['start_s'],p['speed_m_s'],p['wait_s'])
            for vent in cfg['ventilation_variants']:
                values,check=indoor(times,total[:,iy,ix],layout['rooms'],vent)
                rm={'concentration_au':values.tolist(),'integral_au_s':integrate_after(times,values,0).tolist(),'child_post_handover_au_s':integrate_after(times,values,metrics['exposure']['child']['end_s']+60).tolist(),'child_indoor_start_s':metrics['exposure']['child']['end_s']+60,'excluded_handover_seconds':60,'diagnostics':check}
                metrics['rooms'][vent['id']]=rm;name=key+'_'+vent['id']+'_rooms'
                write(out/f'data/{name}.json',{'labels':[r['id']for r in layout['rooms']],'values':rm['concentration_au']})
                layers.append({'id':name,'kind':'time_series','format':'json','asset':f'data/{name}.json','sampling':'linear','field':{'name':'hypothetical_room_concentration','unit':'a.u.'},'display':{'widget':'time_series','capabilities':['pick']}})
            write(out/f'provenance/{key}_diagnostics.json',diag);results[wind['id']][case]=metrics
            write(out/'progress.json',{'school':school,'completed':list(results[wind['id']]),'wind':wind['id'],'runtime_s':time.monotonic()-start})
    summary={'school_id':school,'name':original['name'],'run_id':out.name,'bounds_enu_m':bounds,'cell_m':dx,'times_s':times.tolist(),'duration_s':cfg['duration_s'],'config':cfg,'boundary_proxy':{'id':rid,'requested_enu_m':point,'cell_center_enu_m':(origin+(np.array([ix,iy])+.5)*dx).tolist(),'certainty':receptor['definition']['certainty']},'layout':layout,'source_plan':original['source_mapping']['plan'],'results':results,'limitations':cfg['limitations'],'runtime_s':time.monotonic()-start,'method_reference':'https://www.nist.gov/publications/contam-user-guide-and-program-documentation-version-34','method_note':'Independent prescribed-flow room mass-balance model; not CONTAM, no pressure solve or inferred ACH.'}
    write(out/'summary.json',summary)
    return finalize(config_path,school)

def finalize(config_path,school):
    cfg=json.loads(Path(config_path).read_text());storage=Storage.load();out=storage.scratch('tower_hamlets','school_coupled',cfg['run_prefix']+'_'+school)
    summary=json.loads((out/'summary.json').read_text());source=storage.run('tower_hamlets',cfg['source_runs'][school]);interiors=storage.run('tower_hamlets',cfg['interior_run']);oldmanifest=json.loads((source/'manifest.json').read_text());layers=[]
    for p in sorted((out/'data').glob('*.npy')):
        if p.name=='invalid.npy':continue
        a=np.load(p,mmap_mode='r')
        layers.append({'id':p.stem,'kind':'scalar_field','format':'npy','asset':f'data/{p.name}','sampling':'linear','field':{'name':p.stem,'unit':'a.u.'},'encoding':{'coordinate_frame':'ENU','dtype':'<f4','shape':list(a.shape),'axes':'TYX','origin_m':[*summary['bounds_enu_m'][:2],2.],'spacing_m':[cfg['cell_m']]*2,'sample_location':'cell_center','byte_order':'little','compression':'none','mask_asset':'data/invalid.npy','mask_dtype':'|u1','mask_semantics':'invalid_nonzero'},'display':{'widget':'scalar_field','capabilities':['pick','legend','opacity']}})
    for p in sorted((out/'data').glob('*_rooms.json')):
        layers.append({'id':p.stem,'kind':'time_series','format':'json','asset':f'data/{p.name}','sampling':'linear','field':{'name':'hypothetical_room_concentration','unit':'a.u.'},'display':{'widget':'time_series','capabilities':['pick']}})
    snapshot=out/'source_snapshot.tar.gz'
    if not snapshot.exists():revision=snapshot_sources(storage.root,snapshot)
    else:
        import subprocess
        revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    shutil.copy2(__file__,out/'provenance/finalize_source.py')
    artifacts=[{'id':'source_snapshot'if p.name=='source_snapshot.tar.gz'else p.relative_to(out).as_posix(),'asset':p.relative_to(out).as_posix(),'sha256':digest(p),'media_type':'application/octet-stream'}for p in sorted(out.rglob('*'))if p.is_file()and not p.is_relative_to(out/'data')and p.name!='manifest.json']
    manifest={'schema_version':'1.1.0','scene_id':'tower_hamlets','simulation':'school_coupled','run_id':out.name,'status':'complete','created_at':datetime.now(timezone.utc).isoformat(),'spatial':oldmanifest['spatial'],'time':{'unit':'s','samples':summary['times_s']},'provenance':{'code_revision':revision,'dirty':True,'parameters':{'config':cfg,'limitations':cfg['limitations']},'inputs':[{'id':'parent_run','sha256':digest(source/'manifest.json')},{'id':'interior_layout','sha256':digest(interiors/'rooms.json')},{'id':'config','sha256':digest(config_path)}]},'layers':layers,'artifacts':artifacts}
    write(out/'manifest.json',manifest);validate(out/'manifest.json');retained=promote(storage,out);print('RETAINED',retained,flush=True);return retained
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--school',choices=['olsj','mulberry'],required=True);ap.add_argument('--finalize',action='store_true');a=ap.parse_args();(finalize if a.finalize else run)(a.config,a.school)
