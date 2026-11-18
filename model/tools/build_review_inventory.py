#!/usr/bin/env python3
"""Generate a small public review inventory; never copy raw payloads or provenance."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'model/src'))
SCENARIO = 'imperial_corridor_8km'
CATALOG = ROOT / 'scenario' / SCENARIO / 'asset-catalog.json'
INVENTORY = ROOT / 'visualizer/guide/inventory.json'


def read(path):
    return json.loads(path.read_text())


def encoded(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + '\n'


def refresh_assets():
    from common.storage import Storage
    from canopy.assets.store import load
    from canopy.scenario.store import data_root
    from canopy._io import relative
    storage = Storage.load(ROOT)
    scenario = read(ROOT / 'scenario' / SCENARIO / 'scenario.json')
    selected = {(x['asset'], x['layer']) for x in scenario['visualization']['layers']}
    assets = []
    bundles = {}
    for reference, descriptor in scenario['assets'].items():
        asset, manifest, path = load(storage, SCENARIO, reference, verify=True)
        bundle = path.parent
        # Count complete retained bundles, including descriptor and provenance files.
        files = [p for p in bundle.rglob('*') if p.is_file()]
        size = sum(p.stat().st_size for p in files)
        bundles[manifest['run_id']] = size
        if relative(data_root(storage, SCENARIO), descriptor).parent != bundle:
            raise ValueError('Review summary requires a self-contained retained bundle')
        times = manifest['time']['samples']
        assets.append({
            'reference': reference, 'kind': asset['kind'],
            'run_id': manifest['run_id'], 'simulation': manifest['simulation'],
            'scope': 'historical' if manifest['run_id'].startswith('recorded_') else 'verification',
            'derived_from': asset['derived_from'],
            'manifest_sha256': asset['payload']['sha256'],
            'bundle_bytes': size, 'bundle_files': len(files),
            'sample_count': len(times), 'time_range_s': [times[0], times[-1]] if times else None,
            'layers': [dict(id=l['id'], kind=l['kind'], format=l['format'],
                            unit=l.get('field', {}).get('unit'),
                            selected=(reference, l['id']) in selected)
                       for l in manifest['layers'] if l['id'] in asset['payload']['layers']],
        })
    return {
        'document_type': 'canopy-review-catalog', 'version': 1, 'scenario_id': SCENARIO,
        'description': 'Generated review metadata. scenario.json remains the runtime registry. '
                       'Bundle sizes include metadata and provenance; no raw arrays are included here.',
        'assets': assets, 'unique_bundle_bytes': sum(bundles.values()),
    }


def inventory(catalog):
    scenario = read(ROOT / 'scenario' / SCENARIO / 'scenario.json')
    models = []
    specs = ROOT / 'model/src/canopy/models/specs'
    order = ['geometry', 'solar', 'flood', 'wind', 'temperature', 'pollution']
    for model_path in sorted(specs.glob('*/model.json'), key=lambda p: (
            order.index(p.parent.name) if p.parent.name in order else len(order), p.parent.name)):
        model = read(model_path)
        methods = []
        for name, entry in model['methods'].items():
            spec = read(model_path.parent / entry['spec'])
            if spec['method_id'] != name or spec['version'] != entry['version']:
                raise ValueError(f'Model registry mismatch: {model_path}')
            methods.append({k: spec[k] for k in ('model_id', 'method_id', 'version', 'title',
                'description', 'category', 'inputs', 'outputs', 'parameters', 'capabilities', 'guide', 'example')})
        models.append({'id': model['model_id'], 'methods': methods})
    return {
        'document_type': 'canopy-review-inventory', 'version': 1,
        'repository': 'https://github.com/CANOPY-WORLD/canopy',
        'scenario': {
            'id': SCENARIO, 'title': 'London · Imperial Corridor', 'nominal_extent_m': [8000, 8000],
            'spatial': scenario['spatial'], 'task_count': len(scenario['tasks']),
            'visualization': scenario['visualization'],
            'rerun_status': 'Historical full-domain recipes are not yet registered. The separate '
                            'GLB crop → heightfield → solar chain has been verified.',
        },
        'models': models, 'assets': catalog['assets'],
        'unique_bundle_bytes': catalog['unique_bundle_bytes'],
        'visualizer': {
            'template': 'standard', 'presets': ['engineering', 'city', 'laboratory'],
            'shell': ['Renderer and camera', 'Layer controls', 'Timeline', 'Legend', 'Picking'],
            'layer_kinds': ['mesh', 'scalar_field', 'vector_field', 'trajectories', 'time_series'],
            'formats': ['glb', 'json', 'npy', 'npy_frames', 'trajectory_frames'],
            'widget_interface': ['load(context, layer, signal)', 'setTime(seconds)',
                'setVisible(visible)', 'setOpacity(value)', 'pick(query)', 'dispose()'],
            'compatibility': 'The detailed London website also presents terrain/context, traffic and '
                             'UAV resources through its preserved adapters. These are not all registered V2 Assets.',
        },
        'standards': {component: f'{component}/CONTRIBUTING.md'
                      for component in ('model', 'asset', 'visualizer', 'scenario')},
        'future': ['Zarr payload codec and browser reader', 'Remote object-store Asset resolver',
                   'Arbitrary volume slicing', 'Full-domain historical task recipes'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-assets', action='store_true', help='Validate local retained data and refresh its safe summary')
    parser.add_argument('--check', action='store_true', help='Fail if generated files differ; do not write')
    args = parser.parse_args()
    catalog = refresh_assets() if args.refresh_assets else read(CATALOG)
    outputs = {INVENTORY: inventory(catalog)}
    if args.refresh_assets:
        outputs[CATALOG] = catalog
    stale = []
    for path, value in outputs.items():
        content = encoded(value)
        if args.check:
            if not path.exists() or path.read_text() != content:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    if stale:
        raise SystemExit('Stale generated inventory: ' + ', '.join(stale))
    diagram = ROOT / 'visualizer/diagrams/architecture.svg'
    copy = ROOT / 'visualizer/guide/architecture.svg'
    if args.check:
        if not copy.exists() or copy.read_bytes() != diagram.read_bytes():
            raise SystemExit('Stale guide architecture.svg; regenerate the review inventory')
    else:
        copy.write_bytes(diagram.read_bytes())
    print('Review inventory checked.' if args.check else 'Review inventory generated from current specs and London metadata.')


if __name__ == '__main__':
    main()
