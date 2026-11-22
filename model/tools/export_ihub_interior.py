"""Place the retained I-HUB v10 concept interior in the corridor frame."""
import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
from pathlib import Path
import struct
import zipfile
import numpy as np


def read(p): return json.loads(p.read_text())
def write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2) + '\n')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def alignment(georef, origin):
    # Invert the recorded GLB-to-equirectangular fit, then change geographic origin.
    lat, lon = origin['latitude'], origin['longitude']
    a = np.diag([math.cos(math.radians(lat))/math.cos(math.radians(georef['lat0'])), 1]) @ np.array(georef['R']).T / georef['scale']
    b = np.array([(georef['lon0']-lon)*math.pi/180*6378137*math.cos(math.radians(lat)), (georef['lat0']-lat)*math.pi/180*6378137]) - a @ georef['t']
    m = np.eye(4)
    m[0,0],m[0,2],m[2,0],m[2,2] = a[0,0],-a[0,1],-a[1,0],a[1,1]
    m[0,3],m[2,3] = b[0],-b[1]
    return m


def transform_glb(source, target, matrix):
    raw = source.read_bytes()
    magic,version,size = struct.unpack_from('<4sII',raw)
    if magic != b'glTF' or version != 2 or size != len(raw): raise ValueError('Invalid GLB')
    length,kind = struct.unpack_from('<II',raw,12)
    if kind != 0x4e4f534a: raise ValueError('Missing JSON chunk')
    doc=json.loads(raw[20:20+length])
    for scene in doc['scenes']:
        index=len(doc['nodes'])
        doc['nodes'].append(dict(name='White City georeference to corridor',matrix=matrix.T.flatten().tolist(),children=scene['nodes']))
        scene['nodes']=[index]
    encoded=json.dumps(doc,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%4)
    remainder=raw[20+length:]  # Preserve all vertex, index, image and material payload bytes.
    target.write_bytes(struct.pack('<4sII',b'glTF',2,20+len(encoded)+len(remainder))+struct.pack('<II',len(encoded),kind)+encoded+remainder)


def export(run, georef_path, scenario, output):
    if output.exists(): raise FileExistsError(output)
    source=read(run/'manifest.json');geo=read(georef_path);catalog=read(scenario)
    if source['run_id']!='ihub_office_journey_20261117_v10': raise ValueError('Expected retained v10')
    # Verify source meshes against the retained source checksums before transformation.
    checks=read(run/'retention_checks.json')
    if not checks['passed']: raise ValueError('Retained source QA did not pass')
    for name, key in [('building.glb','buildingGLBSha256'),('office.glb','officeGLBSha256')]:
        if digest(run/name)!=checks[key]: raise ValueError('Retained mesh checksum mismatch: '+name)
    matrix=alignment(geo,catalog['spatial']['origin']);output.mkdir(parents=True)
    for name in ('building.glb','office.glb'): transform_glb(run/name,output/name,matrix)
    for name in ('manifest.json','publication.json','floor_selection.json'):
        (output/('source-'+name)).write_bytes((run/name).read_bytes())
    write(output/'source-georef.json',geo)
    points=[]
    for e,n,z in itertools.product(*zip(source['spatial']['bounds_m']['min'],source['spatial']['bounds_m']['max'])):
        x,y,minus_n,_=matrix @ [e,z,-n,1];points.append([x,-minus_n,y])
    params=dict(source_run=source['run_id'],source_origin=source['spatial']['origin'],source_fit=geo,
        gltf_root_matrix=matrix.T.flatten().tolist(),vertex_buffers_unchanged=True,concept_only=True,
        source_datum_correction='The original manifest labels the authored GLB as ENU. Its retained georef.json records a 2.17 degree rotation and translation. This export applies that inverse fit before changing geographic origin; no additional office-local origin is applied.',
        placement_accuracy='Recorded georeference fit median residual 1.58 m; not a surveyed building alignment.',
        floor_elevation_m=32.267796516331146,vertical_policy='Unchanged authored relative height; not absolute ODN.',
        inherited_layout_limit='office_03 retains the accepted 0.2791 m2 corner discrepancy (up to 0.1801 m outside source slab).')
    write(output/'alignment.json',params)
    with zipfile.ZipFile(output/'source_snapshot.zip','w',zipfile.ZIP_DEFLATED) as z:
        z.write(__file__,'export_ihub_interior.py');z.writestr('scenario-spatial.json',json.dumps(catalog['spatial']));z.writestr('georef.json',json.dumps(geo))
    artifacts=[dict(id=p.stem.replace('-','_'),asset=p.name,sha256=digest(p),media_type='application/zip' if p.suffix=='.zip' else 'application/json') for p in output.iterdir() if p.suffix!='.glb']
    manifest=dict(schema_version='1.1.0',scene_id=catalog['scenario_id'],simulation='geometry',run_id=output.name,status='complete',created_at=datetime.now(timezone.utc).isoformat(),
        provenance=dict(code_revision='retained-v10-with-recorded-georeference-adapter',dirty=True,parameters=params,inputs=[dict(id=n.replace('.','_'),sha256=digest(run/n)) for n in ('building.glb','office.glb','manifest.json')]+[dict(id='georef',sha256=digest(georef_path))]),
        spatial={**catalog['spatial'],'bounds_m':dict(min=np.min(points,axis=0).tolist(),max=np.max(points,axis=0).tolist())},time=dict(unit='s',samples=[]),
        layers=[dict(id=k,kind='mesh',format='glb',asset=k+'.glb',sampling='static',encoding=dict(coordinate_frame='glTF-y-up'),display=dict(widget='mesh',capabilities=['pick','opacity'])) for k in ('building','office')],artifacts=artifacts)
    write(output/'manifest.json',manifest)
    print(json.dumps(dict(output=str(output),matrix=matrix.T.flatten().tolist(),bytes=sum(p.stat().st_size for p in output.iterdir()))))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('run','georef','scenario','output'): p.add_argument(key,type=Path)
    a=p.parse_args();export(a.run,a.georef,a.scenario,a.output)
