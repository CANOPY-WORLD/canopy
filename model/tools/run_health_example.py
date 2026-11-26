"""Run included model weights on explicit fictional inputs and open the shared local viewer."""
import argparse,json,shutil,sys,tempfile,webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'model/src'))
from canopy._io import write, digest, relative
from common.storage import Storage
from canopy.running.runner import run
from canopy.visualization.profile import select

def recorded_input():
    """Verify the pinned fictional recording before importing any bytes."""
    pin=json.loads((ROOT/'model/healthy_route/DEMO_RESULT.json').read_text(encoding='utf-8'))
    source=relative(ROOT,pin['path'])
    for name,expected in pin['files'].items():
        if digest(relative(source,name))!=expected:raise ValueError(f'Recorded preview checksum mismatch: {name}')
    manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    if pin['derived_from'] or manifest['provenance']['inputs']:raise ValueError('Fictional preview must have no external Asset dependencies')
    request=json.loads((source/'provenance/request.json').read_text(encoding='utf-8'))
    return pin,source,manifest,request

def prepare(workspace=None,request_path=None,recorded=False):
    if recorded and request_path:raise ValueError('Choose recorded replay or a new request')
    retained=recorded_input() if recorded else None
    if workspace is None:
        cache=Storage.load(ROOT).cache_root/'health-examples';cache.mkdir(parents=True,exist_ok=True)
        workspace=Path(tempfile.mkdtemp(prefix='inference-',dir=cache))
    else:
        workspace=Path(workspace).resolve();workspace.mkdir(parents=True,exist_ok=False)
    request=retained[3] if retained else json.loads(Path(request_path or ROOT/'model/tests/fixtures/canopy/health_inference.json').read_text(encoding='utf-8'))
    if request['model_id']!='healthy_route' or request['method_id']!='breathing_cvae':raise ValueError('This launcher accepts breathing_cvae requests only')
    from common.storage import identifier
    scene=identifier(request['scenario_id'])
    positions=request['parameters']['positions_m']
    lower=[min(p[i] for p in positions)-10 for i in range(3)]
    upper=[max(p[i] for p in positions)+10 for i in range(3)]
    (workspace/'AGENTS.md').write_text('Disposable health inference workspace.\n')
    shutil.copytree(ROOT/'asset/schemas',workspace/'asset/schemas')
    # Reuse the shared scientific viewer, without copying the public city website.
    shutil.copytree(ROOT/'visualizer/src',workspace/'visualizer/src',ignore=shutil.ignore_patterns('__pycache__'))
    scenario={'schema_version':'2.0.0','scenario_id':scene,'title':'Health inference: '+request['parameters']['input_label'],
        'spatial':{'frame':'ENU','units':'m','georeferenced':False,'origin':{'longitude':0,'latitude':0,'height_m':0,'vertical_datum':'Explicit local example coordinates; not London geography'},'bounds_m':{'min':lower,'max':upper}},
        'assets':{},'tasks':{},'visualization':{'template':'standard','preset':'laboratory','layers':[],'time_alignment':'relative'}}
    if retained:scenario['spatial']=retained[2]['spatial']
    write(workspace/'scenario'/scene/'scenario.json',scenario)
    write(workspace/'request.json',request)
    storage=Storage.load(workspace)
    if retained:
        from canopy.assets.store import import_run,load
        references=import_run(storage,scene,retained[1],expected_kind='physics')
        if references!=[retained[0]['asset_ref']]:raise ValueError('Recorded preview identity mismatch')
        asset,_,_=load(storage,scene,references[0])
        if asset['derived_from']!=retained[0]['derived_from']:raise ValueError('Recorded preview dependency mismatch')
        result={'status':'complete','assets':references}
    else:result=run(storage,request)
    select(storage,scene,result['assets'],'laboratory')
    return workspace,scene,result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace');g=p.add_mutually_exclusive_group();g.add_argument('--request');g.add_argument('--recorded',action='store_true');p.add_argument('--serve',action='store_true');p.add_argument('--open',action='store_true');p.add_argument('--port',type=int,default=8772);a=p.parse_args()
    workspace,scene,result=prepare(a.workspace,a.request,a.recorded)
    url=f'http://127.0.0.1:{a.port}/src/visualization/viewer/?scenario={scene}'
    print(json.dumps({'workspace':str(workspace),'status':result['status'],'assets':result['assets'],'viewer':url,'serve':f'canopy --root "{workspace}" serve --port {a.port}'},indent=2),flush=True)
    if a.serve:
        if a.open:
            import threading
            threading.Timer(1,lambda:webbrowser.open(url)).start()
        from canopy.visualization.server import serve
        serve(Storage.load(workspace),'127.0.0.1',a.port)
