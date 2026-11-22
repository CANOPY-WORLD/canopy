"""Prepare explicit, reproducible OSM traffic-demo inputs in a new directory."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from traffic.demo_network import build_network, build_demand, upstream_waiting

p = argparse.ArgumentParser(description=__doc__)
sub = p.add_subparsers(dest='action', required=True)
n = sub.add_parser('network'); n.add_argument('--osm', required=True, type=Path)
n.add_argument('--scenario', required=True, type=Path); n.add_argument('--output', required=True, type=Path)
n.add_argument('--junction-radius',type=float,default=4);n.add_argument('--join-distance',type=float,default=10)
d = sub.add_parser('demand'); d.add_argument('--network', required=True, type=Path)
d.add_argument('--output', required=True, type=Path); d.add_argument('--rate', required=True, type=float)
d.add_argument('--duration', required=True, type=float); d.add_argument('--seed', type=int, default=42)
w = sub.add_parser('upstream-waiting'); w.add_argument('--network', required=True, type=Path); w.add_argument('--output', required=True, type=Path)
a = p.parse_args()
if a.action == 'network': print(build_network(a.osm, a.scenario, a.output,a.junction_radius,a.join_distance))
elif a.action == 'upstream-waiting': print(upstream_waiting(a.network, a.output))
else: print(build_demand(a.network, a.output, a.rate, a.duration, a.seed))
