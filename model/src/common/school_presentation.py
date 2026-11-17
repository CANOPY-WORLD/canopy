"""Export recorded school scenarios for the shared city viewer, without rerunning solvers."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
from common.storage import Storage
from common.contract import validate
from common.export import write,digest

LABELS={'baseline':'Baseline school traffic','reduced_idling':'Shorter idling','reduced_car_trips':'Fewer car trips','peripheral_dropoff':'Peripheral drop-off'}

def export(storage,config_path,out):
    cfg=json.loads(Path(config_path).read_text());out=Path(out);out.mkdir(parents=True,exist_ok=False)
    catalog={'version':1,'schools':[],'limitations':['Synthetic school-traffic tracer with arbitrary source units; not a calibrated pollutant forecast, inhaled dose or health benefit estimate.','Four independent transport simulations use the same frozen final wind029 field. School-run traffic and driver behaviour have not been measured.','An 800 m local domain has zero tracer inflow, zero initial background and no outside sources. This is incremental hypothetical school traffic only.','No school or council partnership is implied.']};evidence=[]
    for selected in cfg['schools']:
        root=storage.run('tower_hamlets',selected['run_id']);validate(root/'manifest.json');summary=json.loads((root/'summary.json').read_text());site=json.loads((root/'provenance/site.json').read_text());sid=summary['school_id'];folder=out/sid;folder.mkdir()
        data={key:np.load(root/'data'/f'{key}.npy',mmap_mode='r') for key in summary['cases']};invalid=np.load(root/'data/invalid.npy').astype(bool);times=np.asarray(summary['times_s']);n,ny,nx=next(iter(data.values())).shape
        assert all(a.shape==(len(times),ny,nx) and np.isfinite(a).all() and (a>=0).all() for a in data.values())
        Image.fromarray((invalid*255).astype('u1')).save(folder/'invalid.png')
        scale=1e-5;maximum=max(float(a.max()) for a in data.values());hi=float(np.log10(1+maximum/scale));checks={};cases=[]
        valid_receptors=[key for key,r in summary['receptors'].items() if r['cases']['baseline']['valid']]
        receptor='school_frontage' if 'school_frontage' in valid_receptors else ('candidate_gate' if 'candidate_gate' in valid_receptors else valid_receptors[0] if valid_receptors else None)
        label={'school_frontage':'Candidate frontage','candidate_gate':'Candidate gate','campus_boundary':'Candidate boundary','candidate_access':'Candidate access'}.get(receptor,'Candidate outdoor receptor')
        ass=summary['assumptions'];trips=ass['vehicle_trips'];idle=ass['idle_seconds_per_trip'];short=ass['reduced_idle_seconds_per_trip'];fraction=ass['reduced_trip_fraction']
        assumptions={'baseline':f'Assumed {trips} vehicle trips over 10 min; {idle:g} s idling and {ass["rolling_seconds_per_trip"]:g} s movement per trip.', 'reduced_idling':f'Same {trips} assumed trips; shorten idling from {idle:g} to {short:g} s per trip.', 'reduced_car_trips':f'Assume {trips*fraction:g} rather than {trips} car trips; remaining trips keep {idle:g} s idling.', 'peripheral_dropoff':'Relocate the idling source to a candidate outer-road point. Total emissions and approach movement remain unchanged; this is not a traffic rerouting simulation.'}
        for key,a in data.items():
            (folder/key).mkdir();frames=[];worst=0.
            for k,frame in enumerate(a):
                q=np.clip(np.round(np.log10(1+frame/scale)/hi*255),0,255).astype('u1');p=folder/key/f'{k:03d}.png';Image.fromarray(q).save(p,optimize=True);pixels=np.asarray(Image.open(p));assert np.array_equal(q,pixels)
                decoded=scale*np.expm1(pixels.astype('f8')/255*hi*np.log(10));assert not np.any(decoded[frame==0]);worst=max(worst,float(np.max(np.abs(decoded-frame))));frames.append(p.relative_to(out).as_posix())
            concentration=summary['receptors'][receptor]['cases'][key]['concentration_au'] if receptor else [None]*n
            integral=float(np.sum((np.asarray(concentration[:-1])+np.asarray(concentration[1:]))*.5*np.diff(times))) if receptor else None
            route=summary.get('route_proxy',{});rp=route.get('case_proxy_au_s',{}).get(key)
            cases.append({'id':key,'title':LABELS[key],'assumption':assumptions[key],'frames':frames,'metrics':{'campus_mean':a[:,~invalid].mean(axis=1,dtype=np.float64).tolist(),'gate_mean':concentration,'gate_exposure':integral,'route_exposure':rp,'emitted_au':summary['case_metrics'][key]['emitted_au']}})
            checks[key]={'frames':n,'max_absolute_browser_error_au':worst,'exact_zero_preserved':True,'scientific_sha256':digest(root/'data'/f'{key}.npy')}
        plan=summary['source_mapping']['plan'];markers=[]
        for key,r in summary['receptors'].items():
            if key=='campus_centroid':continue
            valid=r['cases']['baseline']['valid'];markers.append({'id':key,'position_enu_m':r['definition']['enu_m'],'kind':'receptor' if valid else 'invalid','label':label if key==receptor else 'Unverified gate · no air value' if not valid else key.replace('_',' '),'note':r['definition']['certainty']})
        for name,point in [('Assumed nearby idling','gate_idling_point_enu_m'),('Assumed outer drop-off','peripheral_idling_point_enu_m')]:
            markers.append({'id':point,'position_enu_m':plan[point],'kind':'dropoff','label':name,'note':'Hypothetical source on mapped road; stopping permission unverified.'})
        route=summary.get('route_proxy',{});route_data=route.get('route',{});routes=[{'id':'candidate_walk','points_enu_m':route_data['enu_xy'],'note':route_data.get('certainty','Unverified walking route')} ] if route.get('available') else []
        sources=[r['url'] for r in site.get('sources',[]) if isinstance(r,dict) and r.get('url')]
        polygon=site.get('campus_polygon_enu',site.get('campus_polygon_enu_m',[]));polygon=polygon.get('coordinates',[[]])[0] if isinstance(polygon,dict) else polygon
        limits=list(summary['limitations'])+[site.get('polygon_semantics','Mapped school site; property boundary unverified.')]
        if 'candidate_gate' in summary['receptors'] and not summary['receptors']['candidate_gate']['cases']['baseline']['valid']:limits.append('The candidate gate is not a valid outdoor sample in the 4 m solid mask. The separately named frontage/receptor is shown; no value was invented at the gate.')
        catalog['schools'].append({'id':sid,'title':summary['name'],'address':site.get('official_address',site.get('address','')),'run_id':selected['run_id'],'center_enu_m':site['center_enu_m'],'bounds_enu_m':summary['bounds_enu_m'],'shape_yx':[ny,nx],'cell_m':4,'height_m':2,'times_s':times.tolist(),'site_polygons_enu_m':[polygon] if polygon else [],'markers':markers,'routes':routes,'route_valid_fraction':route.get('valid_duration_fraction',0),'primary_receptor_id':receptor,'primary_receptor_label':label,'invalid_mask':f'{sid}/invalid.png','encoding':{'transform':'log1p','scale':scale,'range':[0,hi]},'display_max':maximum,'difference_max':max(abs(v) for v in summary['difference_range']),'cases':cases,'limitations':limits,'sources':sources})
        evidence.append({'school_id':sid,'run_id':selected['run_id'],'manifest_sha256':digest(root/'manifest.json'),'summary_sha256':digest(root/'summary.json'),'encoding_checks':checks})
    write(out/'index.json',catalog);write(out/'provenance.json',{'source_config_sha256':digest(config_path),'schools':evidence,'pixels_are_quantized_display_only':True})
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(export(Storage.load(),a.config,a.output))
