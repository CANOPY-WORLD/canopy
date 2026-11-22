"""Summarize completed demo runs; departure count is not concurrent occupancy."""
import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from traffic.diagnostic_validation import assess_run


def summarize(run):
    validation=assess_run(run)
    steps=ET.parse(run/'summary.xml').getroot().findall('step')
    trips=ET.parse(run/'trips.xml').getroot().findall('tripinfo')
    window=[s for s in steps if 300<=float(s.get('time'))<900]
    def mean(values):return sum(values)/len(values) if values else None
    return {'run':run.name,'diagnostic':validation,
        'peak_concurrent':max(int(s.get('running')) for s in steps),
        'mean_concurrent_300_900_s':mean([int(s.get('running')) for s in window]),
        'peak_insertion_backlog':max(int(s.get('waiting')) for s in steps),
        'peak_halting':max(int(s.get('halting')) for s in steps),
        'arrivals':len(trips),'last_arrival_s':max((float(t.get('arrival')) for t in trips),default=None),
        'mean_trip_duration_s':mean([float(t.get('duration')) for t in trips]),
        'mean_trip_waiting_s':mean([float(t.get('waitingTime')) for t in trips]),
        'mean_route_length_m':mean([float(t.get('routeLength')) for t in trips]),
        'scope':'Synthetic demo diagnostics; no claim of calibrated real-world capacity'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('runs',nargs='+',type=Path);a=p.parse_args()
    print(json.dumps([summarize(run) for run in a.runs],indent=2))
