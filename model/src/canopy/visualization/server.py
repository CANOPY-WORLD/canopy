"""Read-only local server. Running is never triggered by an HTTP request."""
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from common.server import ViewerHandler
from common.layout import metadata_root
from canopy.scenario.store import load
from canopy.visualization.profile import describe
from canopy.assets.store import load as load_asset

class Handler(ViewerHandler):
    def respond(self,head):
        path=urlsplit(self.path).path
        if path=='/' and not urlsplit(self.path).query:
            self.send_response(302);self.send_header('Location','/src/visualization/catalog/');self.send_header('Content-Length','0');self.end_headers();return
        try:
            if path=='/api/canopy/scenarios':
                entries=[]
                for p in sorted(metadata_root(self.storage.root).glob('*/scenario.json')):
                    data=load(self.storage,p.parent.name);available=bool(data['assets']) and bool(data['visualization']['layers'])
                    for reference in data['assets']:
                        try:load_asset(self.storage,data['scenario_id'],reference,verify=False)
                        except (ValueError,OSError,KeyError):available=False;break
                    entries.append({'scenario_id':data['scenario_id'],'title':data['title'],'preset':data['visualization']['preset'],'asset_count':len(data['assets']),'layer_count':len(data['visualization']['layers']),'available':available})
                return self.json_response(entries,head)
            if path.startswith('/api/canopy/scenarios/') and path.endswith('/visualization'):
                scenario=path.split('/')[-2]
                return self.json_response(describe(self.storage,scenario),head)
        except (ValueError,OSError,KeyError) as exc:
            self.send_error(400,str(exc));return
        super().respond(head)

def serve(storage,host='127.0.0.1',port=8769):
    server=ThreadingHTTPServer((host,port),partial(Handler,storage=storage))
    print(f'Canopy scenarios: http://{host}:{port}/',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
