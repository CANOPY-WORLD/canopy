"""Versioned, scene-private assets. Protocol v1.1 is the binary payload codec."""
import copy
from pathlib import Path
import shutil
import tempfile
from canopy._io import read, write, check, relative, digest
from canopy.scenario.store import load as load_scenario, data_root, register
from common.contract import validate as validate_payload, asset_references


def load(storage, scenario, reference, *, verify=True):
    catalog = load_scenario(storage, scenario)
    if reference not in catalog['assets']: raise ValueError(f'Unknown scenario asset: {reference}')
    path = relative(data_root(storage, scenario), catalog['assets'][reference])
    asset = read(path); check(asset, 'asset')
    if asset['scenario_id'] != catalog['scenario_id'] or f"{asset['asset_id']}@{asset['version']}" != reference:
        raise ValueError('Asset owner/identity mismatch')
    manifest_path = relative(data_root(storage, scenario), asset['payload']['manifest'])
    if digest(manifest_path) != asset['payload']['sha256']: raise ValueError('Payload manifest checksum mismatch')
    manifest = read(manifest_path)
    if manifest['scene_id'] != scenario or manifest['spatial'] != asset['spatial']:
        raise ValueError('Payload owner/coordinates mismatch')
    # v1 payloads contain their own original provenance; never relabel old sources.
    ids = {x['id']:x for x in manifest['layers']}
    if not set(asset['payload']['layers']) <= ids.keys(): raise ValueError('Unknown payload layer')
    for id in asset['payload']['layers']:
        if (ids[id]['kind'] == 'mesh') != (asset['kind'] == 'geometry'):
            raise ValueError('Asset category disagrees with layer type')
    if asset['spatial']['origin'] != catalog['spatial']['origin'] or asset['spatial'].get('georeferenced',True) != catalog['spatial'].get('georeferenced',True):
        raise ValueError('Asset coordinates disagree with scenario')
    for dependency in asset['derived_from']:
        if dependency not in catalog['assets'] or dependency == reference:
            raise ValueError('Missing or self-referential asset dependency')
    if verify:
        validate_payload(manifest_path)
        expected = set().union(*(asset_references(x) for x in manifest['layers'])) | {x['asset'] for x in manifest.get('artifacts',[])}
        if set(asset['files']) != expected: raise ValueError('Asset file inventory differs from manifest')
        for name, sha in asset['files'].items():
            if digest(relative(manifest_path.parent, name)) != sha: raise ValueError(f'Asset checksum mismatch: {name}')
    return asset, manifest, manifest_path


def import_run(storage, scenario, source, *, derived_from=(), expected_kind=None):
    """Copy validated payload once; index geometry/physics independently. Never overwrite."""
    scenario_data = load_scenario(storage, scenario)
    source = Path(source).resolve(); validate_payload(source / 'manifest.json')
    manifest = read(source / 'manifest.json')
    if manifest['status'] != 'complete' or manifest['scene_id'] != scenario:
        raise ValueError('Only complete same-scenario results can be imported')
    if manifest['spatial']['origin'] != scenario_data['spatial']['origin'] or manifest['spatial'].get('georeferenced',True) != scenario_data['spatial'].get('georeferenced',True):
        raise ValueError('Result and scenario coordinate origins differ')
    for ref in derived_from: load(storage, scenario, ref)
    groups = {kind:[x['id'] for x in manifest['layers'] if (x['kind']=='mesh') == (kind=='geometry')] for kind in ('geometry','physics')}
    if expected_kind and not groups[expected_kind]: raise ValueError('Method did not produce its declared output kind')
    rid = manifest['run_id']
    # Validate identifier before constructing any path.
    from common.storage import identifier
    identifier(rid, run=True)
    base = data_root(storage, scenario); destination = base/'assets'/'bundles'/rid
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists(): raise FileExistsError(destination)
    stage = Path(tempfile.mkdtemp(prefix='.import-', dir=destination.parent))
    references = {}
    moved = False
    try:
        files = set().union(*(asset_references(x) for x in manifest['layers'])) | {x['asset'] for x in manifest.get('artifacts',[])}
        hashes = {}
        for name in sorted(files | {'manifest.json'}):
            src = relative(source, name); target = relative(stage, name)
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src,target)
            if name != 'manifest.json': hashes[name] = digest(target)
        validate_payload(stage/'manifest.json')
        for kind, layers in groups.items():
            if not layers: continue
            aid = rid + '_' + kind
            asset = dict(schema_version='2.0.0',scenario_id=scenario,asset_id=aid,version='1',kind=kind,
                spatial=manifest['spatial'],derived_from=list(derived_from),
                provenance=manifest['provenance'],files=hashes,
                payload={'format':'canopy-run-v1','manifest':str((destination/'manifest.json').relative_to(base)),
                         'sha256':digest(stage/'manifest.json'),'layers':layers})
            check(asset,'asset');write(stage/f'{kind}.asset.json',asset)
            references[aid+'@1']=str((destination/f'{kind}.asset.json').relative_to(base))
        # Atomic directory rename; reject collisions rather than overwrite historical output.
        with __import__('canopy.scenario.store',fromlist=['lock']).lock(storage, scenario):
            if destination.exists(): raise FileExistsError(destination)
            stage.rename(destination);moved=True
        register(storage,scenario,references)
    except BaseException:
        if stage.exists(): shutil.rmtree(stage)
        if moved: shutil.rmtree(destination)
        raise
    return list(references)
