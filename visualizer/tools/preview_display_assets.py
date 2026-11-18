#!/usr/bin/env python3
"""Build an isolated local display preview; never change or publish a snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from build_pages import ROOT, build, encode


def preview(snapshot, display, output):
    if any(output == source or source in output.parents for source in (snapshot, display)):
        raise ValueError('Preview output must be outside the source snapshot and display export')
    report = json.loads((display / 'provenance.json').read_text())
    scenario = report['scenario_id']
    locked = ROOT / 'scenario' / scenario / 'data/manifest.json'
    source = (snapshot / 'manifest.json').read_bytes()
    if (source != locked.read_bytes()
            or hashlib.sha256(source).hexdigest() != report['source_manifest_sha256']):
        raise ValueError('Display derivative does not match the pinned public snapshot')
    source_manifest = json.loads(source)
    scene_record = next(f for f in source_manifest['files'] if f['path'] == 'scene.json')
    scene_bytes = (snapshot / 'scene.json').read_bytes()
    if hashlib.sha256(scene_bytes).hexdigest() != scene_record['sha256']:
        raise ValueError('Source scene checksum mismatch')
    records = {f['path']: f for f in report['files']}
    names = ('buildings.glb.gz', 'ground.glb.gz', 'placements.json.gz')
    for name in names:
        data = (display / name).read_bytes()
        if len(data) != records[name]['bytes'] or hashlib.sha256(data).hexdigest() != records[name]['sha256']:
            raise ValueError(f'Display checksum mismatch: {name}')
    build(ROOT, output=output)
    routing_path = output / 'asset-sources.json'
    routing = json.loads(routing_path.read_text())
    scene_path = f'scenes/{scenario}/scene.json'
    scene = json.loads(scene_bytes)
    scene['display_assets'] = json.loads((display / 'scene-display.json').read_text())
    target = output / scene_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encode(scene))
    routing['resources'][scene_path] = scene_path
    for name in names:
        physical = f'display/{scenario}/{name}'
        target = output / physical
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(display / name, target)
        routing['resources'][f'scenes/{scenario}/display/{name}'] = physical
    routing_path.write_bytes(encode(routing))
    # The source publication and its offline inventory stay immutable. This
    # isolated preview intentionally supports online review only.
    (output / 'preload.js').write_text((output / 'preload.js').read_text().replace(
        "params.get('download')!=='all'", 'true'))
    (output / 'display-preview.json').write_bytes(encode({
        'kind': 'canopy.local-display-preview', 'scenario_id': scenario,
        'source_manifest_sha256': report['source_manifest_sha256'],
        'display_files': [records[name] for name in names],
        'publication': 'Local online preview only; not a publishable snapshot or offline package.'}))
    print(f'Preview: {output}')
    print(f'Open /canopy/viewer/3d/?scene={scenario}&lite=0&play=0')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--display', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    preview(args.snapshot.resolve(), args.display.resolve(), args.output.resolve())
