"""Pin verified current city inputs and evaluate an existing local recorded route."""
import argparse
import gzip
import shutil
from pathlib import Path
from canopy._io import read, write, digest
from canopy.assets.store import import_run, load
from canopy.running.runner import run
from canopy.running.provenance import snapshot_runtime
from common.storage import Storage
from healthy_route.build_network import build_for_workspace

ROOT=Path(__file__).resolve().parents[2]
SCENE='imperial_corridor_8km'
PREFIX='scenes/'+SCENE+'/'


def prepare(city, workspace, recording=None):
    city,workspace=Path(city).resolve(),Path(workspace).resolve()
    storage=Storage.load(workspace)
    if recording is not None:load(storage,SCENE,recording)
    locked=ROOT/'scenario'/SCENE/'data/manifest.json'
    manifest=read(locked);publication=read(ROOT/'scenario'/SCENE/'publication.json')
    profile_path=ROOT/'scenario'/SCENE/'experiments/healthy_route_current_city/profile.json'
    profile=read(profile_path)
    if profile['publication_manifest_sha256']!=digest(locked) or profile['publication_snapshot']!=publication['snapshot']:
        raise ValueError('Scenario experiment profile must be reviewed for this city publication')
    pin=digest(locked)[:16];run_id='city_alignment_inputs_'+pin+'_'+digest(Path(__file__))[:8]
    staging=workspace/'cache'/run_id
    if staging.exists():raise FileExistsError(staging)
    # Verify the entire public snapshot before preparing any derived input.
    for f in manifest['files']:
        from canopy._io import relative
        p=relative(city,f['viewer_path'])
        if p.stat().st_size!=f['bytes'] or digest(p)!=f['sha256']:
            raise ValueError('Pinned city checksum mismatch: '+f['viewer_path'])
    staging.mkdir(parents=True)
    inventory={}
    shutil.copyfile(profile_path,staging/'profile.json');inventory['profile.json']=digest(profile_path)
    for f in manifest['files']:
        name=f['viewer_path'];target=staging/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(city/name,target);inventory[name]=f['sha256']
    build_for_workspace(staging,staging)
    inventory['network.json']=digest(staging/'network.json')
    scene=read(staging/PREFIX/'scene.json');physics=read(staging/PREFIX/'physics/manifest.json')
    source_origin=read(staging/PREFIX/'context/vector_landscape/source/scene-meta.json')['origin']
    scenario=read(workspace/'scenario'/SCENE/'scenario.json')
    if any(source_origin[k]!=scenario['spatial']['origin'][k] for k in ['longitude','latitude']):
        raise ValueError('Current source and Scenario horizontal origins differ')
    transport=scene['protocol_display']['npy_transport'];fields={}
    for key,file,mask in [('pmx','poll.npy','masks/poll_invalid.npy'),('temperature','temp.npy','masks/temp_invalid.npy'),('sunlight','solar_20260621.npy','masks/solar_invalid.npy')]:
        a=physics['arrays'][file];t=transport[file];meta=t['meta']
        fields[key]=dict(shape=meta['shape'][-2:],dtype=meta['descr'],times_s=a['time_s'],
            origin_xy_m=a.get('origin_m',scene['grid']['domain_origin_xy_m'])[:2],
            cell_m=a.get('cell_m',scene['layers'].get('temp',{}).get('cell_m')),
            quantization=meta.get('quantization'),parts=[PREFIX+'physics/'+p['file'] for p in t['parts']],
            mask=PREFIX+'physics/'+transport[mask]['parts'][0]['file'],
            clock_offset_s=profile['solar_clock_offset_s'] if key=='sunlight' else 0)
    terrain=read(staging/PREFIX/'context/terrain/terrain.json')
    alignment=dict(snapshot=publication['snapshot'],repository_revision=publication['revision'],locked_manifest_sha256=digest(locked),
        origin=scene['grid']['origin_label'],**source_origin,axes='Right-handed ENU metres; render X=east,Y=up,Z=-north',
        presentation=profile['presentation'],
        horizontal_mapping='Exact selected network edges and all source XY vertices must match within 0.00001 m; no snapping or offsets.',
        vertical_source=terrain['terrain']['source'],vertical_datum=terrain['terrain']['vertical_datum'],
        network_builder_sha256=digest(ROOT/'model/src/healthy_route/build_network.py'),
        key_sources={'terrain':PREFIX+'context/terrain/terrain.json','walking_map':PREFIX+'context/vector_landscape/source/scene-meta.json','road_decks':PREFIX+'context/terrain/road-network.json.gz','traffic_and_signals':PREFIX+'context/traffic-native.json','pmx_provenance':PREFIX+'physics/traffic-pmx-provenance.json'},
        vertical_policy='Original route Z is discarded. Current terrain and matched road/deck heights define scene height. Retained ENU Z = scene height minus pinned terrain height. No certified geodetic datum conversion.',
        clock='Relative simulation seconds, original departure and waits preserved. Temperature and PMx sampled at t; their shared simulation t is not a common observation UTC.',
        solar_clock='Conditional 21 June clear-sky scenario: solar seconds = 31800 + t (08:50 BST at t=0; 07:50 UTC). This is an explicit scenario assumption, not a measured common epoch.',
        traffic_clock='Current native traffic only covers simulation seconds 680–720.9, outside PMx/temperature 0–600. Not overlaid or rebased; no vehicle-clearance claim.',
        field_limits='PMx is a partial traffic exhaust increment, zero initial/background; not total PM2.5. Presentation quantization retained. 4 m voxel mean; temperature is the 8 m slice. No breathing-height extrapolation.',
        missing='Original masks and quantization invalid codes remain unavailable. Temporal interpolation only inside each field coverage, no repeats, no spatial filling.',
        files=inventory)
    meta=dict(format='canopy-city-alignment-v1',files=inventory,fields=fields,alignment=alignment)
    write(staging/'city-inputs.json',meta)
    # Coarse and detailed geometry bytes are exact public inputs. The normalized
    # coarse mesh supplies the Geometry layer; all detailed source tiles remain
    # hashed artifacts. Native terrain is a separate explicit display transform.
    (staging/'geometry.glb').write_bytes(gzip.decompress((staging/PREFIX/'models/buildings.glb.gz').read_bytes()))
    write(staging/'input.json',{'labels':['snapshot'],'values':[1]})
    runtime_revision=snapshot_runtime(staging/'source_snapshot.tar.gz')
    shutil.copyfile(Path(__file__),staging/'prepare_city_alignment.py')
    payload=dict(schema_version='1.1.0',scene_id=SCENE,simulation='healthy_route',run_id=run_id,status='complete',created_at='2026-11-25T00:00:00Z',
        spatial=scenario['spatial'],time={'unit':'s','samples':[]},
        provenance={'code_revision':runtime_revision,'dirty':True,'parameters':{'purpose':'pinned public presentation inputs; native terrain conversion declared in city-inputs.json'},'inputs':[{'id':'publication_manifest','sha256':digest(locked)}]},
        layers=[{'id':'geometry','kind':'mesh','format':'glb','asset':'geometry.glb','sampling':'static','encoding':{'coordinate_frame':'glTF-y-up'},'display':{'widget':'mesh','capabilities':['pick','opacity']}},
                {'id':'input','kind':'time_series','format':'json','asset':'input.json','sampling':'static','field':{'name':'snapshot','unit':'1'},'display':{'widget':'time_series','capabilities':[]}}],artifacts=[])
    for i,name in enumerate([*inventory,'city-inputs.json']):
        payload['artifacts'].append({'id':'city_inputs' if name=='city-inputs.json' else 'source_'+str(i),'asset':name,'sha256':digest(staging/name),'media_type':'application/octet-stream'})
    for ident,name,media in [('source_snapshot','source_snapshot.tar.gz','application/gzip'),('preparation_source','prepare_city_alignment.py','text/x-python')]:
        payload['artifacts'].append({'id':ident,'asset':name,'sha256':digest(staging/name),'media_type':media})
    write(staging/'manifest.json',payload)
    refs=import_run(storage,SCENE,staging)
    if recording is None:
        return {'inputs':{'geometry':next(r for r in refs if '_geometry@' in r),
                          'city':next(r for r in refs if '_physics@' in r)}}
    request=dict(schema_version='2.0.0',scenario_id=SCENE,model_id='healthy_route',method_id='city_exposure',method_version='1.0.0',
        inputs={'geometry':next(r for r in refs if '_geometry@' in r),'city':next(r for r in refs if '_physics@' in r),'recording':recording},parameters={},execution={'device':'cpu','threads':1})
    write(workspace/'city-alignment-request.json',request)
    state=run(storage,request,retain=True)
    write(workspace/'city-recorded-preview.json',{'result':state['assets'][0]})
    return {'result':state['assets'][0],'diagnostics':state['diagnostics']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--city-data',required=True);p.add_argument('--workspace',required=True);p.add_argument('--recording',required=True)
    a=p.parse_args();print(prepare(a.city_data,a.workspace,a.recording))
