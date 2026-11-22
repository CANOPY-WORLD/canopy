"""Explicit retained-input SUMO diagnostic; never overwrites a run or an Asset."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from traffic.diagnostic_validation import assess_run


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--network',type=Path,required=True)
    p.add_argument('--routes',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--begin',type=float,required=True)
    p.add_argument('--end',type=float,required=True)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--lane-mode',choices=['sublane','continuous'],default='sublane',help='Sublane lateral freedom or lane-based 2 s continuous lane changes')
    p.add_argument('--guard-junctions',type=Path,help='JSON array of explicitly guarded junction IDs; omitted means native SUMO')
    a=p.parse_args()
    if not all(math.isfinite(v) for v in (a.begin,a.end)) or not a.end>a.begin:
        p.error('begin/end must be finite and end must exceed begin')
    guards=json.loads(a.guard_junctions.read_text()) if a.guard_junctions else []
    if not isinstance(guards,list) or not all(isinstance(v,str) for v in guards):p.error('guard-junctions must be a JSON array of strings')
    if not a.network.is_file() or not a.routes.is_file():p.error('network and routes must exist')
    import sumo
    output=a.output.resolve(); output.mkdir(parents=True,exist_ok=False)
    names=[];inputs=[]
    for kind,source in [('network',a.network),('routes',a.routes)]:
        name=kind+('.xml.gz' if source.suffix=='.gz' else '.xml');destination=output/name
        shutil.copy2(source,destination);names.append(str(destination));inputs.append({'file':name,'sha256':digest(destination)})
    command=[str(Path(sumo.SUMO_HOME)/'bin/sumo'),'-n',names[0],'-r',names[1],
      '--begin',str(a.begin),'--end',str(a.end),'--step-length','.1','--seed',str(a.seed),
      '--time-to-teleport','-1','--collision.action','warn','--collision.check-junctions','true',
      '--fcd-output',str(output/'traffic.fcd.xml.gz'),
      '--device.fcd.period','.1','--fcd-output.acceleration','true',
      '--summary-output',str(output/'summary.xml'),'--collision-output',str(output/'collisions.xml'),
      '--tripinfo-output',str(output/'trips.xml'),'--no-step-log','--duration-log.statistics','true','--precision','4']
    command += ['--lateral-resolution','.4'] if a.lane_mode=='sublane' else ['--lanechange.duration','2']
    controller=Path(__file__).resolve().parents[1]/'src/traffic/junction_reservations.py'
    config={'command':command,'guarded_junctions':guards,'inputs':inputs,
      'runner_sha256':digest(Path(__file__)),
      'validator_sha256':digest(Path(__file__).resolve().parents[1]/'src/traffic/diagnostic_validation.py'),
      'controller_sha256':digest(controller) if guards else None,
      'solver_version':subprocess.check_output([command[0],'--version'],text=True).splitlines()[0],
      'limitations':(['Experimental junction guards; not actual London signal operation'] if guards else [])+['Exact native input hashes retained; demand calibration not inferred','A zero-collision run does not establish safety for other demands or seeds']}
    config_path=output/'config.json';config_path.write_text(json.dumps(config,indent=2)+'\n')
    launch=[sys.executable,str(controller),str(config_path)] if guards else command
    with (output/'sumo.log').open('w') as log:subprocess.run(launch,stdout=log,stderr=log,check=True)
    report=assess_run(output)
    report['limitations']=config['limitations']
    (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    return 0 if report['diagnostic_pass'] else 2

if __name__=='__main__':sys.exit(main())
