"""Snapshot the installed first-party code actually resolved by this interpreter."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

from canopy._io import digest

PACKAGES=('healthy_route','canopy','common','urban_flow','urban_geometry','urban_planning','traffic','uav_routing','energy')
SUFFIXES={'.py','.json','.js','.mjs','.cjs','.sh','.toml','.yaml','.yml','.md','.cu','.c','.cpp','.h','.hpp','.so'}


def snapshot_runtime(destination):
    """Return a content identity, independent of a possibly unrelated metadata checkout.

    Third-party dependencies are versioned in environment.json, not recopied. The
    archive preserves package paths for both editable and wheel installations.
    """
    destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    inventory={};sources=[]
    for name in PACKAGES:
        spec=importlib.util.find_spec(name)
        if spec is None or not spec.submodule_search_locations:continue
        for root in sorted({Path(location).resolve() for location in spec.submodule_search_locations}):
            for path in sorted(root.rglob('*')):
                if not path.is_file() or path.is_symlink() or '__pycache__' in path.parts:continue
                if path.suffix not in SUFFIXES and not path.name.startswith(('LICENSE','NOTICE','COPYING')):continue
                archive_path=f'src/{name}/{path.relative_to(root).as_posix()}'
                if archive_path in inventory:raise ValueError('Ambiguous runtime package source')
                inventory[archive_path]=digest(path);sources.append((path,archive_path))
    if not any(path.startswith('src/canopy/') for path in inventory):raise ValueError('Canopy runtime source unavailable')
    identity=hashlib.sha256(json.dumps(inventory,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(destination,'x:gz') as archive:
        for path,arcname in sources:
            archive.add(path,arcname=arcname,recursive=False)
        index=json.dumps({'schema_version':'1.0.0','identity':'source-sha256:'+identity,'files':inventory},sort_keys=True,indent=2).encode()
        info=tarfile.TarInfo('runtime-source.json');info.size=len(index);info.mode=0o644
        archive.addfile(info,io.BytesIO(index))
    return 'source-sha256:'+identity
