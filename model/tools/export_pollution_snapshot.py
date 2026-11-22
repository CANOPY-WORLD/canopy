#!/usr/bin/env python3
"""Export recorded ENU pollution slices into an immutable city presentation delta.

No rerun, spatial resampling, time interpolation or scientific-volume upload.
Log-quantized presentation slices and the exact invalid mask use per-frame gzip.
The native float32 result is preserved; encoding errors are recorded.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def export(run, source, output, encoding="log8"):
    manifest = json.loads((run / 'manifest.json').read_text())
    layer, = manifest['layers']
    enc = layer['encoding']
    if manifest['status'] != 'complete' or enc['coordinate_frame'] != 'ENU' or enc['axes'] != 'TYX':
        raise ValueError('Expected a completed ENU TYX result')
    if enc['spacing_m'][0] != enc['spacing_m'][1]:
        raise ValueError('The city adapter requires square cells')
    times = manifest['time']['samples']
    n, rows, cols = enc['shape']
    if n != len(times) or n != len(enc['frame_assets']):
        raise ValueError('Frame count mismatch')
    if encoding not in ('log8', 'float16'):
        raise ValueError('Unsupported presentation encoding')
    peak = max(float(np.load(run / name).max()) for name in enc['frame_assets'])
    reference = 1e-6
    quantization = dict(transform='log1p', scale=float(np.log1p(peak / reference) / 254) if peak > 0 else 1.0, offset=0, reference=reference, invalid_code=255) if encoding == 'log8' else None
    old = json.loads((source / 'manifest.json').read_text())
    scene = json.loads((source / 'scene.json').read_text())
    output.mkdir(parents=True, exist_ok=False)
    transport = scene['protocol_display']['npy_transport']
    records = []
    removed = []
    for record in old['files']:
        path = record['path']
        if path in ('scene.json', 'derivation.json', 'physics/manifest.json') or (path.startswith('physics/') and ('poll' in path)):
            removed.append(path)
        else:
            records.append({**record, 'source_snapshot': record.get('source_snapshot', old['snapshot'])})
    for key in list(transport):
        if 'poll' in key:
            del transport[key]
    inputs = []
    errors = dict(max_abs_ug_m3=0.0, squared_error=0.0, samples=0, max_relative_visible=0.0)
    def encode(key, arrays, dtype):
        parts = []
        block = rows * cols
        itemsize = np.dtype(dtype).itemsize
        count = 0
        for i, (path, array) in enumerate(arrays):
            if array.size != block or not np.isfinite(array).all():
                raise ValueError('Invalid recorded frame')
            is_field = key == 'poll.npy'
            if is_field and np.any(array < 0):
                raise ValueError('Negative concentration')
            if is_field and quantization:
                encoded = np.rint(np.log1p(array.astype('f8') / reference) / quantization['scale']).astype('u1')
                decoded = reference * np.expm1(encoded.astype('f8') * quantization['scale'])
            else:
                encoded = np.ascontiguousarray(array, dtype=dtype)
                decoded = encoded.astype('f8')
            if not np.isfinite(encoded).all():
                raise ValueError('Float16 overflow')
            if is_field:
                error = decoded - array.reshape(encoded.shape)
                visible = array >= 0.00023500917
                if visible.any():
                    errors['max_relative_visible'] = max(errors['max_relative_visible'], float(np.max(np.abs(error[visible]) / array[visible])))
                errors['max_abs_ug_m3'] = max(errors['max_abs_ug_m3'], float(np.abs(error).max()))
                errors['squared_error'] += float(np.sum(error * error))
                errors['samples'] += error.size
            raw = encoded.tobytes()
            name = f'chunks/traffic_pmx/{Path(key).stem}_{i:03d}.bin.gz'
            target = output / 'physics' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(gzip.compress(raw, compresslevel=6, mtime=0))
            if gzip.decompress(target.read_bytes()) != raw:
                raise ValueError('Transport roundtrip failed')
            parts.append(dict(file=name, offset=i*len(raw), bytes=len(raw)))
            inputs.append(dict(path=path.name, sha256=digest(path)))
            count += 1
        transport[key] = dict(meta=dict(descr=np.dtype(dtype).str, shape=[count, rows, cols], itemsize=itemsize, offset=0, block=block), total_bytes=count*block*itemsize, parts=parts)
    field_dtype = '|u1' if quantization else '<f2'
    encode('poll.npy', ((run / name, np.load(run / name)) for name in enc['frame_assets']), field_dtype)
    if quantization:
        transport['poll.npy']['meta']['quantization'] = quantization
    mask = run / enc['mask_asset']
    encode('masks/poll_invalid.npy', [(mask, np.load(mask))], '|u1')
    cell = enc['spacing_m'][0]
    origin = enc['origin_m']
    scene['layers']['poll'] = dict(file='poll.npy', cell_m=cell, cols=cols, rows=rows,
        offset_x_m=origin[0]-scene['grid']['x0'], offset_z_m=-origin[1]-scene['grid']['z_south'],
        frames=n, own_clock=True, t0_s=times[0], step_s=times[1]-times[0], time_s=times,
        overlay_frame=n-1, y=origin[2], rate=5, preload_sequence=True,
        title='Traffic exhaust PMx increment', label='Traffic exhaust PMx increment · 8 m',
        unit_label='PMx increment · µg/m³', range=[0.00023500917, 2.3500917], quantitative=True, palette='warm')
    scene['preview_fields_8m']['poll.npy'] = dict(frames=n, cell_m=cell, source_run=manifest['run_id'], method=encoding + ' gzip; original ENU cell centres and recorded samples')
    errors['rmse_ug_m3'] = (errors.pop('squared_error') / errors.pop('samples')) ** 0.5
    provenance = dict(source_run=manifest['run_id'], source_manifest_sha256=digest(run/'manifest.json'), source_frames=inputs,
        field=layer['field'], encoding=enc, time=manifest['time'], provenance=manifest['provenance'],
        presentation=dict(compression=encoding + ' gzip', quantization=quantization, errors=errors, spatial_resampling=False, temporal_resampling=False, slice='0–8 m voxel mean centred at 4 m; not pedestrian breathing height'))
    diagnostics = run / 'provenance/diagnostics.json'
    if diagnostics.is_file():
        provenance['diagnostics'] = json.loads(diagnostics.read_text())
    write(output/'physics/traffic-pmx-provenance.json', provenance)
    physics_record = next(r for r in old['files'] if r['path'] == 'physics/manifest.json')
    physics_base = source.parent / physics_record.get('source_snapshot', source.name)
    physics = json.loads((physics_base / 'physics/manifest.json').read_text())
    physics['arrays']['poll.npy'] = dict(shape=[n, rows, cols], dtype=field_dtype, quantization=quantization, axes='TYX', unit='ug/m3', cell_m=cell, time_s=times, origin_m=origin, field=layer['field']['name'], presentation_errors=errors)
    write(output/'physics/manifest.json', physics)
    write(output/'scene.json', scene)
    write(output/'derivation.json', dict(kind='traffic-wind-pollution-replacement', source_snapshot=old['snapshot'], source_manifest_sha256=digest(source/'manifest.json'), removed_from_selection=removed, source_run=manifest['run_id']))
    previous = {r['path']: r['viewer_path'] for r in old['files']}
    for path in sorted(output.rglob('*')):
        if path.is_file():
            name = path.relative_to(output).as_posix()
            records.append(dict(path=name, viewer_path=previous.get(name, 'scenes/imperial_corridor_8km/'+name), bytes=path.stat().st_size, sha256=digest(path)))
    result = {**old, 'schema_version':'1.1.0', 'snapshot':output.name, 'bytes':sum(r['bytes'] for r in records), 'files':sorted(records,key=lambda r:r['path']), 'derivation':dict(source_snapshot=old['snapshot'], pollution_run=manifest['run_id'])}
    write(output/'manifest.json', result)
    print(json.dumps(dict(files=len(records), logical_bytes=result['bytes'], new_bytes=sum(r['bytes'] for r in records if 'source_snapshot' not in r))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('run', 'source', 'output'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--encoding', choices=['log8', 'float16'], default='log8')
    args = parser.parse_args()
    export(args.run, args.source, args.output, args.encoding)
