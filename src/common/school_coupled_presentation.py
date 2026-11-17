"""Export retained coupled school runs into the existing shared school viewer."""
import argparse,json,copy,shutil
from pathlib import Path
import numpy as np
from PIL import Image
from common.storage import Storage
from common.export import write,digest
from common.contract import validate
from common.school_presentation import LABELS

def export(config_path,template_path,out):
    cfg=json.loads(Path(config_path).read_text());template=json.loads(Path(template_path).read_text());out=Path(out);out.mkdir(parents=True,exist_ok=False);storage=Storage.load();catalog={'version':2,'schools':[],'limitations':cfg['limitations']};checks=[]
    for sid in cfg['schools']:
        root=storage.run('tower_hamlets',cfg['run_prefix']+'_'+sid);validate(root/'manifest.json');s=json.loads((root/'summary.json').read_text());school=copy.deepcopy(next(v for v in template['schools']if v['id']==sid));invalid=np.load(root/'data/invalid.npy').astype(bool);folder=out/sid;folder.mkdir();Image.fromarray((invalid*255).astype('u1')).save(folder/'invalid.png');times=np.asarray(s['times_s']);scale=1e-5
        maximum=max(v['max_au']for w in s['results'].values()for v in w.values());hi=float(np.log10(1+maximum/scale));difference=max(v['difference_abs_max']for w in s['results'].values()for v in w.values());allcases={};encoding_checks=[]
        for wind in cfg['wind_variants']:
            wid=wind['id'];allcases[wid]=[]
            for case,m in s['results'][wid].items():
                a=np.load(root/f'data/{wid}_{case}.npy',mmap_mode='r');dest=folder/wid/case;dest.mkdir(parents=True);frames=[];worst=0.
                for k,frame in enumerate(a):
                    q=np.clip(np.round(np.log10(1+frame/scale)/hi*255),0,255).astype('u1');p=dest/f'{k:03d}.png';Image.fromarray(q).save(p,optimize=True);decoded=scale*np.expm1(q.astype(float)/255*hi*np.log(10));worst=max(worst,float(np.abs(decoded-frame).max()));frames.append(p.relative_to(out).as_posix())
                boundary=np.asarray(m['boundary_au']);integral=float(np.sum((boundary[:-1]+boundary[1:])*.5*np.diff(times)));trips=cfg['vehicle_trips']*(cfg['reduced_trip_fraction']if case=='reduced_car_trips'else 1);idle=cfg['reduced_idle_seconds_per_trip']if case=='reduced_idling'else cfg['idle_seconds_per_trip']
                assumption=f'{trips:g} modeled arrivals during minutes 10–30; {idle:g} s idle per trip and {cfg["rolling_seconds_per_trip"]:g} s total movement. One-hour incremental tracer.'
                if case=='peripheral_dropoff':assumption+=' Only the idling source is relocated; road movement is unchanged.'
                allcases[wid].append({'id':case,'title':LABELS[case],'assumption':assumption,'frames':frames,'metrics':{'campus_mean':m['outdoor_mean_au'],'gate_mean':m['boundary_au'],'gate_exposure':integral,'route_exposure':m['exposure']['carer']['exposure_au_s'],'emitted_au':sum(m['emitted_au'].values())}})
                encoding_checks.append({'wind':wid,'case':case,'frames':len(frames),'max_display_error_au':worst,'scientific_sha256':digest(root/f'data/{wid}_{case}.npy')})
        roommax=max(float(np.max(r['concentration_au']))for w in s['results'].values()for c in w.values()for r in c['rooms'].values())
        school.update(run_id=s['run_id'],times_s=s['times_s'],cases=allcases['reference'],invalid_mask=f'{sid}/invalid.png',encoding={'transform':'log1p','scale':scale,'range':[0,hi]},display_max=maximum,difference_max=difference,metric_duration_s=cfg['duration_s'],limitations=s['limitations'],primary_receptor_id=s['boundary_proxy']['id'],primary_receptor_label='Outdoor boundary / wait proxy')
        school['coupled']={'wind_variants':cfg['wind_variants'],'ventilation_variants':cfg['ventilation_variants'],'all_cases':allcases,'results':s['results'],'room_ids':[r['id']for r in s['layout']['rooms']],'room_labels':[r['label']for r in s['layout']['rooms']],'room_display_max':roommax,'boundary_proxy':s['boundary_proxy'],'method_note':s['method_note'],'wind_note':'Same recorded flow pattern; speed sensitivity only, not newly inferred wind directions.'}
        if school.get('pickup_plan'):
            for point in school['pickup_plan']['points']:
                if point['role']=='waiting':point['position_enu_m']=s['boundary_proxy']['requested_enu_m'];point['label']='Modeled wait · candidate';point['certainty']=s['boundary_proxy']['certainty']
            school['pickup_plan']['indoor_note']='Prescribed-flow room tracer on an imagined layout; arbitrary units and assumed ventilation, not a measured indoor prediction.'
            school['pickup_plan']['emission_note']='Tailpipe and non-exhaust proxy components are transported separately with assumed strengths; no brake/tyre/dust calibration.'
        school['geometry_note']='Exterior and room layout remain estimated. Outdoor transport uses the original 4 m solid mask; conceptual rooms use assumed volumes and air exchange.'
        catalog['schools'].append(school);checks.append({'school':sid,'manifest_sha256':digest(root/'manifest.json'),'encoding':encoding_checks})
    write(out/'template.json',template);write(out/'index.json',catalog);write(out/'provenance.json',{'config_sha256':digest(config_path),'template_sha256':digest(template_path),'schools':checks,'display_images_only':True});return out
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--template',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(export(a.config,a.template,a.output))
