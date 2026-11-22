"""Export a checked SUMO interval for local viewer review, not Asset registration."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from traffic.diagnostic_validation import assess_run


def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def export(run,output,begin,end):
    if not all(math.isfinite(v) for v in (begin,end)) or end<=begin:
        raise ValueError('Review interval must be finite and increasing')
    validation=assess_run(run)
    if not validation['diagnostic_pass']:
        raise ValueError('Run failed diagnostic acceptance: '+str(validation['failed_checks']))
    config=json.loads((run/'config.json').read_text())
    route=Path(config['command'][config['command'].index('-r')+1])
    opener=gzip.open if route.suffix=='.gz' else open
    with opener(route,'rb') as stream:types={v.get('id'):{k:float(v.get(k)) for k in ['length','width','height']} for v in ET.parse(stream).getroot().findall('vType')}
    output.mkdir(parents=True,exist_ok=False)
    vehicles=[];lookup={};times=[];counts={}
    source=run/'traffic.fcd.xml.gz'
    with gzip.open(source,'rb') as stream,(output/'traffic-am.bin').open('wb') as binary:
        for _,element in ET.iterparse(stream,events=['end']):
            if element.tag!='timestep':continue
            time=float(element.get('time'))
            if begin<=time<end:
                if abs(time-(begin+len(times)*.1))>1e-6:raise ValueError('Missing or nonuniform 0.1 s samples')
                records=[]
                for v in element:
                    if abs(float(v.get('z','0')))>1e-6 or abs(float(v.get('slope','0')))>1e-6:
                        raise ValueError('Legacy XY review format cannot preserve recorded elevation/slope; use native 3D review')
                    identity=v.get('id');kind=v.get('type')
                    if kind not in types:raise ValueError(f'Missing dimensions for {kind}')
                    if identity not in lookup:
                        lookup[identity]=len(vehicles);vehicles.append({'id':identity,'type':kind});counts[kind]=counts.get(kind,0)+1
                    x,y,angle=map(float,[v.get('x'),v.get('y'),v.get('angle')])
                    records.append(struct.pack('<Ifff',lookup[identity],x,y,math.radians(90-angle)))
                binary.write(struct.pack('<I',len(records)));binary.write(b''.join(records));times.append(time)
            element.clear()
            if time>=end:break
    if not times or abs(len(times)*.1-(end-begin))>1e-6:raise ValueError('Incomplete requested review interval')
    metadata={'schema':'corridor-traffic-v1','t0':begin,'dt':.1,'frames':len(times),'synthetic':True,
      'coordinate_frame':'ENU','units':'m','position_reference':'front_bumper','vehicle_types':types,
      'heading':'radians counter-clockwise from +x (east)','vehicles':vehicles,
      'binary':{'asset':'traffic-am.bin','byte_order':'little','frame_layout':'uint32 count, then count x {uint32 vehicleIndex, float32 x, float32 y, float32 headingRad}', 'bytes':(output/'traffic-am.bin').stat().st_size,'sha256':sha256(output/'traffic-am.bin')},
      'provenance':{'simulation':'SUMO 1.28.0 diagnostic rerun','source_fcd_sha256':sha256(source),'controller_sha256':config.get('controller_sha256'),'guarded_junctions':config.get('guarded_junctions',[]),'collision_count':0,'teleports':0,'limitations':config.get('limitations',[])},'type_counts':counts}
    (output/'traffic-am.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps({'frames':len(times),'vehicles':len(vehicles),'types':counts,'bytes':metadata['binary']['bytes']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('output',type=Path);p.add_argument('--begin',type=float,required=True);p.add_argument('--end',type=float,required=True);a=p.parse_args()
    if a.end<=a.begin:p.error('end must exceed begin')
    export(a.run,a.output,a.begin,a.end)
