"""Package the approved native review recording without altering its samples."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def export(run, source, output):
    review=run/'southken-review.json'
    data=json.loads(review.read_text())
    validation=json.loads((run/'validation.json').read_text())
    if not validation['diagnostic_pass'] or validation['collisions'] or validation['teleports']:
        raise ValueError('Rejected traffic run')
    for key,name in [('network_sha256','network.xml'),('fcd_sha256','traffic.fcd.xml.gz'),('signals_sha256','signals.xml')]:
        if digest(run/name)!=data['provenance'][key]:raise ValueError('Recording source mismatch: '+name)
    if output.exists():raise ValueError('Snapshot already exists')
    old=json.loads((source/'manifest.json').read_text())
    scene=json.loads((source/'scene.json').read_text())
    output.mkdir(parents=True)
    (output/'context').mkdir()
    shutil.copy2(review,output/'context/traffic-native.json')
    write(output/'context/traffic-native-validation.json',validation)
    context=scene['corridor_context']
    removed={'scene.json','derivation.json',context.pop('traffic_meta'),context.pop('traffic_binary')}
    context['native_traffic']='context/traffic-native.json';context['traffic_speed']=1
    scene['layers']['solar']['daylight_default']=True
    write(output/'scene.json',scene)
    records=[{**r,'source_snapshot':r.get('source_snapshot',old['snapshot'])} for r in old['files'] if r['path'] not in removed]
    write(output/'derivation.json',dict(kind='native-traffic-replacement',source_snapshot=old['snapshot'],source_manifest_sha256=digest(source/'manifest.json'),recording_sha256=digest(review),retained_source_sha256=data['provenance'],removed_from_selection=sorted(removed),scope='South Kensington review interval 680.0–720.9 simulation seconds, 0.1 s samples. Synthetic low-load demonstration, not citywide calibrated traffic.',attribution='Roads and crossings © OpenStreetMap contributors, ODbL; https://www.openstreetmap.org/copyright',validation_limits='Zero collisions and teleports in this run; three emergency brakes. Higher demand remains rejected. Native heights are OSM layer estimates, not terrain survey.'))
    for p in sorted(output.rglob('*')):
        if p.is_file():
            name=p.relative_to(output).as_posix()
            records.append(dict(path=name,viewer_path='scenes/imperial_corridor_8km/'+name,bytes=p.stat().st_size,sha256=digest(p)))
    manifest={**old,'snapshot':output.name,'files':sorted(records,key=lambda r:r['path']),'bytes':sum(r['bytes'] for r in records),'derivation':dict(source_snapshot=old['snapshot'],traffic_recording_sha256=digest(review))}
    write(output/'manifest.json',manifest)
    print(json.dumps(dict(files=len(records),bytes=manifest['bytes'],new_bytes=sum(r['bytes'] for r in records if 'source_snapshot' not in r))))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['run','source','output']:p.add_argument(name,type=Path)
    a=p.parse_args();export(a.run,a.source,a.output)
