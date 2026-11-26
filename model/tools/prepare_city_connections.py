"""Retain a new connector-aware city input bundle; never replace an input Asset."""
import argparse
import copy
from datetime import datetime, timezone
from pathlib import Path
import shutil

from canopy._io import read, write, digest, relative
from canopy.assets.store import import_run, load
from canopy.running.provenance import snapshot_runtime
from common.storage import Storage
from healthy_route.source_walking_network import build_pinned


def prepare(workspace, request_path, segments, connectors, origin, goal, output_request):
    workspace=Path(workspace).resolve(); storage=Storage.load(workspace)
    request=read(request_path); scene=request['scenario_id']
    geometry,_,geometry_path=load(storage,scene,request['inputs']['geometry'])
    city,manifest,source=load(storage,scene,request['inputs']['city'])
    if source != geometry_path:
        raise ValueError('Expected Geometry and city inputs from the same bundle')
    network,audit=build_pinned(source.parent,segments,connectors)
    for node in [origin,goal]:
        if node not in network['nodes']:raise ValueError('Unknown explicit new endpoint: '+node)
    import hashlib,json
    network_bytes=json.dumps(network,separators=(',',':'),allow_nan=False).encode()
    rid='city_connections_'+hashlib.sha256(network_bytes).hexdigest()[:12]+'_'+digest(Path(__file__))[:8]
    stage=workspace/'cache'/rid
    if stage.exists():raise FileExistsError(stage)
    if Path(output_request).exists():raise FileExistsError(output_request)
    stage.mkdir(parents=True)
    for name in city['files']:
        if name == 'source_snapshot.tar.gz':
            continue  # New runtime snapshot below; original remains in dependency.
        target=relative(stage,name);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(relative(source.parent,name),target)
    (stage/'network.json').write_bytes(network_bytes)
    write(stage/'network-audit.json',audit)
    extra=['network-audit.json']
    for original,kind in [(Path(segments),'segments'),(Path(connectors),'connectors')]:
        name='transportation-source/connectivity-'+kind+'-2026-10-21.0.parquet'
        target=stage/name;target.parent.mkdir(exist_ok=True)
        shutil.copyfile(original,target);extra.append(name)
    meta=read(stage/'city-inputs.json')
    meta['files']['network.json']=digest(stage/'network.json')
    meta['alignment']['files']['network.json']=digest(stage/'network.json')
    meta['alignment']['network_topology']=network['provenance']
    meta['alignment']['network_summary']=network['summary']
    meta['alignment']['network_audit_sha256']=digest(stage/'network-audit.json')
    meta['alignment']['network_builder_sha256']=digest(Path(__file__).parents[1]/'src/healthy_route/source_walking_network.py')
    meta['alignment']['horizontal_mapping']='Routes preserve the prepared network vertices within 0.00001 m. Source junction IDs are reconciled to 0.1 m presentation coordinates within 0.081 m; no nearest-road or across-gap connections.'
    # Only the public snapshot inventory is checked against the web root. Raw
    # source metadata/audit stays in the retained input bundle, not the static site.
    meta['files']=dict(meta['files'],**{name:digest(stage/name) for name in extra})
    write(stage/'city-inputs.json',meta)
    revision=snapshot_runtime(stage/'source_snapshot.tar.gz')
    shutil.copyfile(Path(__file__),stage/'prepare_city_connections.py');extra.append('prepare_city_connections.py')
    payload=copy.deepcopy(manifest)
    payload.update(run_id=rid,created_at=datetime.now(timezone.utc).isoformat())
    payload['provenance']=dict(code_revision=revision,dirty=True,
        parameters={'purpose':'Local connector-aware walking input; city geometry/fields byte-identical',
                    'network_sha256':digest(stage/'network.json')},
        inputs=[{'id':'previous_city_manifest','sha256':digest(source)}])
    for artifact in payload['artifacts']:
        artifact['sha256']=digest(stage/artifact['asset'])
    for i,name in enumerate(extra):
        payload['artifacts'].append(dict(id='network_source_'+str(i),asset=name,sha256=digest(stage/name),media_type='application/octet-stream'))
    write(stage/'manifest.json',payload)
    refs=import_run(storage,scene,stage,derived_from=[request['inputs']['geometry'],request['inputs']['city']])
    request['inputs'].update(geometry=next(r for r in refs if '_geometry@' in r),city=next(r for r in refs if '_physics@' in r))
    request['parameters'].update(origin=origin,goal=goal)
    write(Path(output_request),request)
    return dict(inputs=request['inputs'],network_summary=network['summary'],request=str(output_request))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['workspace','request','segments','connectors','origin','goal','output-request']:p.add_argument('--'+key,required=True)
    a=p.parse_args()
    print(prepare(a.workspace,a.request,a.segments,a.connectors,a.origin,a.goal,a.output_request))
