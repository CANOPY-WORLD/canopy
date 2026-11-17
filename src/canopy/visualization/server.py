"""Read-only local server. Running is never triggered by an HTTP request."""
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from common.server import ViewerHandler
from canopy.scenario.store import load
from canopy.visualization.profile import describe

class Handler(ViewerHandler):
    def respond(self,head):
        path=urlsplit(self.path).path
        try:
            if path=='/api/canopy/scenarios':
                return self.json_response([{'scenario_id':(d:=load(self.storage,p.parent.name))['scenario_id'],'title':d['title']} for p in sorted((self.storage.root/'project').glob('*/scenario.json'))],head)
            if path.startswith('/api/canopy/scenarios/') and path.endswith('/visualization'):
                scenario=path.split('/')[-2]
                return self.json_response(describe(self.storage,scenario),head)
        except (ValueError,OSError,KeyError) as exc:
            self.send_error(400,str(exc));return
        super().respond(head)

def serve(storage,host='127.0.0.1',port=8769):
    server=ThreadingHTTPServer((host,port),partial(Handler,storage=storage))
    print(f'Canopy viewer: http://{host}:{port}/src/visualization/viewer/?scenario=demo',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
