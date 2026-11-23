"""Run included model weights on explicit fictional inputs and open the shared local viewer."""
import argparse,json,shutil,sys,tempfile,webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'model/src'))
from canopy._io import write
from common.storage import Storage
from canopy.running.runner import run
from canopy.visualization.profile import select

def prepare(workspace=None,request_path=None):
    if workspace is None:
        cache=Storage.load(ROOT).cache_root/'health-examples';cache.mkdir(parents=True,exist_ok=True)
        workspace=Path(tempfile.mkdtemp(prefix='inference-',dir=cache))
    else:
        workspace=Path(workspace).resolve();workspace.mkdir(parents=True,exist_ok=False)
    request=json.loads(Path(request_path or ROOT/'model/tests/fixtures/canopy/health_inference.json').read_text(encoding='utf-8'))
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
    write(workspace/'scenario'/scene/'scenario.json',scenario)
    write(workspace/'request.json',request)
    storage=Storage.load(workspace);result=run(storage,request)
    select(storage,scene,result['assets'],'laboratory')
    return workspace,scene,result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace');p.add_argument('--request');p.add_argument('--serve',action='store_true');p.add_argument('--open',action='store_true');p.add_argument('--port',type=int,default=8772);a=p.parse_args()
    workspace,scene,result=prepare(a.workspace,a.request)
    url=f'http://127.0.0.1:{a.port}/src/visualization/viewer/?scenario={scene}'
    print(json.dumps({'workspace':str(workspace),'status':result['status'],'assets':result['assets'],'viewer':url,'serve':f'canopy --root "{workspace}" serve --port {a.port}'},indent=2),flush=True)
    if a.serve:
        if a.open:
            import threading
            threading.Timer(1,lambda:webbrowser.open(url)).start()
        from canopy.visualization.server import serve
        serve(Storage.load(workspace),'127.0.0.1',a.port)
