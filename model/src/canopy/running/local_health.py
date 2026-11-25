"""Explicit loopback-only planning service; the shared Viewer remains read-only."""
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote
import json
import secrets
import threading
from canopy._io import read
from canopy.assets.store import load as load_asset
from canopy.running.runner import run, prepare_request
from canopy.visualization.profile import select
from canopy.visualization.server import Handler as ReadHandler
from canopy.scenario.store import load as load_scenario
from common.layout import visualization_root


class Session:
    def __init__(self, storage, request):
        self.storage=storage
        self.request=read(request)
        if self.request.get('model_id')!='healthy_route' or self.request.get('method_id')!='wave_cvae':
            raise ValueError('An explicit wave_cvae request is required')
        _,_,path=load_asset(storage,self.request['scenario_id'],self.request['inputs']['bundle'])
        self.bundle_path=path.parent
        self.network=read(self.bundle_path/'pedestrian/generated/network.json')
        self.token=secrets.token_urlsafe(32)
        self.lock=threading.Lock();self.job={'status':'idle'}
        self.allowed_files=set()
        self.allow_results(load_scenario(storage,self.request['scenario_id'])['assets'])

    def allow_results(self,references):
        allowed=set(self.allowed_files)
        for reference in references:
            _,manifest,path=load_asset(self.storage,self.request['scenario_id'],reference,verify=False)
            recording=next((a for a in manifest.get('artifacts',[]) if a['id']=='health_recording'),None)
            if recording is None:continue
            prefix='/project/'+self.request['scenario_id']+'/assets/bundles/'+path.parent.name+'/'
            allowed.update(prefix+name for name in ['manifest.json',recording['asset'],*[layer['asset'] for layer in manifest['layers']]])
        self.allowed_files=allowed

    def calculate(self,parameters):
        if not self.lock.acquire(blocking=False):raise RuntimeError('A journey is already being calculated')
        try:
            request={**self.request,'parameters':parameters}
            prepare_request(self.storage,request)
        except Exception:
            self.lock.release();raise
        self.job={'status':'running'}
        def work():
            try:
                result=run(self.storage,request)
                if result['status']!='complete':raise RuntimeError('Run did not complete')
                self.allow_results(result['assets'])
                select(self.storage,request['scenario_id'],result['assets'],'laboratory')
                self.job={'status':'complete','assets':result['assets'],'viewer':'/src/visualization/viewer/?scenario='+request['scenario_id']}
            except Exception:
                import traceback
                traceback.print_exc()
                self.job={'status':'failed','error':'Calculation failed. Check the local terminal and retained run diagnostics.'}
            finally:self.lock.release()
        threading.Thread(target=work,daemon=True).start()


class Handler(ReadHandler):
    def valid_host(self):
        return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'

    def respond(self,head):
        if not self.valid_host():return self.send_error(403,'Loopback host required')
        path=unquote(urlsplit(self.path).path)
        session=self.server.session
        if path=='/':
            data=(visualization_root(self.storage.root)/'healthy-route/planner.html').read_bytes()
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers()
            if not head:self.wfile.write(data)
            return
        if path=='/api/health/planning':
            return self.json_response({'token':session.token,'parameters':session.request['parameters'],
                'nodes':session.network['nodes'],'edges':[e['points'] for e in session.network['edges']]},head)
        if path=='/api/health/job':return self.json_response(session.job,head)
        # Never expose the private input bundle, caches or source records through HTTP.
        if path.startswith('/project/'):
            if path not in session.allowed_files:
                return self.send_error(403,'Private input or provenance resource')
        return super().respond(head)

    def do_POST(self):
        if not self.valid_host() or urlsplit(self.path).path!='/api/health/plan':return self.send_error(403)
        origin=self.headers.get('Origin')
        if origin!=f'http://127.0.0.1:{self.server.server_port}' or not secrets.compare_digest(self.headers.get('X-Planning-Token',''),self.server.session.token):return self.send_error(403)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=8192:raise ValueError('Invalid request size')
            parameters=json.loads(self.rfile.read(size))
            self.server.session.calculate(parameters)
        except RuntimeError:return self.send_error(409,'A calculation is already running')
        except Exception:return self.send_error(400,'Invalid planning request; check endpoints, mode, time and duration')
        return self.json_response({'status':'running'},False)


def serve(storage,request,port=8774):
    session=Session(storage,request)
    server=ThreadingHTTPServer(('127.0.0.1',port),partial(Handler,storage=storage))
    server.session=session
    print(f'Local planning: http://127.0.0.1:{server.server_port}/',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
