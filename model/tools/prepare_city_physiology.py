"""Run conditional city physiology locally from explicit retained dependencies."""
import argparse
from pathlib import Path
from canopy._io import read,write
from canopy.running.runner import run
from common.storage import Storage


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--exposure',required=True);p.add_argument('--city',required=True);p.add_argument('--physiology',required=True)
    p.add_argument('--profile',type=Path,required=True)
    a=p.parse_args()
    request=dict(schema_version='2.0.0',scenario_id='imperial_corridor_8km',model_id='healthy_route',method_id='city_breathing',method_version='1.0.0',
        inputs={'exposure':a.exposure,'city':a.city,'physiology':a.physiology},parameters=read(a.profile),execution={'device':'cpu','threads':2})
    write(a.workspace/'city-physiology-request.json',request)
    state=run(Storage.load(a.workspace),request,retain=True)
    write(a.workspace/'city-physiology-preview.json',{'result':state['assets'][0]})
    print(state['assets'][0]);print(state['diagnostics'])
