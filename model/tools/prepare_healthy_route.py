"""Create an isolated private research workspace from an explicitly selected release."""
import argparse,json,shutil,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from canopy._io import write,digest
from canopy.assets.store import import_run
from common.storage import Storage

def prepare(source,workspace):
    source=Path(source).resolve(); workspace=Path(workspace).resolve()
    if workspace.exists(): raise FileExistsError(workspace)
    repo=Path(__file__).resolve().parents[2]
    version=json.loads((source/'VERSION.json').read_text())
    if version['version']!='2026.11.16-v2': raise ValueError('Expected explicit 2026.11.16-v2 input release')
    workspace.mkdir(parents=True)
    shutil.copy2(repo/'AGENTS.md',workspace/'AGENTS.md')
    shutil.copytree(repo/'asset/schemas',workspace/'asset/schemas')
    scenario=json.loads((repo/'scenario/imperial_corridor_8km/scenario.json').read_text())
    scenario['assets']={};scenario['tasks']={};scenario['visualization']['layers']=[]
    write(workspace/'scenario/imperial_corridor_8km/scenario.json',scenario)
    payload=workspace/'cache/input-staging';payload.mkdir(parents=True)
    files=[source/'pedestrian/generated/network.json']
    files+=list((source/'pedestrian/private/breathing_model').glob('*'))
    scene=source/'scenes/imperial_corridor_8km'
    files+=[scene/'scene.json',scene/'physics/manifest.json',scene/'context/traffic-am.bin',scene/'context/traffic-am.json']
    transport=json.loads((scene/'scene.json').read_text())['protocol_display']['npy_transport']
    for key in ['poll.npy','temp.npy','solar_20260621.npy','solar_20261221.npy','masks/poll_invalid.npy','masks/temp_invalid.npy']:
        files += [scene/'physics'/p['file'] for p in transport[key]['parts']]
    inventory={}
    for src in sorted(set(files)):
        if not src.is_file() or src.is_symlink():raise ValueError('Missing or linked bundle input: '+str(src))
        rel=src.relative_to(source);target=payload/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
        inventory[rel.as_posix()]=digest(target)
    profile=repo/'scenario/imperial_corridor_8km/experiments/healthy_route_extended_replay/profile.json'
    shutil.copy2(profile,payload/'pedestrian/scenario.json');inventory['pedestrian/scenario.json']=digest(payload/'pedestrian/scenario.json')
    write(payload/'bundle.json',dict(format='healthy-route-private-bundle-v1',scenario_id=scenario['scenario_id'],spatial=scenario['spatial'],files=inventory,source_release=version['version']))
    write(payload/'input.json',{'labels':['input_version'],'values':[2]})
    manifest=dict(schema_version='1.1.0',scene_id=scenario['scenario_id'],simulation='healthy_route',run_id='healthy_route_inputs_20261116_v2',status='complete',created_at='2026-11-16T00:00:00Z',spatial=scenario['spatial'],time={'unit':'s','samples':[]},provenance={'code_revision':'release-2026.11.16-v2','dirty':False,'parameters':{'purpose':'private healthy-route research inputs'},'inputs':[]},layers=[{'id':'input_version','kind':'time_series','format':'json','asset':'input.json','sampling':'static','field':{'name':'input_version','unit':'1'},'display':{'widget':'time_series','capabilities':[]}}],artifacts=[])
    for i,name in enumerate([*inventory,'bundle.json']):
        manifest['artifacts'].append({'id':'healthy_route_bundle' if name=='bundle.json' else 'input_'+str(i),'asset':name,'sha256':digest(payload/name),'media_type':'application/octet-stream'})
    write(payload/'manifest.json',manifest)
    refs=import_run(Storage.load(workspace),scenario['scenario_id'],payload)
    request=json.loads((repo/'model/tests/fixtures/canopy/healthy_route.json').read_text());request['inputs']['bundle']=refs[0]
    network=json.loads((payload/'pedestrian/generated/network.json').read_text())
    c=next(c for c in network['crossings'] if c['both_pavement_approaches'])
    request['parameters'].update(origin=c['edge'][0],goal=c['edge'][1])
    write(workspace/'request.json',request)
    print('Private workspace:',workspace)
    print('Request:',workspace/'request.json')
    return workspace

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--workspace',required=True)
    a=p.parse_args();prepare(a.source,a.workspace)
