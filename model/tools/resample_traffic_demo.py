"""Scale a validated demo OD pool without changing its network or vehicle types."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import xml.etree.ElementTree as ET


def resample(source, output, count, duration, seed):
    if count <= 0 or not math.isfinite(duration) or duration <= 0:
        raise ValueError('Count and duration must be positive and finite')
    tree = ET.parse(source).getroot()
    pool = tree.findall('vehicle')
    if not pool or any(v.find('route') is None for v in pool):
        raise ValueError('Explicit routed OD pool required')
    rng = random.Random(seed)
    root = ET.Element('routes')
    root.extend(copy.deepcopy(tree.findall('vType')))
    vehicles = []
    for i in range(count):
        original = rng.choice(pool)
        vehicle = copy.deepcopy(original)
        vehicle.set('id', f'demo_{seed}_{i}')
        vehicle.set('depart', f'{rng.uniform(0, duration):.6f}')
        ET.SubElement(vehicle, 'param', key='demo.source_route_id', value=original.get('id'))
        vehicles.append(vehicle)
    root.extend(sorted(vehicles, key=lambda v: float(v.get('depart'))))
    output.mkdir(parents=True, exist_ok=False)
    ET.ElementTree(root).write(output/'routes.rou.xml', encoding='utf-8', xml_declaration=True)
    (output/'provenance.json').write_text(json.dumps({
        'pool_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'route_pool_size':len(pool),'seed':seed,'requested_departures':count,
        'demand_duration_s':duration,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limitations':['Synthetic resampling with replacement, not measured OD demand',
                       'Vehicle mix is sampled from the routed pool; count is departures, not concurrent occupancy']},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--count',type=int,required=True);p.add_argument('--duration',type=float,required=True);p.add_argument('--seed',type=int,default=43)
    a=p.parse_args();resample(a.source,a.output,a.count,a.duration,a.seed)
