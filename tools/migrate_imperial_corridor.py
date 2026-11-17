#!/usr/bin/env python3
"""Import retained Imperial Corridor display arrays into scenario-owned V2 assets.

The source root is local_viewer_20261102; the source report is local_physics_20261102.json.
All recorded samples, masks and float16 values are preserved. No simulation is run.
"""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import shutil
import sys
import tempfile
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from canopy._io import read,write,digest,relative
from canopy.scenario.store import create,load,lock
from canopy.assets.store import import_run,load as load_asset
from canopy.visualization.profile import select
from common.storage import Storage
from common.contract import validate

SCENE='imperial_corridor_8km'


def migrate(storage,source,report_path):
    source=Path(source).resolve();report_path=Path(report_path).resolve()
    folder=source/'scenes'/SCENE;physics=folder/'physics'
    scene=read(folder/'scene.json');original=read(physics/'manifest.json');report=read(report_path)
    if scene['id']!=SCENE or report['scene_id']!=SCENE:raise ValueError('Source scene identity mismatch')
    # These are source evidence, not defaults inferred from a viewer title.
    if 'terrain height' not in report['spatial_alignment'] or 'ENU' not in report['spatial_alignment']:
        raise ValueError('Source must document ENU and terrain-normalized geometry')
    lon,lat=report['origin_lon_lat'];x0,y0=scene['grid']['domain_origin_xy_m']
    if x0!=scene['grid']['x0'] or y0!=-scene['grid']['z_south']:raise ValueError('Source coordinate conventions disagree')
    # Enclose both the 8192 m computation and retained edge buildings.
    from urban_geometry.voxelization.glb_plan import read_glb_header
    from canopy.models.geometry import meshes
    geometry_path=relative(folder,scene['model']['url']);doc,_=read_glb_header(geometry_path);corners=[]
    for _,node,mesh,world in meshes(doc):
        for primitive in mesh['primitives']:
            acc=doc['accessors'][primitive['attributes']['POSITION']]
            if acc.get('normalized'):raise ValueError('Decode normalized bounds explicitly before import')
            lo,hi=acc['min'],acc['max']
            points=np.array([[x,y,z] for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])])@world[:3,:3].T+world[:3,3]
            enu=points[:,[0,2,1]];enu[:,1]*=-1;corners.extend(enu)
    width=scene['grid']['cols']*scene['grid']['cell_m'];height=scene['grid']['rows']*scene['grid']['cell_m']
    corners.extend([[x0,y0,0],[x0+width,y0+height,0]])
    spatial={'frame':'ENU','units':'m','georeferenced':True,'origin':{'longitude':lon,'latitude':lat,'height_m':0,'vertical_datum':'terrain-normalized height above local ground; not absolute ODN (source local_physics_20261102)'},'bounds_m':{'min':np.floor(np.min(corners,axis=0)).tolist(),'max':np.ceil(np.max(corners,axis=0)).tolist()}}
    if not (storage.metadata(SCENE)/'scenario.json').exists():create(storage,SCENE,scene['title'],spatial)
    if load(storage,SCENE)['spatial']!=spatial:raise ValueError('Existing Scenario has a different spatial definition')
    storage.cache_root.mkdir(parents=True,exist_ok=True)
    records=[];references=[]
    common_sources={'source_scene':folder/'scene.json','source_fields':physics/'manifest.json','source_report':report_path,'source_viewer_conventions':source/'viewer/3d/main.js'}
    def build(key,sources,make):
        identities={name:digest(path) for name,path in {**common_sources,**sources}.items()}
        import hashlib,json
        fingerprint=hashlib.sha256(json.dumps(identities,sort_keys=True).encode()).hexdigest()[:12]
        rid=f'recorded_20261102_{key}_{fingerprint}'
        existing=[ref for ref in load(storage,SCENE)['assets'] if ref.startswith(rid+'_')]
        if existing:
            for ref in existing:load_asset(storage,SCENE,ref)
            references.extend(existing);records.append({'group':key,'assets':existing,'source_sha256':identities});return
        with tempfile.TemporaryDirectory(prefix='corridor-import-',dir=storage.cache_root) as temp:
            stage=Path(temp)
            m={'schema_version':'1.1.0','scene_id':SCENE,'simulation':key,'run_id':rid,'status':'complete','created_at':datetime.now(timezone.utc).isoformat(),'spatial':spatial,'time':{'unit':'s','samples':[]},'layers':[],'artifacts':[],
               'provenance':{'code_revision':'legacy-unrecorded','dirty':False,'inputs':[{'id':name,'sha256':sha} for name,sha in identities.items()],
               'parameters':{'importer':'tools/migrate_imperial_corridor.py','historical_solver_revision':'unknown; do not substitute importer version','recorded_source':'local_viewer_20261102','disclaimer':'Recorded display grids; original clocks are independent. Terrain-normalized geometry; ground fields are not warped onto survey terrain.','geometry_dependency':'not inferred; historical exact geometry version unrecorded','spatial_resampling':'none during migration; source display aggregation retained','time_alignment':'relative comparison only; no shared physical epoch'}}}
            for name,path in common_sources.items():
                target=stage/(name+path.suffix);shutil.copy2(path,target)
                m['artifacts'].append({'id':name,'asset':target.name,'sha256':digest(target),'media_type':'text/javascript' if target.suffix=='.js' else 'application/json'})
            # Record adapter identity separately from unknown historical solver provenance.
            shutil.copy2(Path(__file__),stage/'migration_adapter.py')
            m['artifacts'].append({'id':'migration_adapter','asset':'migration_adapter.py','sha256':digest(stage/'migration_adapter.py'),'media_type':'text/x-python'})
            make(stage,m);write(stage/'manifest.json',m);validate(stage/'manifest.json')
            refs=import_run(storage,SCENE,stage);references.extend(refs);records.append({'group':key,'assets':refs,'source_sha256':identities})
    def geometry(stage,m):
        shutil.copy2(geometry_path,stage/'geometry.glb')
        m['layers']=[{'id':'geometry','kind':'mesh','format':'glb','asset':'geometry.glb','sampling':'static','encoding':{'coordinate_frame':'glTF-y-up'},'display':{'widget':'mesh','capabilities':['pick','opacity']}}]
    build('geometry',{'source_geometry':geometry_path},geometry)
    groups=[('wind',['wind.npy'],'wind'),('temperature',['temp.npy'],'temp'),('solar_summer',['solar_20260621.npy','shadow_20260621.npy'],'solar'),('solar_winter',['solar_20261221.npy','shadow_20261221.npy'],'solar'),('pollution',['poll.npy'],'poll'),('flood',['flood.npy'],'flood')]
    for group,files,config_key in groups:
        config=scene['layers'][config_key];mask_paths={}
        for name in files:
            if config_key=='wind':mask_name=scene['masks']['solid_wind']['file']
            elif config_key=='temp':mask_name=scene['masks']['footprint'][str(int(config['cell_m']))]
            else:mask_name=scene['masks']['layer_invalid']['shadow' if name.startswith('shadow') else config_key]
            mask_paths[name]=relative(physics,mask_name)
        sources={f'array_{i}':relative(physics,name) for i,name in enumerate(files)}
        sources.update({f'mask_{i}':mask_paths[name] for i,name in enumerate(files)})
        def field(stage,m):
            for name in files:
                data=np.load(relative(physics,name),mmap_mode='r',allow_pickle=False);meta=original['arrays'][name]
                if list(data.shape)!=meta['shape'] or len(data)!=len(meta['time_s']):raise ValueError('Recorded shape/time differs from source metadata')
                vector=meta['axes']=='TCYX'
                if meta['axes'] not in ['TCYX','TYX'] or (vector and data.shape[1]!=3):raise ValueError('Unsupported source axes')
                if data.shape[-1]*config['cell_m']!=width or data.shape[-2]*config['cell_m']!=height:raise ValueError('Recorded field does not cover declared domain')
                if m['layers'] and m['time']['samples']!=meta['time_s']:raise ValueError('Layers in a bundle must share exact sample times')
                m['time']['samples']=meta['time_s']
                id=Path(name).stem;mask=np.load(mask_paths[name],allow_pickle=False)
                if config_key=='wind':mask=mask[scene['masks']['solid_wind']['layer']]
                if mask.shape!=data.shape[-2:] or not np.isin(mask,[0,1]).all():raise ValueError('Invalid source mask')
                np.save(stage/(id+'_invalid.npy'),np.asarray(mask,dtype='u1'))
                frames=[];(stage/id).mkdir()
                for i in range(len(data)):
                    rel=f'{id}/{i:05d}.npy';np.save(stage/rel,np.ascontiguousarray(data[i:i+1]));frames.append(rel)
                write(stage/(id+'_frames.json'),{'frames':frames})
                encoding={'coordinate_frame':'ENU','dtype':data.dtype.str,'shape':list(data.shape),'axes':meta['axes'],'origin_m':[x0,y0,config['y'] if config_key in ('wind','temp','poll') else 0],'spacing_m':[config['cell_m']]*2,'sample_location':'cell_center','byte_order':'little','compression':'none','frame_assets':frames,'mask_asset':id+'_invalid.npy','mask_dtype':'|u1','mask_semantics':'invalid_nonzero'}
                kind='vector_field' if vector else 'scalar_field'
                m['layers'].append({'id':id,'kind':kind,'format':'npy_frames','asset':id+'_frames.json','sampling':'step','encoding':encoding,'field':{'name':id,'unit':meta['unit']},'display':{'widget':kind,'capabilities':['pick','legend','opacity']}})
                m['provenance']['parameters'][id]={'display_aggregation':meta.get('display_aggregation','none recorded'),'source_shape':meta['shape'],'sampling':'exact saved frames; hold previous sample within recorded domain','original_display_lift_m':config['y'] if config_key in ('solar','flood') else 0}
        build(group,sources,field)
    select(storage,SCENE,references,'city')
    with lock(storage,SCENE):
        scenario=load(storage,SCENE)
        # All recorded layers remain selectable; default avoids stacked unrelated scalar maps.
        for selection in scenario['visualization']['layers']:selection['visible']=selection['layer'] in ('geometry','wind')
        scenario['legacy']={'viewer':'/viewer/3d/?scene=imperial_corridor_8km','description':'Preserved detailed website, terrain/context, traffic and UAV presentation'}
        write(storage.metadata(SCENE)/'scenario.json',scenario)
    result={'scenario_id':SCENE,'groups':records,'selected_assets':references,'source_untouched':True,'published':False,'time_policy':'Original time_s copied verbatim; independent clocks, no invented epoch','data_policy':'Recorded float16 samples split into frames without resampling; source masks preserved','remaining_legacy':'Detailed tiles, terrain/context, traffic and UAV site presentation retain their original entrypoint'}
    write(storage.metadata(SCENE)/'migration.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);args=p.parse_args()
    result=migrate(Storage.load(args.root),args.source,args.report)
    print(f"Imported {len(result['selected_assets'])} private assets for {SCENE}")
