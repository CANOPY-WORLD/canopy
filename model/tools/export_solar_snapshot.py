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

def compact_frame(raw, kind, shape):
    """Web-only encoding: bounded irradiance quantization or exact binary packing."""
    a = np.frombuffer(raw, dtype='<f2' if kind == 'ghi' else 'u1').reshape(shape)
    if kind == 'ghi':
        if not np.isfinite(a).all() or a.min() < 0 or a.max() > 950:
            raise ValueError('Irradiance outside declared 0–950 W/m2 quantization range')
        scale = 950 / 254
        codes = np.rint(a.astype('f4') / scale).astype('u1')
        error = codes.astype('f4') * scale - a
        return codes, dict(max_error_w_m2=float(np.abs(error).max()),
                          squared_error=float(np.sum(error.astype('f8')**2)), samples=a.size)
    if kind != 'shadow' or not np.isin(a, [0, 1]).all():
        raise ValueError('Expected binary shadow values')
    packed = np.packbits(a, axis=1, bitorder='big')
    if not np.array_equal(np.unpackbits(packed, axis=1, count=shape[1], bitorder='big'), a):
        raise ValueError('Shadow packing changed values')
    return packed, dict(lossless=True)


def export(run, source, output, compact=False):
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
    compression = dict(mode='quantized-irradiance-packed-shadow' if compact else 'float16-irradiance-byte-shadow', max_error_w_m2=0, squared_error=0, samples=0)
    for kind,key in [('ghi',f'solar_{tag}.npy'),('shadow',f'shadow_{tag}.npy')]:
        record=copy.deepcopy(transport[kind])
        source_shape=record['meta']['shape'][1:]
        if compact:
            shape = [len(frames), *source_shape] if kind == 'ghi' else [len(frames), source_shape[0], (source_shape[1]+7)//8]
            record['meta'].update(descr='|u1', shape=shape, itemsize=1, block=int(np.prod(shape[1:])))
            if kind == 'ghi':record['meta']['quantization']=dict(scale=950/254,offset=0)
            record['total_bytes']=len(frames)*record['meta']['block']
        for i,part in enumerate(record['parts']):
            sourcepart=run/'web'/part['file'];part['file']='chunks/solar_day/'+part['file'];target=output/'physics'/part['file'];target.parent.mkdir(parents=True,exist_ok=True)
            if compact:
                encoded, stats = compact_frame(gzip.decompress(sourcepart.read_bytes()),kind,source_shape)
                target.write_bytes(gzip.compress(encoded.tobytes(),compresslevel=6,mtime=0))
                part.update(offset=i*encoded.nbytes,bytes=encoded.nbytes)
                if kind == 'ghi':
                    compression['max_error_w_m2']=max(compression['max_error_w_m2'],stats['max_error_w_m2'])
                    compression['squared_error']+=stats['squared_error'];compression['samples']+=stats['samples']
            else:shutil.copy2(sourcepart,target)
        scene['protocol_display']['npy_transport'][key]=record
        physics['arrays'][key]=dict(shape=record['meta']['shape'],dtype=record['meta']['descr'],axes='TYX',unit='W/m2' if kind=='ghi' else '1',cell_m=8,time_s=times,time_local=[f['local'][11:19] for f in frames],epoch=frames[0]['utc'],timezone=cfg['timezone'],altitude_deg=[f['altitude_deg'] for f in frames],azimuth_deg=[f['azimuth_deg'] for f in frames],display_aggregation='Mean of valid 2x2 non-building ground cells' if kind=='ghi' else 'Majority of valid 2x2 non-building ground cells; ties shadowed')
        if compact:
            physics['arrays'][key]['web_encoding'] = dict(quantization=record['meta']['quantization']) if kind=='ghi' else dict(packing='numpy.packbits',axis='X',bitorder='big',unpacked_shape=[len(frames),*source_shape])
        scene['preview_fields_8m'][key]=dict(frames=len(frames),cell_m=8,method=physics['arrays'][key]['display_aggregation'],source_run=run.name,source_inventory_sha256=sha(run/'inventory.json'))
    invalid=np.load(run/'web/invalid.npy');maskfile='chunks/solar_day/invalid.bin.gz';(output/'physics'/maskfile).write_bytes(gzip.compress(invalid.tobytes(),mtime=0))
    for name in ['solar','shadow']:
        scene['protocol_display']['npy_transport'][f'masks/{name}_invalid.npy']=dict(meta=dict(descr='|u1',shape=[1,*invalid.shape],itemsize=1,offset=0,block=invalid.size),total_bytes=invalid.size,parts=[dict(file=maskfile,offset=0,bytes=invalid.size)])
    L=scene['layers']['solar'];L.update(shadow_packed=compact,quantitative=True,palette='warm',file=f'solar_{tag}.npy',frames=len(frames),t0_s=0,step_s=step,overlay_frame=int(np.argmax([f['altitude_deg'] for f in frames])),shadow_only=False,dates={tag:dict(label='21 June · full day · 100 samples · BST · clear sky',ghi=f'solar_{tag}.npy',shadow=f'shadow_{tag}.npy')},label='Sunlight · clear-sky irradiance · 8 m',title='Sunlight · clear-sky irradiance · 8 m',ghi_rate=4,shadow_rate=4,rate=4)
    write(output/'scene.json',scene);write(output/'physics/manifest.json',physics)
    if compact:
        compression['rmse_w_m2']=(compression.pop('squared_error')/compression.pop('samples'))**.5
        compression.update(error_reference='retained float16 8 m display samples, including masked and night zeros', shadow_lossless=True, temporal_subsampling=False, spatial_resampling=False, native_results_unchanged=True)
    public_cfg={**cfg,'web_compression':compression,'source_run':run.name,'source_inventory_sha256':sha(run/'inventory.json')}
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
    p.add_argument('--compact',action='store_true',help='Quantize irradiance to 0–950 / 254 W/m2; losslessly bit-pack shadows')
    a=p.parse_args();export(a.run,a.source,a.output,a.compact)
