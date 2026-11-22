"""Numerical acceptance for diagnostic runs, separate from system validation.

Passing these checks is necessary but does not establish valid road geometry,
calibrated demand, correct signal timing, or safety at untested loads.
"""
import re
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path


def assess_run(folder):
    folder = Path(folder)
    collisions = ET.parse(folder / 'collisions.xml').getroot().findall('collision')
    steps = ET.parse(folder / 'summary.xml').getroot().findall('step')
    if not steps:
        raise ValueError('Run has no summary samples')
    last = steps[-1]
    collision_count = max(len(collisions), int(last.get('collisions', '0')))
    log = (folder / 'sumo.log').read_text()
    emergency_stops = len(re.findall(r'performs emergency stop\b', log))
    emergency_braking = len(re.findall(r'performs emergency braking\b', log))
    detector_warnings = [line for line in log.splitlines() if 'no controlling detector' in line]
    invalid_routes = [line for line in log.splitlines() if
                      'no connection to the next edge' in line or
                      'has no valid route' in line or 'is not connected' in line]
    invalid_departures = [line for line in log.splitlines() if 'Invalid departPos' in line]
    interval_complete = False
    config_path = folder / 'config.json'
    if config_path.exists():
        command = json.loads(config_path.read_text()).get('command', [])
        try:
            end = float(command[command.index('--end') + 1])
            step = float(command[command.index('--step-length') + 1])
            final_time = float(last.get('time'))
            interval_complete = (all(math.isfinite(v) for v in (end, step, final_time))
                                 and step > 0 and abs(final_time - (end - step)) < 1e-5)
        except (ValueError, IndexError, TypeError):
            pass
    teleports = int(last.get('teleports', '0'))
    discarded = int(last.get('discarded', '0'))
    failures = []
    for name, count in [('collisions', collision_count), ('teleports', teleports),
                        ('emergency_stops', emergency_stops), ('discarded', discarded),
                        ('invalid_route_warnings', len(invalid_routes)),
                        ('invalid_departure_warnings', len(invalid_departures)),
                        ('signal_detector_warnings', len(detector_warnings))]:
        if count:
            failures.append({'check': name, 'count': count})
    if not interval_complete:
        failures.append({'check': 'requested_interval_not_verified', 'count': 1})
    return {
        'collisions': collision_count, 'teleports': teleports,
        'emergency_stops': emergency_stops, 'emergency_braking': emergency_braking,
        'invalid_route_warnings': invalid_routes,
        'invalid_departure_warnings': invalid_departures,
        'requested_interval_complete': interval_complete,
        'signal_detector_warnings': detector_warnings,
        'final_summary': last.attrib,
        'diagnostic_pass': not failures, 'failed_checks': failures,
        'traffic_system_validated': False,
        'acceptance_scope': 'Necessary numerical and configuration checks only; '
                            'network geometry, signal semantics and demand still require validation.',
    }
