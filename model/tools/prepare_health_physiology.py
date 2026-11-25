"""Import an explicit physiology profile as an immutable local input Asset."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
from canopy._io import read, write, digest
from canopy.assets.store import import_run
from common.storage import Storage
from healthy_route.conditional_runtime import read_profile
from healthy_route.inference import load_model


def prepare(workspace, profile_path):
    workspace, profile_path = Path(workspace).resolve(), Path(profile_path).resolve()
    storage = Storage.load(workspace)
    scene = 'imperial_corridor_8km'
    rid = 'health_physiology_' + digest(profile_path)[:16]
    stage = workspace / 'cache' / rid
    stage.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(profile_path, stage / 'physiology.json')
    profile = read_profile(stage)
    _, _, _, weights = load_model()
    write(stage / 'model-identity.json', weights)
    write(stage / 'input.json', {'labels':['physiology_profile'], 'values':[1]})
    manifest = dict(schema_version='1.1.0', scene_id=scene, simulation='healthy_route',
        run_id=rid, status='complete', created_at=datetime.now(timezone.utc).isoformat(),
        spatial=read(workspace/'scenario'/scene/'scenario.json')['spatial'],
        time={'unit':'s','samples':[]},
        provenance={'code_revision':'sha256:'+digest(Path(__file__)), 'dirty':False,
            'parameters':{'purpose':'Explicit '+profile['input_kind']+' conditional inference input; not observed city physiology'},
            'inputs':[{'id':'profile','sha256':digest(profile_path)}]},
        layers=[{'id':'input','kind':'time_series','format':'json','asset':'input.json','sampling':'static',
            'field':{'name':'physiology_profile','unit':'1'},'display':{'widget':'time_series','capabilities':[]}}],
        artifacts=[{'id':ident,'asset':name,'sha256':digest(stage/name),'media_type':'application/json'}
            for ident,name in [('physiology_inputs','physiology.json'),('model_identity','model-identity.json')]])
    write(stage/'manifest.json',manifest)
    return import_run(storage,scene,stage,expected_kind='physics')[0]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',required=True,type=Path)
    parser.add_argument('--profile',required=True,type=Path)
    args=parser.parse_args()
    print(prepare(args.workspace,args.profile))
