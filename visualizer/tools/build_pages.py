#!/usr/bin/env python3
"""Build the shared Canopy website with pinned Scenario data references."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit

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


def https_url(value, directory=False):
    """Public deployment URLs cannot carry credentials, queries or traversal."""
    if not isinstance(value, str) or any(c in value for c in '\\%?#') or any(c.isspace() for c in value):
        raise ValueError('Invalid public HTTPS URL')
    url = urlsplit(value)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password or
            url.query or url.fragment or any(p in ('.', '..') for p in url.path.split('/')) or
            '//' in url.path or (directory and not url.path.endswith('/'))):
        raise ValueError('Invalid public HTTPS URL')
    return value


def publication_reference(scenario_root):
    path = scenario_root / 'publication.json'
    if not path.is_file():
        return None
    value = json.loads(path.read_bytes())
    manifest = scenario_root / 'data/manifest.json'
    if (value.get('schema_version') != '1.0.0' or
            value.get('kind') != 'canopy.publication-reference' or
            value.get('scenario_id') != scenario_root.name or
            not re.fullmatch('[0-9a-f]{40}', value.get('revision', '')) or
            value.get('manifest', {}).get('path') != 'data/manifest.json' or
            value['manifest'].get('sha256') != checksum(manifest) or
            not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9._-]*', value.get('snapshot', ''))):
        raise ValueError(f'Invalid publication reference or manifest checksum: {path}')
    https_url(value['repository'])
    https_url(value['website'], directory=True)
    https_url(value['base_url'], directory=True)
    if not value['base_url'].endswith('/snapshots/' + value['snapshot'] + '/'):
        raise ValueError('Public data URLs must select an immutable snapshot directory')
    return value


def publications(root):
    """Verify local bytes or a locked remote inventory; never bundle remote data."""
    resources, manifests = {}, {}
    for manifest_path in sorted((root / 'scenario').glob('*/data/manifest.json')):
        data_root = manifest_path.parent
        scenario = data_root.parent.name
        manifest = json.loads(manifest_path.read_bytes())
        reference = publication_reference(data_root.parent)
        if (manifest.get('schema_version') not in ('1.0.0', '1.1.0') or
                manifest.get('kind') != 'canopy.publication' or
                manifest.get('scenario_id') != scenario or
                not (data_root.parent / 'scenario.json').is_file()):
            raise ValueError(f'Invalid public Scenario manifest: {manifest_path}')
        if reference and reference['snapshot'] != manifest.get('snapshot'):
            raise ValueError('Publication reference and manifest snapshots disagree')
        declared, total = set(), 0
        for record in manifest['files']:
            name, viewer_path = record['path'], record['viewer_path']
            path = bounded(data_root, name)
            bounded(root, viewer_path)
            prefixes = (f'scenes/{scenario}/',)
            if scenario == 'imperial_corridor_8km':
                prefixes += ('assets/', 'tiles/', 'agents/')
            if not viewer_path.startswith(prefixes):
                raise ValueError(f'Invalid presentation resource: {viewer_path}')
            if name in declared or viewer_path in resources:
                raise ValueError(f'Duplicate public resource: {viewer_path}')
            if (type(record['bytes']) is not int or record['bytes'] < 0 or
                    not re.fullmatch('[0-9a-f]{64}', record['sha256'])):
                raise ValueError(f'Invalid public resource size/checksum: {path}')
            if not reference and (not path.is_file() or path.stat().st_size != record['bytes'] or
                                  checksum(path) != record['sha256']):
                raise ValueError(f'Public resource checksum/size mismatch: {path}')
            if record['bytes'] >= 100 * 1024 ** 2:
                raise ValueError(f'Public resource exceeds ordinary Git file limit: {path}')
            source_base = reference['base_url'] if reference else None
            if 'source_snapshot' in record:
                snapshot = record['source_snapshot']
                if (manifest['schema_version'] != '1.1.0' or not reference or
                        not isinstance(snapshot, str) or
                        not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9._-]*', snapshot) or
                        snapshot == manifest['snapshot']):
                    raise ValueError('Invalid immutable source snapshot')
                source_base = reference['base_url'].rsplit('/snapshots/', 1)[0] + '/snapshots/' + snapshot + '/'
            declared.add(name)
            total += record['bytes']
            resources[viewer_path] = {'source': None if reference else path,
                                      'scenario_id': scenario,
                                      'path': source_base + name if reference else path.relative_to(root).as_posix(),
                                      'bytes': record['bytes'], 'sha256': record['sha256'], 'remote_base': source_base}
        actual = {p.relative_to(data_root).as_posix() for p in data_root.rglob('*') if p.is_file()}
        expected = {'manifest.json'} if reference else declared | {'manifest.json'}
        if actual != expected or total != manifest['bytes']:
            raise ValueError(f'Unlisted public files or incorrect total: {data_root}')
        manifests[manifest_path.relative_to(root).as_posix()] = manifest_path
        if reference:
            source = data_root.parent / 'publication.json'
            manifests[source.relative_to(root).as_posix()] = source
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
    for name in ('scenario-tabs.mjs', 'scenario-tabs.css'):
        route = 'src/visualization/shared/' + name
        files[route] = (root / 'visualizer' / route).read_bytes()
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
    scenarios, remote_bases = [], []
    for scenario in sorted({r['scenario_id'] for r in resources.values()}):
        scenario_root = root / 'scenario' / scenario
        description = json.loads((scenario_root / 'scenario.json').read_bytes())
        manifest = json.loads((scenario_root / 'data/manifest.json').read_bytes())
        reference = publication_reference(scenario_root)
        entry = {'id': scenario, 'title': description.get('title', scenario),
                 'viewer_url': 'viewer/3d/?scene=' + scenario,
                 'download_manifest': 'download-manifests/' + scenario + '.json',
                 'snapshot': manifest.get('snapshot'), 'bytes': manifest['bytes'],
                 'files': len(manifest['files'])}
        if reference:
            remote_bases.append(reference['base_url'])
            remote_bases.extend(r['remote_base'] for r in resources.values() if r['scenario_id'] == scenario and r['remote_base'])
            entry.update(repository=reference['repository'], revision=reference['revision'],
                         data_website=reference['website'], manifest_url=reference['base_url'] + 'manifest.json',
                         manifest_sha256=reference['manifest']['sha256'])
        scenarios.append(entry)
    default = json.loads(files['scenes/index.json'])['default']
    if default not in {entry['id'] for entry in scenarios}:
        raise ValueError('Default Scenario has no publication')
    routing = encode({'schema_version': '2.0.0', 'remote_bases': sorted(set(remote_bases)),
                      'resources': dict(sorted(routes.items()))})
    files['asset-sources.json'] = routing
    # A changed data pin must install a fresh router even when worker logic is unchanged.
    files['asset-router.js'] += ('\n// Publication routing: ' + hashlib.sha256(routing).hexdigest() + '\n').encode()
    files['scenario-index.json'] = encode({'schema_version': '1.0.0', 'kind': 'canopy.scenario-index',
                                         'default': default, 'scenarios': scenarios})
    for name, path in manifests.items():
        files[name] = path.read_bytes()
    shared = [{'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
              for name, data in files.items()]
    downloads = {}
    for scenario in scenarios:
        inventory = shared + [{'path': name, 'bytes': record['bytes'], 'sha256': record['sha256']}
                              for name, record in resources.items() if record['scenario_id'] == scenario['id']]
        inventory.sort(key=lambda f: f['path'])
        version = hashlib.sha256(encode(inventory)).hexdigest()[:20]
        downloads[scenario['id']] = encode({'version': version, 'scenario_id': scenario['id'],
            'bytes': sum(f['bytes'] for f in inventory), 'files': inventory})
        files[scenario['download_manifest']] = downloads[scenario['id']]
    download = downloads[default]
    return resources, files, routing, download


def build(root, output=None, refresh=False):
    resources, files, routing, download = generated(root)
    indexes = {name: data for name, data in files.items()
               if name in ('asset-sources.json', 'scenario-index.json') or name.startswith('download-manifests/')}
    indexes['download-manifest.json'] = download
    for name, data in indexes.items():
        target = root / 'visualizer/site' / name
        if refresh:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        elif not target.is_file() or target.read_bytes() != data:
            raise ValueError(f'Stale {name}; run build_pages.py --refresh')
    files['download-manifest.json'] = download
    files['.nojekyll'] = b''
    local = [r for r in resources.values() if r['source'] is not None]
    size = sum(len(data) for data in files.values()) + sum(r['bytes'] for r in local)
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
        for record in local:
            target = bounded(output, record['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(record['source'], target)
    return {'public_files': len(resources), 'frontend_files': len(files), 'bytes': size,
            'bundled_data_bytes': sum(r['bytes'] for r in local),
            'remote_data_bytes': sum(r['bytes'] for r in resources.values() if r['source'] is None)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New static artifact directory, usually under cache/')
    parser.add_argument('--refresh', action='store_true', help='Regenerate the tracked routing and download indexes')
    args = parser.parse_args()
    print(json.dumps(build(ROOT, args.output, args.refresh), indent=2))
