"""Explicit OSM-based traffic demonstrator preparation; never edits source Assets.

This experimental preparation utility is not a registered Canopy Method. Demand
and signal plans are generated assumptions, not measured London operations.
"""
from pathlib import Path
import hashlib
import json
import math
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

VEHICLES = {
    'car': ('passenger', .60, 4.5, 1.8, 1.5),
    'taxi': ('taxi', .10, 4.8, 1.9, 1.9),
    'bus': ('bus', .08, 10.5, 2.55, 4.4),
    'lgv': ('delivery', .15, 5.5, 2., 2.5),
    'hgv': ('truck', .05, 10.5, 2.55, 3.6),
    'motorcycle': ('motorcycle', .02, 2.2, .8, 1.4),
}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def audit_signals(network):
    """Check protected greens against native foes, not surveyed real-world rules."""
    root = ET.parse(network).getroot()
    by_via = {c.get('via'): c for c in root.findall('connection') if c.get('tl')}
    programs = {}
    for tls in root.findall('tlLogic'):
        programs.setdefault(tls.get('id'), []).append(tls)
    conflicts = []
    for junction in root.findall('junction'):
        internal = junction.get('intLanes', '').split()
        requests = {int(r.get('index')): r for r in junction.findall('request')}
        for i, via in enumerate(internal):
            a = by_via.get(via)
            if a is None or i not in requests:
                continue
            foes = requests[i].get('foes', '')[::-1]
            for k, other in enumerate(internal[:i]):
                b = by_via.get(other)
                if b is None or a.get('tl') != b.get('tl') or k >= len(foes) or foes[k] != '1':
                    continue
                for program in programs[a.get('tl')]:
                    for phase in program.findall('phase'):
                        state = phase.get('state')
                        if state[int(a.get('linkIndex'))] == state[int(b.get('linkIndex'))] == 'G':
                            conflicts.append({'junction': junction.get('id'), 'lanes': [via, other], 'state': state})
    return {'signal_controllers': len(programs), 'conflicting_protected_greens': conflicts,
            'scope': 'Native foe matrix consistency only; does not certify geometric conflict detection or real signal plans'}


def execute(command, output, name):
    save(output / (name + '.command.json'), [str(v) for v in command])
    with (output / (name + '.log')).open('w') as log:
        subprocess.run([str(v) for v in command], stdout=log, stderr=log, check=True)


