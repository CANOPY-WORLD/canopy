"""Prepare a participant-free city Health example in a new local workspace.

Requires the exact public city snapshot and matching public transportation
sources. No downloads, participant records, or private saved routes are used.
"""
import argparse
from pathlib import Path
import shutil
from canopy._io import read, write
from canopy.assets.store import load
from canopy.running.runner import run
from common.storage import Storage
from healthy_route.source_walking_network import build_pinned
from healthy_route.city_physiology import EstimatedCityFields, model_inputs, solar_input
from prepare_city_alignment import prepare as prepare_alignment
from prepare_city_connections import prepare as prepare_connections
from prepare_health_physiology import prepare as prepare_physiology

ROOT=Path(__file__).resolve().parents[2]
SCENE='imperial_corridor_8km'


def prepare(city_data, segments, connectors, workspace, example=False, origin=None, goal=None, departure=0):
    if not example and (origin is None or goal is None):
        raise ValueError('Select --example or provide both explicit node IDs')
    workspace=Path(workspace).resolve()
    workspace.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(ROOT/'AGENTS.md',workspace/'AGENTS.md')
    scenario=read(ROOT/'scenario'/SCENE/'scenario.json')
    scenario.update(assets={},tasks={},visualization={'template':'standard','preset':'city','layers':[],'time_alignment':'relative'})
    write(workspace/'scenario'/SCENE/'scenario.json',scenario)
    shutil.copytree(ROOT/'asset/schemas',workspace/'asset/schemas')
    inputs=prepare_alignment(city_data,workspace)['inputs']
    inputs['physiology']=prepare_physiology(workspace,ROOT/'model/tests/fixtures/canopy/city_physiology_inputs.json')
    storage=Storage.load(workspace)
    _,_,city=load(storage,SCENE,inputs['city'])
    network,_=build_pinned(city.parent,segments,connectors)
    profile=read(ROOT/'scenario'/SCENE/'experiments/healthy_route_current_city/crossing-health-profile.json')
    if example:
        # Deterministic small source-mapped example; no user's saved endpoints.
        fields=EstimatedCityFields(city.parent,read(city.parent/'city-inputs.json')['fields'])
        fields.estimation_method='idw4'
        candidates=[]
        for edge in sorted(network['edges'],key=lambda e:(e['u'],e['v'])):
            length=edge['distance'][-1]
            if not 5<=length<=15:continue
            try:
                for point in edge['points']:
                    model_inputs(fields,point,0,profile);solar_input(fields,point,0,profile)
            except ValueError:continue
            candidates.append(edge)
            break
        if not candidates:raise ValueError('No supported small example edge; select explicit endpoints')
        edge=min(candidates,key=lambda e:(e['u'],e['v']))
        origin,goal=edge['u'],edge['v']
    request=read(ROOT/'model/tests/fixtures/canopy/city_walk.json')
    request['inputs']=inputs
    request['parameters'].update(profile,origin=origin,goal=goal,departure_s=departure)
    write(workspace/'source-city-request.json',request)
    prepare_connections(workspace,workspace/'source-city-request.json',segments,connectors,origin,goal,workspace/'city-walk-request.json')
    request=read(workspace/'city-walk-request.json')
    result=run(storage,request,retain=True)
    write(workspace/'city-recorded-preview.json',{'result':result['assets'][0]})
    return {'result':result['assets'][0],'inputs':request['inputs'],'origin':origin,'goal':goal,
            'physiology':'synthetic; no participant records', 'workspace':str(workspace)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['city-data','segments','connectors','workspace']:parser.add_argument('--'+key,required=True,type=Path)
    parser.add_argument('--example',action='store_true')
    parser.add_argument('--origin');parser.add_argument('--goal')
    parser.add_argument('--departure',type=float,default=0)
    args=parser.parse_args()
    print(prepare(args.city_data,args.segments,args.connectors,args.workspace,args.example,args.origin,args.goal,args.departure))
