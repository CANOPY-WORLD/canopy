"""Canopy developer CLI; explicit execution, read-only visualization."""
import argparse
import json
from pathlib import Path
import sys
from jsonschema import ValidationError
from common.storage import Storage
from canopy._io import read, write


def main(argv=None):
    p=argparse.ArgumentParser(prog='canopy');p.add_argument('--root',type=Path)
    sub=p.add_subparsers(dest='command',required=True)
    models=sub.add_parser('models');models.add_argument('model',nargs='?');models.add_argument('method',nargs='?')
    init=sub.add_parser('init');init.add_argument('scenario');init.add_argument('--title');init.add_argument('--spatial',type=Path)
    run=sub.add_parser('run');run.add_argument('request',type=Path);run.add_argument('--dry-run',action='store_true');run.add_argument('--no-retain',action='store_true')
    task=sub.add_parser('run-task');task.add_argument('scenario');task.add_argument('task');task.add_argument('--dry-run',action='store_true');task.add_argument('--no-retain',action='store_true')
    imp=sub.add_parser('import-run');imp.add_argument('scenario');imp.add_argument('directory',type=Path)
    validate=sub.add_parser('validate');validate.add_argument('scenario');validate.add_argument('--metadata-only',action='store_true')
    view=sub.add_parser('view');view.add_argument('scenario');view.add_argument('assets',nargs='+');view.add_argument('--preset',choices=['engineering','city','laboratory'],default='engineering')
    serve=sub.add_parser('serve');serve.add_argument('--host',default='127.0.0.1');serve.add_argument('--port',type=int,default=8769)
    demo=sub.add_parser('demo');demo.add_argument('--scenario',default='demo');demo.add_argument('--physics',nargs='*',choices=['solar','flood','wind','temperature','pollution'],default=['solar','flood','wind'])
    pack=sub.add_parser('pack');pack.add_argument('scenario');pack.add_argument('destination',type=Path)
    cancel=sub.add_parser('cancel');cancel.add_argument('scenario');cancel.add_argument('model');cancel.add_argument('run_id')
    args=p.parse_args(argv)
    try:
        storage=Storage.load(args.root)
        if args.command=='models':
            from canopy.models.registry import catalog,describe
            result=describe(args.model,args.method) if args.model and args.method else catalog()
        elif args.command=='init':
            from canopy.scenario.store import create
            spatial=read(args.spatial) if args.spatial else synthetic_spatial()
            result=create(storage,args.scenario,args.title or args.scenario,spatial)
        elif args.command in ('run','run-task'):
            from canopy.running.runner import run,prepare_request
            if args.command=='run-task':
                from canopy.scenario.store import load
                request=load(storage,args.scenario)['tasks'][args.task]
            else:request=read(args.request)
            result={'valid':True,'request':prepare_request(storage,request)[0]} if args.dry_run else run(storage,request,retain=not args.no_retain)
        elif args.command=='import-run':
            from canopy.assets.store import import_run
            result=import_run(storage,args.scenario,args.directory)
        elif args.command=='validate':
            from canopy.scenario.store import load
            from canopy.assets.store import load as asset_load
            data=load(storage,args.scenario)
            for reference in data['assets']:asset_load(storage,args.scenario,reference,verify=not args.metadata_only)
            from canopy.visualization.profile import describe
            describe(storage,args.scenario)
            result={'valid':True,'scenario_id':args.scenario,'assets':len(data['assets']),'payloads_checked':not args.metadata_only}
        elif args.command=='view':
            from canopy.visualization.profile import select
            result=select(storage,args.scenario,args.assets,args.preset)
        elif args.command=='serve':
            from canopy.visualization.server import serve
            serve(storage,args.host,args.port);return 0
        elif args.command=='pack':
            from canopy.assets.package import pack
            result=pack(storage,args.scenario,args.destination)
        elif args.command=='cancel':
            workspace=storage.scratch(args.scenario,args.model,args.run_id)
            if not (workspace/'run.json').exists():raise ValueError('Unknown run')
            if read(workspace/'run.json')['status'] not in ['preparing','running','exporting']:raise ValueError('Run is not active')
            (workspace/'cancel.request').touch();result={'cancellation_requested':args.run_id}
        else: result=run_demo(storage,args.scenario,args.physics)
        print(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False));return 0
    except (ValueError,OSError,ValidationError,KeyError,RuntimeError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr);return 1

def synthetic_spatial():
    return {'frame':'ENU','units':'m','georeferenced':False,'origin':{'longitude':0,'latitude':0,'height_m':0,'vertical_datum':'synthetic local engineering datum'},'bounds_m':{'min':[0,0,0],'max':[32,32,16]}}

def run_demo(storage,scenario,physics):
    from canopy.scenario.store import create,load
    from canopy.models.registry import describe
    from canopy.running.runner import run
    from canopy.visualization.profile import select
    if not (storage.metadata(scenario)/'scenario.json').exists():create(storage,scenario,'Canopy · synthetic method demonstration',synthetic_spatial())
    else:load(storage,scenario)
    def request(model,method,inputs):
        spec=describe(model,method)
        return dict(schema_version='2.0.0',scenario_id=scenario,model_id=model,method_id=method,method_version=spec['version'],inputs=inputs,parameters={},execution={'device':'cpu','threads':1})
    geometry=run(storage,request('geometry','heightfield',{}));refs=geometry['assets'][:];geometry_ref=refs[0]
    methods={'solar':'shadow','flood':'shallow_water','wind':'mac','temperature':'finite_difference_numpy','pollution':'steady_tracer'}
    order=list(dict.fromkeys(physics))
    if any(model in order for model in ('temperature','pollution')):
        order=[model for model in order if model!='wind'];order.insert(0,'wind')
    tasks={'geometry':request('geometry','heightfield',{})};wind_ref=None
    for model in order:
        inputs={'geometry':geometry_ref}
        if model in ('temperature','pollution'):inputs['wind']=wind_ref
        tasks[model]=request(model,methods[model],inputs)
        result=run(storage,tasks[model]);refs.extend(result['assets'])
        if model=='wind':wind_ref=result['assets'][0]
    from canopy.scenario.store import lock
    with lock(storage,scenario):
        document=load(storage,scenario);document['tasks'].update(tasks)
        write(storage.metadata(scenario)/'scenario.json',document)
    select(storage,scenario,refs,'laboratory')
    return {'scenario':scenario,'assets':refs,'viewer':f'/src/visualization/viewer/?scenario={scenario}'}

if __name__=='__main__':raise SystemExit(main())
