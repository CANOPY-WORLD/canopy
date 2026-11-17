#!/usr/bin/env python3
"""Copy selected real Physics4D scene assets into Canopy without altering the source.

python tools/migrate_physics4d.py --source /path/to/physics4d --scene south_ken --scene white_city
The default selection is existing GLB geometry, one recorded wind run and temperature when available.
No simulation is rerun, no data is synthesized, and nothing is published.
"""
import argparse
from pathlib import Path
import shutil
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common.storage import Storage
from common.contract import validate,asset_references
from canopy._io import read,write,digest
from canopy.scenario.store import create,load
from canopy.assets.store import import_run
from canopy.visualization.profile import select


def migrate(source,destination,scene):
    old=read(source.metadata(scene)/'project.json')
    if not (destination.metadata(scene)/'scenario.json').exists():create(destination,scene,old['title'],old['spatial'])
    choices=[('legacy_web','geometry')]
    for category in ['wind','temperature']:
        paths=sorted(source.assets(scene,'runs').glob(f'city_{category}_*/manifest.json'))
        if paths:choices.append((paths[0].parent.name,None))
    imported=[];records=[]
    destination.cache_root.mkdir(parents=True,exist_ok=True)
    for rid,layer_id in choices:
        src=source.run(scene,rid);original=read(src/'manifest.json')
        m=read(src/'manifest.json')
        if layer_id:
            m['run_id']=rid+'_geometry';m['layers']=[l for l in m['layers'] if l['id']==layer_id];m['time']={'unit':'s','samples':[]}
        known=load(destination,scene)['assets']
        existing=[ref for ref in known if ref.startswith(m['run_id']+'_')]
        if existing:
            imported.extend(existing);continue
        with tempfile.TemporaryDirectory(dir=destination.cache_root,prefix='migration-') as tmp:
            stage=Path(tmp)
            paths=set().union(*(asset_references(l) for l in m['layers']))|{a['asset'] for a in m.get('artifacts',[])}
            from canopy._io import relative
            for rel in paths:
                target=relative(stage,rel);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(relative(src,rel),target)
            shutil.copy2(src/'manifest.json',stage/'original-manifest.json')
            m.setdefault('artifacts',[]).append({'id':'original_manifest','asset':'original-manifest.json','sha256':digest(stage/'original-manifest.json'),'media_type':'application/json'})
            write(stage/'manifest.json',m);validate(stage/'manifest.json')
            refs=import_run(destination,scene,stage);imported.extend(refs)
            records.append({'source_run':rid,'source_manifest_sha256':digest(src/'manifest.json'),'assets':refs,'selection':layer_id or 'all layers','geometry_dependency':'not inferred for historical results'})
    select(destination,scene,imported,'city')
    report={'scenario':scene,'copied':records,'selected_assets':imported,'source_untouched':True}
    write(destination.metadata(scene)/'migration.json',report)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True,type=Path);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--scene',action='append',required=True)
    args=p.parse_args();source=Storage.load(args.source);destination=Storage.load(args.root)
    import json
    for scene in args.scene:print(json.dumps(migrate(source,destination,scene),indent=2))
