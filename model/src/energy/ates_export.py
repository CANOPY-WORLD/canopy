"""Protocol packaging for recorded ATES inference or retained cycle aggregates."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import uuid
import zipfile

import numpy as np
import trimesh

from common.storage import Storage
from common.export import write, digest
from common.contract import validate
from common.runs import promote, refresh_catalog
from common.catalog import view as check_view
from energy.ates import YEAR, heat_dispatch
from energy.pilot import ribbons


def write_run(config_path, *, inference=None, model_source=None, cycle_source=None, retain=False):
    storage=Storage.load();config=json.loads(Path(config_path).read_text());scene=config['scene_id']
    spatial=json.loads((storage.metadata(scene)/'project.json').read_text())['spatial']
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:6]
    rid=('ates_field_' if inference else 'ates_cycles_')+stamp
    out=storage.scratch(scene,'energy',rid);out.mkdir(parents=True,exist_ok=False)
    write(out/'config.json',config); layers=[]
    def scalar(name,positions,values,unit,field,widget='scalar_field'):
        asset=f'data/{name}.json';write(out/asset,dict(positions=np.asarray(positions).tolist(),values=np.asarray(values).tolist()))
        display=dict(widget=widget,capabilities=['pick','opacity','legend'])
        if widget=='thermal_slice':display['range']=[8,18]
        layers.append(dict(id=name,kind='scalar_field',format='json',asset=asset,sampling='step',field=dict(name=field,unit=unit),display=display))
    def series(name,labels,values,unit,field):
        asset=f'data/{name}.json';write(out/asset,dict(labels=labels,values=np.asarray(values).tolist()))
        layers.append(dict(id=name,kind='time_series',format='json',asset=asset,sampling='step',field=dict(name=field,unit=unit),display=dict(widget='time_series',capabilities=['pick','legend','opacity'])))
    def mesh(name,obj):
        asset=f'data/{name}.glb';(out/'data').mkdir(exist_ok=True);obj.export(out/asset)
        layers.append(dict(id=name,kind='mesh',format='glb',asset=asset,sampling='static',encoding=dict(coordinate_frame='glTF-y-up'),display=dict(widget='mesh',capabilities=['pick','opacity'])))
    origin=np.asarray(config['model_origin_enu_m'],float)
    if config['model_yaw_deg']!=0:raise ValueError('Pilot slices require yaw=0; do not silently rotate grids')
    field_report=None
    if inference:
        inference=Path(inference);model_source=Path(model_source)
        shutil.copytree(inference,out/'recorded');shutil.copytree(model_source,out/'model_source')
        meta=json.loads((model_source/'scenario.json').read_text()); names=meta['param_names'];params=dict(zip(names,meta['params']))
        times=np.load(inference/'times.npy'); temp=np.load(inference/'temperature.npy',mmap_mode='r');wells=np.load(inference/'wells.npy')
        axes=[np.load(inference/(k+'.npy'))for k in ('x','y','z')]
        if temp.shape!=(len(times),*map(len,axes)) or wells.shape!=(len(times),8) or not np.all(np.diff(times)>0) or not np.isfinite(temp).all() or not np.isfinite(wells).all():raise ValueError('Invalid recorded inference')
        if not np.array_equal(times,np.asarray(meta['times_s'])) or not np.array_equal(wells[:,:2],np.asarray(meta['rates_m3_s'],dtype='<f4')):raise ValueError('Original schedule changed')
        for depth in (-60,-135):
            iz=int(np.abs(axes[2]-depth).argmin());x,y=np.meshgrid(axes[0],axes[1],indexing='ij')
            positions=np.stack([x,y,np.full_like(x,axes[2][iz])],axis=-1).reshape(-1,3)+origin
            scalar('temperature_depth_'+str(abs(depth)),positions,temp[:,:,:,iz].reshape(len(times),-1),'degC',f'ATES prediction · actual z={axes[2][iz]:.2f} m','thermal_slice')
        iy=int(np.abs(axes[1]).argmin());x,z=np.meshgrid(axes[0],axes[2],indexing='ij')
        positions=np.stack([x,np.full_like(x,axes[1][iy]),z],axis=-1).reshape(-1,3)+origin
        scalar('temperature_vertical',positions,temp[:,:,iy,:].reshape(len(times),-1),'degC',f'ATES prediction · actual y={axes[1][iy]:.2f} m','thermal_slice')
        dispatch=heat_dispatch(wells[:,2:4],wells[:,:2],demand_kw=config['building_heat_demand_kw'],cop=config['heat_pump_cop'],return_deg_c=config['source_return_temperature_deg_c'])
        series('well_temperature',['Cold well','Warm well'],wells[:,2:4],'degC','Surrogate well temperatures')
        series('heat_supply',['HP heat','Backup','Source used'],np.stack([dispatch['delivered_kw'],dispatch['backup_heat_kw'],dispatch['source_used_kw']],axis=1),'kW','Assumed one-way heat dispatch')
        series('electricity',['Heat pump','Backup'],np.stack([dispatch['hp_electric_kw'],dispatch['backup_electric_kw']],axis=1),'kW','Assumed heating electricity; excludes pumping')
        values=dispatch['delivered_kw'];value_unit='kW';value_title='Assumed building heat from ATES + heat pump'
        field_report=json.loads((inference/'inference.json').read_text())
        disclaimer=config['disclaimer']+' 地下色块为已计算节点值；井筒半径放大显示。'
    else:
        cycle_source=Path(cycle_source);shutil.copytree(cycle_source,out/'cycle_source')
        a=np.load(cycle_source/'energy_arrays.npz',allow_pickle=False)
        matches=np.flatnonzero(a['ids']==config['scenario_id'])
        if len(matches)!=1:raise ValueError('Scenario not present exactly once')
        i=int(matches[0]);e=a['surrogate'][i]
        if e.shape!=(9,2) or not np.isfinite(e).all():raise ValueError('Invalid cycle energies')
        with (cycle_source/'scenario_energy.csv').open()as f:row=next(r for r in csv.DictReader(f)if int(r['scenario'])==config['scenario_id'])
        d,L,S=[float(row[k])for k in ('d_m','L_m','S_m')]
        params={'Wellspacing [m]':d,'Well1_depth [m]':-(50+L),'Well2_depth [m]':-(50+L)-S,'Well1_screenlength [m]':L,'Well2_screenlength [m]':L}
        # Upstream protocol defines different warm/cold extraction windows for a
        # paired cycle. Place the aggregate at the later (cold) completion time.
        times=(np.arange(9)+5/3)*YEAR
        series('recovered_cycle_energy',['Cold recovery','Warm recovery'],e,'MWh','Surrogate recovery per completed cycle pair; 13 C reference')
        series('warm_energy_comparison',['Surrogate','Simulation'],np.stack([e[:,1],a['reference'][i,:,1]],axis=1),'MWh','Warm cycle energy, surrogate vs source simulation')
        cop=config['heat_pump_cop'];demand_mwh=config['building_heat_demand_kw']*(YEAR/3)/3600/1000
        delivered=np.minimum(demand_mwh,np.maximum(e[:,1],0)/(1-1/cop));hp=delivered/cop;backup=demand_mwh-delivered
        series('assumed_cycle_heating',['HP heat','HP electric','Backup heat'],np.stack([delivered,hp,backup],axis=1),'MWh','Assumed warm-season aggregate; not an hourly dispatch')
        values=delivered;value_unit='MWh';value_title='Assumed heat per building per completed warm cycle'
        disclaimer=config['disclaimer']+' 当前只有已保存周期热量：曲线为每周期MWh，不是瞬时功率。Vega证书过期，地下温度场尚未载入；未生成替代温度场。'
    x0,y0,z0=origin;d=params['Wellspacing [m]']
    for w,name,color in [(1,'cold_well',[65,165,255,255]),(2,'warm_well',[255,104,55,255])]:
        x=x0+(-1 if w==1 else 1)*d/2;bottom=z0+params[f'Well{w}_depth [m]'];L=params[f'Well{w}_screenlength [m]']
        bore=trimesh.creation.cylinder(radius=3,height=-bottom+z0+8,sections=12)
        # trimesh cylinder is z-up; convert explicit scene ENU -> GLB x/up/-north.
        bore.apply_translation([x,y0,(bottom+z0+8)/2]);bore.vertices=bore.vertices[:,[0,2,1]];bore.vertices[:,2]*=-1;bore.visual.vertex_colors=color
        screen=trimesh.creation.cylinder(radius=7,height=L,sections=12);screen.apply_translation([x,y0,bottom+L/2]);screen.vertices=screen.vertices[:,[0,2,1]];screen.vertices[:,2]*=-1;screen.visual.vertex_colors=color
        mesh(name,trimesh.util.concatenate([bore,screen]))
    selected=json.loads((storage.run(scene,config['energy_context_run'])/'selected_buildings.json').read_text())
    samples=json.loads((storage.run(scene,config['energy_context_run'])/'solar_samples.json').read_text())
    positions=np.asarray(samples['positions']);n=len(positions)
    scalar('building_heat',positions,np.repeat((values/n)[:,None],n,axis=1),value_unit,value_title)
    context_run=storage.run(scene,config['energy_context_run'])
    source_manifest=json.loads((context_run/'solar/source_manifest.json').read_text())
    enc=source_manifest['layers'][0]['encoding'];dx,dy=enc['spacing_m'];ox,oy,_=enc['origin_m']
    heights=np.load(context_run/'solar/surface_height_m.npy')
    for b in selected:
        b['roof_positions_enu_m']=[[ox+(x+.5)*dx,oy+(y+.5)*dy,float(heights[y,x])+.6] for y,x in b['raster_cells_yx']]
    write(out/'building_catalog.json',dict(buildings=selected,positions=positions.tolist(),cell_size_m=[dx,dy]))
    next(l for l in layers if l['id']=='building_heat')['display']['widget']='building_heat'

    # Planning links have no claim to real route, pipe or electrical connectivity.
    mesh('assumed_heat_connections',ribbons([__import__('shapely.geometry',fromlist=['LineString']).LineString([[x0,y0],p[:2]])for p in positions],[255,185,75,255],z=16,width=3,dashed=True))
    pump=trimesh.creation.box(extents=[25,18,20]);pump.apply_translation([x0,9,-y0]);pump.visual.vertex_colors=[245,190,65,255];mesh('assumed_heat_pump',pump)
    spatial={**spatial,'bounds_m':{'min':[spatial['bounds_m']['min'][0],spatial['bounds_m']['min'][1],-250+z0],'max':spatial['bounds_m']['max']}}
    presentation=dict(building_catalog='building_catalog.json',time_unit='model_year',year_seconds=YEAR,playback_rate=YEAR/6,initial_time_s=float(times[min(24,len(times)-1)]),geometry_opacity=.18,labels={'cold_well':'冷井（模型几何 / 假设位置）','warm_well':'热井（模型几何 / 假设位置）','temperature_vertical':'地下温度 · 纵剖面','temperature_depth_60':'地下温度 · 浅层切片','temperature_depth_135':'地下温度 · 深层切片','building_heat':'六栋建筑 · 假设供热分配','assumed_heat_connections':'假设供热连接','assumed_heat_pump':'假设热泵','recovered_cycle_energy':'代理模型 · 每周期取热量','warm_energy_comparison':'代理模型与原仿真对比','assumed_cycle_heating':'假设热泵 · 周期能量收支'})
    report=dict(mode='field_inference'if inference else 'retained_cycle_results',scenario_id=config['scenario_id'],field_inference=field_report,field_available=bool(inference),samples=len(times),time_range_s=[float(times[0]),float(times[-1])],model_to_scene=dict(translation_enu_m=origin.tolist(),yaw_deg=0,status='hypothetical placement; no site geology validation'),well_parameters=params,assumptions=config,limitations=['Fixed upstream injection schedule; one-way energy accounting, no reservoir feedback.','No local geology, permitting, drilling or building-network connection validation.','Temperature field remains unavailable in cycle-only mode; do not interpolate cycle energies into instantaneous heat powers.'])
    write(out/'report.json',report)
    with zipfile.ZipFile(out/'source_snapshot.zip','x',zipfile.ZIP_DEFLATED)as archive:
        for folder in ('src/energy','src/visualization/widgets','src/visualization/shared','src/visualization/viewer'):
            for p in (storage.root/folder).glob('*'):
                if p.is_file()and p.suffix in ('.py','.mjs','.html','.css','.txt'):archive.write(p,str(p.relative_to(storage.root)))
    assets={l['asset']for l in layers};artifacts=[]
    for i,p in enumerate(sorted(out.rglob('*'))):
        if p.is_file()and str(p.relative_to(out))not in assets:
            artifacts.append(dict(id='source_snapshot'if p.name=='source_snapshot.zip'else f'artifact_{i}',asset=str(p.relative_to(out)),sha256=digest(p),media_type='application/octet-stream'))
    m=dict(schema_version='1.1.0',scene_id=scene,simulation='ates_energy',run_id=rid,status='complete',created_at=datetime.now(timezone.utc).isoformat(),provenance=dict(code_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,parameters=dict(disclaimer=disclaimer,presentation=presentation,source_mode=report['mode']),inputs=[dict(id='ates_configuration',sha256=digest(out/'config.json'))]),spatial=spatial,time=dict(unit='s',samples=times.tolist()),layers=layers,artifacts=artifacts)
    write(out/'manifest.json',m);validate(out/'manifest.json')
    if retain:
        destination=promote(storage,out);vid=rid.lower();base=config['geometry_run'];context=config['energy_context_run']
        view=dict(schema_version='1.1.0',scene_id=scene,title='Canary Wharf · ATES 地下储热与城市供热测试',time_alignment='relative',runs=[rid,base],layers=[dict(run_id=rid,layer_id=l['id'],visible=l['id']!='temperature_depth_60')for l in layers]+[dict(run_id=base,layer_id='geometry',visible=True)],camera=dict(position=[x0+650,y0-900,650],target=[x0,y0,-65]))
        # Static context only: deliberately exclude the 600-second energy curves.
        write(storage.metadata(scene)/'views'/f'{vid}.json',view);check_view(storage,scene,vid);refresh_catalog(storage)
        print('VIEW',vid);print('RUN',destination)
    else:print('TRIAL',out)
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--inference',type=Path);p.add_argument('--model-source',type=Path);p.add_argument('--cycle-source',type=Path);p.add_argument('--retain',action='store_true');a=p.parse_args()
    if bool(a.inference)==bool(a.cycle_source):p.error('Choose exactly one source mode')
    if a.inference and not a.model_source:p.error('Inference requires its staged model source')
    write_run(a.config,inference=a.inference,model_source=a.model_source,cycle_source=a.cycle_source,retain=a.retain)