def build_network(osm, scenario, output, junction_radius=4, join_distance=10):
    if not all(math.isfinite(v) and v > 0 for v in (junction_radius, join_distance)):
        raise ValueError('Junction radius and join distance must be positive and finite')
    osm, scenario, output = Path(osm), Path(scenario), Path(output).resolve()
    source = ET.parse(osm).getroot()
    if source.tag != 'osm' or source.find('remark') is not None or not source.findall('way'):
        raise ValueError('Incomplete OSM input')
    spatial = json.loads(scenario.read_text())['spatial']
    origin = spatial['origin']
    lon, lat = origin['longitude'], origin['latitude']
    if not all(math.isfinite(v) for v in (lon, lat)):
        raise ValueError('Invalid scene origin')
    import sumo
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(osm, output / 'roads.osm.xml')
    shutil.copy2(scenario, output / 'source-scenario.json')
    home = Path(sumo.SUMO_HOME)
    projection = f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs'
    command = [home / 'bin/netconvert', '--osm-files', output / 'roads.osm.xml',
        '--output-file', output / 'network.net.xml', '--proj', projection,
        '--offset.disable-normalization', '--lefthand', '--geometry.remove',
        '--ramps.guess', '--roundabouts.guess', '--junctions.join', '--tls.guess-signals',
        '--junctions.join-dist', str(join_distance), '--default.junctions.radius', str(junction_radius),
        '--tls.discard-simple', '--tls.join', '--tls.default-type', 'actuated',
        '--tls.yellow.time', '4', '--tls.allred.time', '2', '--osm.turn-lanes',
        '--osm.layer-elevation', '5',
        '--keep-edges.in-boundary', '-4500,-4500,4500,4500',
        '--keep-edges.by-vclass', 'passenger,taxi,bus,delivery,truck,motorcycle',
        '--no-turnarounds', '--junctions.internal-link-detail', '12',
        '--internal-junctions.vehicle-width', '2.55', '--junctions.limit-turn-speed', '4',
        '--precision', '6']
    execute(command, output, 'netconvert')
    tree = ET.parse(output / 'network.net.xml')
    root = tree.getroot()
    # Shared turn lanes need jam-aware detector eligibility, not missing detectors.
    for tls in root.findall('tlLogic'):
        if tls.get('type') == 'actuated':
            ET.SubElement(tls, 'param', key='jam-threshold', value='30')
    tree.write(output / 'network.net.xml', encoding='utf-8', xml_declaration=True)
    save(output / 'provenance.json', {
        'osm_sha256': digest(osm), 'network_sha256': digest(output / 'network.net.xml'),
        'code_sha256': digest(__file__), 'projection': projection,
        'coordinate_frame': 'local east/north metres; terrain-normalized z with estimated 5 m per OSM layer',
        'scenario_origin': origin, 'scenario_bounds_m': spatial['bounds_m'],
        'license': 'OpenStreetMap contributors, ODbL 1.0',
        'solver_version': subprocess.check_output([home / 'bin/netconvert', '--version'], text=True).splitlines()[0],
        'external_edges': sum(e.get('function') != 'internal' for e in root.findall('edge')),
        'signal_controllers': len(root.findall('tlLogic')),
        'limitations': ['Generated signal plans, not observed London timings',
                       'OSM turning-lane markings and restrictions; missing information inferred by netconvert',
                       'New demonstrator, not reproduction of the old website recording',
                       'Bridge/tunnel elevations inferred at 5 m per OSM layer, not surveyed heights',
                       'No traffic-system acceptance until numerical and geometry checks pass']})
    return output / 'network.net.xml'


def build_demand(network, output, rate, duration, seed):
    if not all(math.isfinite(v) and v > 0 for v in (rate, duration)):
        raise ValueError('Rate and duration must be finite and positive')
    import sumo
    network, output = Path(network).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    home = Path(sumo.SUMO_HOME)
    all_types, all_vehicles, counts = [], [], {}
    for index, (kind, (vclass, fraction, length, width, height)) in enumerate(VEHICLES.items()):
        command = [sys.executable, home / 'tools/randomTrips.py', '-n', network,
            '-o', output / f'{kind}.trips.xml', '-r', output / f'{kind}.rou.xml',
            '--vehicle-class', vclass, '--prefix', kind, '--seed', str(seed + index),
            '--begin', '0', '--end', str(duration), '--insertion-rate', str(rate * fraction),
            '--min-distance', '1000', '--max-distance', '6000', '--fringe-factor', '3',
            '--length', '--random-depart', '--validate', '--threads', '4',
            '--trip-attributes', f'departLane="best" departSpeed="0" departPos="base" '
                f'length="{length}" width="{width}" height="{height}" '
                'carFollowModel="Krauss" tau="1.5" minGap="2.5" sigma="0.2" '
                'jmTimegapMinor="2" jmAdvance="0" jmExtraGap="2.5" '
                'lcAssertive="0.5" lcCooperative="1"']
        execute(command, output, kind)
        root = ET.parse(output / f'{kind}.rou.xml').getroot()
        for t in root.findall('vType'):
            t.set('id', kind)
            all_types.append(t)
        vehicles = root.findall('vehicle')
        for vehicle in vehicles:
            vehicle.set('type', kind)
        all_vehicles.extend(vehicles)
        counts[kind] = {'requested_rate_per_hour': rate * fraction, 'routed_vehicles': len(vehicles)}
    root = ET.Element('routes')
    root.extend(all_types)
    root.extend(sorted(all_vehicles, key=lambda v: (float(v.get('depart')), v.get('id'))))
    ET.ElementTree(root).write(output / 'routes.rou.xml', encoding='utf-8', xml_declaration=True)
    save(output / 'provenance.json', {
        'network_sha256': digest(network), 'routes_sha256': digest(output / 'routes.rou.xml'),
        'code_sha256': digest(__file__), 'seed': seed,
        'demand_duration_s': duration, 'requested_rate_per_hour': rate,
        'routed_vehicle_count': len(all_vehicles), 'vehicle_counts': counts,
        'limitations': ['Synthetic OD sampling and vehicle mix; not calibrated counts',
                       'Generic bus trips, not scheduled GTFS services',
                       'Routed count may differ from requested demand; routing logs retained',
                       'Departure rate is not simultaneous road occupancy']})
    return output / 'routes.rou.xml'


