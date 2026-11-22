#!/usr/bin/env python3
"""Run a retained full-day solar experiment; never publishes or registers it implicitly."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from urban_flow.physics.solar.day import run
if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--terrain',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--day',default='2026-06-21')
    p.add_argument('--timezone',default='Europe/London')
    p.add_argument('--frames',type=int,default=100)
    p.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    a=p.parse_args(); run(a.terrain,a.output,a.day,a.timezone,a.frames,a.device)
