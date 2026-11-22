#!/usr/bin/env python3
"""Export a completed solar-day experiment as a V1.1 scientific payload.

This does not register or publish; import-run separately registers validated outputs.
The surface fields use local-ground height zero; original ODN geometry is provenance.
"""
import argparse
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import shutil
import sys
import tarfile
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from urban_flow.physics.solar.day import digest


def export(source, output, scenario):
    inventory=json.loads((source/'inventory.json').read_text())
    if inventory.get('status')!='complete':raise ValueError('Incomplete run')
    for f in inventory['files']:
        if digest(source/f['path'])!=f['sha256']:raise ValueError('Source hash mismatch: '+f['path'])
    config=json.loads((source/'provenance/request.json').read_text())
    frames=json.loads((source/'frames.json').read_text())
    transport=json.loads((source/'web/transport.json').read_text())
    spatial=json.loads(scenario.read_text())['spatial']
    if [spatial['origin']['longitude'],spatial['origin']['latitude']]!=config['origin_lon_lat']:
        raise ValueError('Geographic origins differ')
    output.mkdir(parents=True,exist_ok=False)
    shutil.copytree(source/'provenance',output/'provenance')
    for name in ['frames.json','validation.json','inventory.json']:
        shutil.copy2(source/name,output/'provenance'/name)
    shutil.copy2(source/'web/invalid.npy',output/'invalid.npy')
    shape=transport['ghi']['meta']['shape']
    np.save(output/'height.npy',np.zeros(shape[1:],dtype='<f4'))
    layers=[]
    for name,unit in [('ghi','W/m2'),('shadow','1')]:
        record=transport[name];source_dtype=record['meta']['descr'];dtype='<f2';paths=[]
        (output/name).mkdir()
        for i,part in enumerate(record['parts']):
            arr=np.frombuffer(gzip.decompress((source/'web'/part['file']).read_bytes()),dtype=source_dtype).reshape(shape[1:]).astype(dtype)
            path=f'{name}/{i:03d}.npy';np.save(output/path,arr[None]);paths.append(path)
        (output/f'{name}_frames.json').write_text(json.dumps(dict(frames=paths))+'\n')
        layers.append(dict(id='irradiance' if name=='ghi' else name,kind='scalar_field',format='npy_frames',asset=f'{name}_frames.json',sampling='step',
            encoding=dict(coordinate_frame='ENU',dtype=dtype,shape=shape,axes='TYX',origin_m=[*config['origin_xy_m'],0],spacing_m=[config['cell_m']*2]*2,sample_location='cell_center',byte_order='little',compression='none',frame_assets=paths,height_asset='height.npy',height_dtype='<f4',mask_asset='invalid.npy',mask_dtype='|u1',mask_semantics='invalid_nonzero'),
            field=dict(name='global_horizontal_irradiance' if name=='ghi' else 'direct_beam_shadow',unit=unit),display=dict(widget='scalar_field',capabilities=['legend','opacity','pick'])))
    with tarfile.open(output/'provenance/source_snapshot.tar.gz','w:gz') as archive:
        for name in ['day.py','model.py']:archive.add(source/'provenance'/name,arcname='urban_flow/physics/solar/'+name)
    artifacts=[dict(id='source_snapshot' if p.name=='source_snapshot.tar.gz' else 'provenance_'+str(i),asset=p.relative_to(output).as_posix(),sha256=digest(p),media_type='application/octet-stream') for i,p in enumerate(sorted((output/'provenance').rglob('*'))) if p.is_file()]
    manifest=dict(schema_version='1.1.0',scene_id='imperial_corridor_8km',simulation='solar',run_id=source.name,status='complete',created_at=datetime.now(timezone.utc).isoformat(),
        spatial=spatial,time=dict(unit='s',epoch=frames[0]['utc'],samples=[f['seconds'] for f in frames]),layers=layers,artifacts=artifacts,
        provenance=dict(code_revision='sha256:'+digest(source/'provenance/day.py'),dirty=True,parameters={**config,'display_surface':'local-ground horizontal surface at height zero; source ODN bed used only for ray occlusion'},inputs=[dict(id=f['name'],sha256=f['sha256']) for f in config['inputs']]))
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--scenario',type=Path,required=True)
    a=p.parse_args();export(a.source,a.output,a.scenario)