def upstream_waiting(network, output):
    """Build a native policy that waits before, rather than inside, junctions.

    Internal driving lanes remain present. This avoids auto-generated internal
    waiting locations which can place a long vehicle in a conflicting swept path.
    It changes the demo's native junction policy, not a runtime speed controller.
    """
    import sumo
    network, output = Path(network).resolve(), Path(output).resolve()
    root = ET.parse(network).getroot()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(network, output / 'source.net.xml')
    patches = ET.Element('connections')
    for connection in root.findall('connection'):
        if not connection.get('from', '').startswith(':'):
            attrs = {key: connection.get(key) for key in ('from','to','fromLane','toLane')}
            ET.SubElement(patches, 'connection', **attrs, contPos='0')
    ET.ElementTree(patches).write(output/'waiting.con.xml', encoding='utf-8', xml_declaration=True)
    home = Path(sumo.SUMO_HOME)
    command = [home/'bin/netconvert', '-s', output/'source.net.xml',
        '--connection-files', output/'waiting.con.xml', '-o', output/'network.net.xml',
        '--junctions.internal-link-detail','12','--internal-junctions.vehicle-width','2.55',
        '--junctions.limit-turn-speed','4','--precision','6','--offset.disable-normalization',
        '--tls.rebuild','--tls.layout','incoming','--tls.default-type','actuated',
        '--tls.yellow.time','4','--tls.allred.time','2']
    execute(command, output, 'netconvert')
    rebuilt = ET.parse(output/'network.net.xml').getroot()
    for tls in rebuilt.findall('tlLogic'):
        if tls.get('type') == 'actuated':
            for param in list(tls.findall('param')):
                if param.get('key') == 'jam-threshold': tls.remove(param)
            ET.SubElement(tls, 'param', key='jam-threshold', value='30')
    ET.ElementTree(rebuilt).write(output/'network.net.xml', encoding='utf-8', xml_declaration=True)
    def connections(net):
        return {(c.get('from'),c.get('to'),c.get('fromLane'),c.get('toLane')) for c in net.findall('connection') if not c.get('from','').startswith(':')}
    if connections(root) != connections(rebuilt):
        raise ValueError('Native lane connectivity changed during waiting-policy rebuild')
    if any(j.get('type')=='internal' for j in rebuilt.findall('junction')):
        raise ValueError('Internal waiting points remain')
    if not any(e.get('function')=='internal' for e in rebuilt.findall('edge')):
        raise ValueError('Internal driving lanes were lost')
    save(output/'provenance.json', {
        'source_network_sha256':digest(network),'network_sha256':digest(output/'network.net.xml'),
        'source_sha256':digest(__file__),'patched_connections':len(patches),
        'policy':'Native SUMO contPos=0: wait upstream; preserve driving lanes/connectivity; rebuild protected incoming-approach signal plans',
        'limitations':['Conservative generated demo policy, not measured London operation',
                       'Requires simulation and clearance checks before acceptance']})
    return output/'network.net.xml'
