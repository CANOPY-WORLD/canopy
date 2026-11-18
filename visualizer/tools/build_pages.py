#!/usr/bin/env python3
"""Verify Scenario-owned public data and build one self-contained Pages artifact."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()


def bounded(base, name):
    if (not isinstance(name, str) or not name or name.startswith('/') or
            any(c in name for c in '\\%?#:') or
            any(p in ('', '.', '..') for p in name.split('/'))):
        raise ValueError(f'Invalid publication path: {name!r}')
    path = base / name
    if not path.resolve().is_relative_to(base.resolve()) or path.is_symlink():
        raise ValueError(f'Publication path escapes its root: {name}')
    return path


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def publications(root):
    """Return only explicitly declared, checksum-verified public resources."""
    resources, manifests = {}, {}
    for manifest_path in sorted((root / 'scenario').glob('*/data/manifest.json')):
        data_root = manifest_path.parent
        scenario = data_root.parent.name
        manifest = json.loads(manifest_path.read_bytes())
        if (manifest.get('schema_version') != '1.0.0' or
                manifest.get('kind') != 'canopy.publication' or
                manifest.get('scenario_id') != scenario or
                not (data_root.parent / 'scenario.json').is_file()):
            raise ValueError(f'Invalid public Scenario manifest: {manifest_path}')
        declared, total = set(), 0
        for record in manifest['files']:
            name, viewer_path = record['path'], record['viewer_path']
            path = bounded(data_root, name)
            bounded(root, viewer_path)
            if not viewer_path.startswith((f'scenes/{scenario}/', 'assets/', 'tiles/', 'agents/')):
                raise ValueError(f'Invalid presentation resource: {viewer_path}')
            if name in declared or viewer_path in resources:
                raise ValueError(f'Duplicate public resource: {viewer_path}')
            if (not path.is_file() or path.stat().st_size != record['bytes'] or
                    not re.fullmatch('[0-9a-f]{64}', record['sha256']) or
                    checksum(path) != record['sha256']):
                raise ValueError(f'Public resource checksum/size mismatch: {path}')
            if record['bytes'] >= 100 * 1024 ** 2:
                raise ValueError(f'Public resource exceeds ordinary Git file limit: {path}')
            declared.add(name)
            total += record['bytes']
            resources[viewer_path] = {'source': path, 'path': path.relative_to(root).as_posix(),
                                      'bytes': record['bytes'], 'sha256': record['sha256']}
        actual = {p.relative_to(data_root).as_posix() for p in data_root.rglob('*') if p.is_file()}
        if actual != declared | {'manifest.json'} or total != manifest['bytes']:
            raise ValueError(f'Unlisted public files or incorrect total: {data_root}')
        manifests[manifest_path.relative_to(root).as_posix()] = manifest_path
    if not resources:
        raise ValueError('No public Scenario data found')
    return resources, manifests


def frontend(root):
    site = root / 'visualizer/site'
    files = {}
    for folder in ('viewer', 'vendor', 'agents'):
        for path in sorted((site / folder).rglob('*')):
            # The worker serves logical GLB requests from the packed representation.
            if path.suffix == '.glb' and path.with_suffix('.glb.gz').is_file():
                continue
            if path.is_file() and path.suffix != '.md' and not any(p.startswith('.') for p in path.relative_to(site).parts):
                name = path.relative_to(site).as_posix()
                files[name] = bounded(site, name).read_bytes()
    for name in ('index.html', 'preload.js', 'asset-router.js', 'scenes/index.json'):
        files[name] = (site / name).read_bytes()
    files['src/visualization/public-scenes.json'] = (root / 'visualizer/src/visualization/public-scenes.json').read_bytes()
    for name in ('index.html', 'style.css', 'app.js', 'inventory.json', 'architecture.svg'):
        files['guide/' + name] = (root / 'visualizer/guide' / name).read_bytes()
    return files


def generated(root):
    resources, manifests = publications(root)
    files = frontend(root)
    if resources.keys() & files.keys():
        raise ValueError('A public resource collides with a frontend file')
    routes = {name: record['path'] for name, record in resources.items()}
    routes.update({name: name for name in files if name.endswith('.glb.gz')})
    routing = encode({'schema_version': '1.0.0', 'resources': dict(sorted(routes.items()))})
    files['asset-sources.json'] = routing
    for name, path in manifests.items():
        files[name] = path.read_bytes()
    inventory = [{'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                 for name, data in files.items()]
    inventory.extend({'path': name, 'bytes': record['bytes'], 'sha256': record['sha256']}
                     for name, record in resources.items())
    inventory.sort(key=lambda f: f['path'])
    version = hashlib.sha256(encode(inventory)).hexdigest()[:20]
    download = encode({'version': version, 'bytes': sum(f['bytes'] for f in inventory), 'files': inventory})
    return resources, files, routing, download


def build(root, output=None, refresh=False):
    resources, files, routing, download = generated(root)
    for name, data in [('asset-sources.json', routing), ('download-manifest.json', download)]:
        target = root / 'visualizer/site' / name
        if refresh:
            target.write_bytes(data)
        elif not target.is_file() or target.read_bytes() != data:
            raise ValueError(f'Stale {name}; run build_pages.py --refresh')
    files['download-manifest.json'] = download
    files['.nojekyll'] = b''
    size = sum(len(data) for data in files.values()) + sum(r['bytes'] for r in resources.values())
    if size > 950_000_000:
        raise ValueError(f'Pages artifact exceeds the 950 MB publication budget: {size}')
    if output:
        output = output.resolve()
        if output.exists():
            raise ValueError('Choose a new output directory; existing builds are never overwritten')
        for name, data in files.items():
            target = bounded(output, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        for record in resources.values():
            target = bounded(output, record['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(record['source'], target)
    return {'public_files': len(resources), 'frontend_files': len(files), 'bytes': size}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New static artifact directory, usually under cache/')
    parser.add_argument('--refresh', action='store_true', help='Regenerate the tracked routing and download indexes')
    args = parser.parse_args()
    print(json.dumps(build(ROOT, args.output, args.refresh), indent=2))
