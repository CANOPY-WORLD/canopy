"""Open explicit private route planning and the shared recorded-result Viewer."""
import argparse
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'model/src'))
from common.storage import Storage
from canopy.running.local_health import serve


def prepare_viewer(workspace):
    workspace=Path(workspace).resolve()
    if not (workspace/'request.json').is_file():raise ValueError('First prepare an isolated private workspace with prepare_healthy_route.py')
    # Shared source files, not another renderer implementation.
    shutil.copytree(ROOT/'visualizer/src',workspace/'visualizer/src',dirs_exist_ok=True)
    return workspace


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',required=True);p.add_argument('--port',type=int,default=8774);p.add_argument('--open',action='store_true')
    a=p.parse_args();workspace=prepare_viewer(a.workspace)
    if a.open:
        import threading,webbrowser
        threading.Timer(1,lambda:webbrowser.open(f'http://127.0.0.1:{a.port}/')).start()
    serve(Storage.load(workspace),workspace/'request.json',a.port)
