"""Export native 3D samples and roads for an offline demo recording, not an Asset."""
import argparse
import gzip
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from traffic.diagnostic_validation import assess_run
from traffic.demo_network import digest


def export(run, output, begin, end, center, radius):
    if not all(math.isfinite(v) for v in (begin,end,*center,radius)) or end<=begin or radius<=0:
        raise ValueError('Invalid recording bounds')
    validation=assess_run(run)
    if not validation['diagnostic_pass']: raise ValueError(f'Run failed: {validation["failed_checks"]}')
    config=json.loads((run/'config.json').read_text()); command=config['command']
    # Resolve retained copies relative to the run, even after archiving it elsewhere.
    network=run/Path(command[command.index('-n')+1]).name
    routes=run/Path(command[command.index('-r')+1]).name
    def parse(path):
        with (gzip.open if path.suffix=='.gz' else open)(path,'rb') as stream:return ET.parse(stream).getroot()
    def nearby(x,y):return abs(x-center[0])<=radius and abs(y-center[1])<=radius
    root=parse(network);lanes=[];junctions=[]
    def shape(text):return [list(map(float,p.split(','))) for p in text.split()]
    for edge in root.findall('edge'):
        for lane in edge.findall('lane'):
            points=shape(lane.get('shape'))
            if any(nearby(*p[:2]) for p in points):
                lanes.append({'id':lane.get('id'),'width':float(lane.get('width','3.2')),'internal':edge.get('function')=='internal','shape':points})
    for junction in root.findall('junction'):
        points=shape(junction.get('shape',''))
        if points and any(nearby(*p[:2]) for p in points):junctions.append({'id':junction.get('id'),'shape':points})
    types={t.get('id'):{k:float(t.get(k)) for k in ('length','width','height')} for t in parse(routes).findall('vType')}
    frames=[]
    with gzip.open(run/'traffic.fcd.xml.gz','rb') as stream:
        for _,step in ET.iterparse(stream,events=['end']):
            if step.tag!='timestep':continue
            time=float(step.get('time'))
            if begin<=time<end:
                if abs(time-begin-len(frames)*.1)>1e-6:raise ValueError('Missing 0.1 s sample')
                vehicles=[]
                for v in step:
                    x,y=float(v.get('x')),float(v.get('y'))
                    if nearby(x,y):vehicles.append([v.get('id'),v.get('type'),x,y,float(v.get('z','0')),math.radians(90-float(v.get('angle'))),math.radians(float(v.get('slope','0'))),float(v.get('speed'))])
                frames.append({'time':time,'vehicles':vehicles})
            step.clear()
            if time>=end:break
    if not frames or abs(len(frames)*.1-(end-begin))>1e-6:raise ValueError('Incomplete recording interval')
    data={'schema':'experimental-offline-sumo-review-1','position_reference':'front_bumper','coordinate_frame':'ENU','center':center,'radius':radius,'vehicle_types':types,'lanes':lanes,'junctions':junctions,'frames':frames,'record_layout':['id','type','east_m','north_m','z_m','heading_rad_ccw_east','slope_rad','speed_m_s'],'provenance':{'network_sha256':digest(network),'fcd_sha256':digest(run/'traffic.fcd.xml.gz'),'exporter_sha256':digest(__file__)},'limitations':['Synthetic demand and generated signals, not observed London operations','Heights derived from OSM layers, not terrain survey','Signal state not shown; no recorded phase output','Only vehicles present in adjacent samples may be interpolated']}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:json.dump(data,f,separators=(',',':'))
    return {'frames':len(frames),'lanes':len(lanes),'bytes':output.stat().st_size}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--begin',type=float,required=True);p.add_argument('--end',type=float,required=True)
    p.add_argument('--center',type=float,nargs=2,required=True);p.add_argument('--radius',type=float,default=220)
    a=p.parse_args();print(export(a.run,a.output,a.begin,a.end,a.center,a.radius))
