"""Export a scenario and its declared assets as a portable local archive."""
from pathlib import Path
import os
import io
import json
import tarfile
import tempfile
from canopy.scenario.store import load as scenario_load,data_root
from canopy.assets.store import load as asset_load
from canopy._io import relative


def pack(storage,scenario,destination):
    data=scenario_load(storage,scenario);root=data_root(storage,scenario)
    destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError(destination)
    if destination.is_relative_to(root):raise ValueError('Archive output must be outside scenario assets')
    members={}
    for ref,descriptor in data['assets'].items():
        asset,manifest,path=asset_load(storage,scenario,ref)
        members[f'project/{scenario}/{descriptor}']=relative(root,descriptor)
        members[f'project/{scenario}/{asset["payload"]["manifest"]}']=path
        for name in asset['files']:
            file=relative(path.parent,name)
            members[f'project/{scenario}/'+str(file.relative_to(root))]=file
    destination.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(dir=destination.parent,prefix='.canopy-pack-');os.close(fd)
    try:
        with tarfile.open(temp,'w:gz',dereference=True) as archive:
            encoded=(json.dumps(data,indent=2,allow_nan=False)+'\n').encode()
            metadata=tarfile.TarInfo(f'project/{scenario}/scenario.json');metadata.size=len(encoded)
            archive.addfile(metadata,io.BytesIO(encoded))
            for name,path in sorted(members.items()):archive.add(path,arcname=name,recursive=False)
        # Exclusive creation protects another concurrent pack operation.
        os.link(temp,destination)
    finally:os.unlink(temp)
    return {'scenario_id':scenario,'archive':str(destination),'files':len(members)+1,'bytes':destination.stat().st_size}
