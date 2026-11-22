#!/usr/bin/env python3
"""Create an immutable solar-only publication delta; reuse unchanged snapshot bytes."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np


def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')

def export(run, source, output):
    inv=json.loads((run/'inventory.json').read_text())
    if inv.get('status')!='complete':raise ValueError('Incomplete solar run')
    for f in inv['files']:
        if sha(run/f['path'])!=f['sha256']:raise ValueError('Run checksum mismatch')
    old=json.loads((source/'manifest.json').read_text());scene=json.loads((source/'scene.json').read_text());physics=json.loads((source/'physics/manifest.json').read_text())
    frames=json.loads((run/'frames.json').read_text());cfg=json.loads((run/'provenance/request.json').read_text());transport=json.loads((run/'web/transport.json').read_text())
    output.mkdir(parents=True,exist_ok=False)
    records=[];removed=[]
    def solar_path(name):return ('solar' in name or 'shadow' in name) and name.startswith('physics/')
    replaced={'scene.json','physics/manifest.json','derivation.json'}
    for r in old['files']:
        if solar_path(r['path']) or r['path'] in replaced:removed.append(r['path']);continue
        records.append({**r,'source_snapshot':r.get('source_snapshot',old['snapshot'])})
    for key in list(scene['protocol_display']['npy_transport']):
        if 'solar' in key or 'shadow' in key:del scene['protocol_display']['npy_transport'][key]
    for mapping in [physics['arrays'],scene['preview_fields_8m']]:
        for key in list(mapping):
            if 'solar' in key or 'shadow' in key:del mapping[key]
    tag=cfg['day'].replace('-','');times=[f['seconds'] for f in frames];step=times[1]-times[0]
    for kind,key in [('ghi',f'solar_{tag}.npy'),('shadow',f'shadow_{tag}.npy')]:
        record=copy.deepcopy(transport[kind])
        for part in record['parts']:
            sourcepart=run/'web'/part['file'];part['file']='chunks/solar_day/'+part['file'];target=output/'physics'/part['file'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(sourcepart,target)
        scene['protocol_display']['npy_transport'][key]=record
        physics['arrays'][key]=dict(shape=record['meta']['shape'],dtype=record['meta']['descr'],axes='TYX',unit='W/m2' if kind=='ghi' else '1',cell_m=8,time_s=times,time_local=[f['local'][11:19] for f in frames],epoch=frames[0]['utc'],timezone=cfg['timezone'],altitude_deg=[f['altitude_deg'] for f in frames],azimuth_deg=[f['azimuth_deg'] for f in frames],display_aggregation='Mean of valid 2x2 non-building ground cells' if kind=='ghi' else 'Majority of valid 2x2 non-building ground cells; ties shadowed')
        scene['preview_fields_8m'][key]=dict(frames=len(frames),cell_m=8,method=physics['arrays'][key]['display_aggregation'],source_run=run.name,source_inventory_sha256=sha(run/'inventory.json'))
    invalid=np.load(run/'web/invalid.npy');maskfile='chunks/solar_day/invalid.bin.gz';(output/'physics'/maskfile).write_bytes(gzip.compress(invalid.tobytes(),mtime=0))
    for name in ['solar','shadow']:
        scene['protocol_display']['npy_transport'][f'masks/{name}_invalid.npy']=dict(meta=dict(descr='|u1',shape=[1,*invalid.shape],itemsize=1,offset=0,block=invalid.size),total_bytes=invalid.size,parts=[dict(file=maskfile,offset=0,bytes=invalid.size)])
    L=scene['layers']['solar'];L.update(quantitative=True,palette='warm',file=f'solar_{tag}.npy',frames=len(frames),t0_s=0,step_s=step,overlay_frame=int(np.argmax([f['altitude_deg'] for f in frames])),shadow_only=False,dates={tag:dict(label='21 June · full day · 100 samples · BST · clear sky',ghi=f'solar_{tag}.npy',shadow=f'shadow_{tag}.npy')},label='Sunlight · clear-sky irradiance · 8 m',title='Sunlight · clear-sky irradiance · 8 m',ghi_rate=4,shadow_rate=4,rate=4)
    write(output/'scene.json',scene);write(output/'physics/manifest.json',physics)
    public_cfg={**cfg,'source_run':run.name,'source_inventory_sha256':sha(run/'inventory.json')}
    write(output/'physics/solar-day-provenance.json',public_cfg)
    shutil.copy2(run/'frames.json',output/'physics/solar-day-frames.json');shutil.copy2(run/'validation.json',output/'physics/solar-day-validation.json')
    write(output/'derivation.json',dict(kind='solar-day-replacement',source_snapshot=old['snapshot'],source_manifest_sha256=sha(source/'manifest.json'),removed_from_selection=removed,unchanged_files=len(records),solar=public_cfg))
    previous={r['path']:r['viewer_path'] for r in old['files']}
    for p in sorted(output.rglob('*')):
        if p.is_file():
            name=p.relative_to(output).as_posix();records.append(dict(path=name,viewer_path=previous.get(name,'scenes/imperial_corridor_8km/'+name),bytes=p.stat().st_size,sha256=sha(p)))
    manifest={**old,'schema_version':'1.1.0','snapshot':output.name,'bytes':sum(r['bytes'] for r in records),'files':sorted(records,key=lambda r:r['path']), 'derivation':dict(source_snapshot=old['snapshot'],solar_run=run.name)}
    write(output/'manifest.json',manifest)
    print(json.dumps(dict(snapshot=output.name,files=len(records),logical_bytes=manifest['bytes'],new_bytes=sum(r['bytes'] for r in records if 'source_snapshot' not in r))))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();export(a.run,a.source,a.output)
