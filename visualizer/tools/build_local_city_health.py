"""Build a local city comparison from verified, already downloaded city files.

This is not a Pages publication artifact. No private health inputs are copied.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from build_pages import build, ROOT


def local_build(city_data, output):
    city_data, output = city_data.resolve(), output.resolve()
    manifest = json.loads((ROOT / 'scenario/imperial_corridor_8km/data/manifest.json').read_bytes())
    # Check the complete selected snapshot before creating the new build.
    for item in manifest['files']:
        source = (city_data / item['viewer_path']).resolve()
        if not source.is_relative_to(city_data):
            raise ValueError('City resource escapes the selected directory')
        data = source.read_bytes()
        if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('City input checksum mismatch: ' + item['viewer_path'])
    build(ROOT, output, refresh=True)
    shutil.copyfile(ROOT / 'scenario/imperial_corridor_8km/experiments/healthy_route_current_city/display.json',
                    output / 'local-health-presentation.json')
    routes = {}
    for item in manifest['files']:
        name = item['viewer_path']
        target = output / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(city_data / name, target)
        routes[name] = name
    for name in ['healthy-route', 'shared']:
        shutil.copytree(ROOT / 'visualizer/src/visualization' / name,
                        output / 'src/visualization' / name, dirs_exist_ok=True)
    original = json.loads((output / 'asset-sources.json').read_bytes())
    routes.update({k:v for k,v in original['resources'].items() if k not in routes and not v.startswith('https:')})
    (output / 'asset-sources.json').write_text(json.dumps({'schema_version':'2.0.0', 'remote_bases':[], 'resources':routes}, indent=2), encoding='utf-8')
    indexes = {'download-manifest.json', 'download-manifests/imperial_corridor_8km.json'}
    files = []
    for path in sorted(output.rglob('*')):
        if path.is_file() and path.suffix != '.mp4' and path.relative_to(output).as_posix() not in indexes:
            data = path.read_bytes()
            files.append({'path':path.relative_to(output).as_posix(), 'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest()})
    version = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:20]
    inventory = {'version':version, 'scenario_id':'imperial_corridor_8km', 'bytes':sum(f['bytes'] for f in files), 'files':files}
    for name in indexes:
        (output / name).write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    return {'verified_city_files':len(manifest['files']), 'city_bytes':manifest['bytes'], 'frontend_revision':'local working tree', 'output':str(output)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--city-data', required=True, type=Path, help='Verified public resources, addressed by viewer_path')
    parser.add_argument('--output', required=True, type=Path, help='New empty output location under cache')
    args = parser.parse_args()
    print(json.dumps(local_build(args.city_data, args.output), indent=2))
