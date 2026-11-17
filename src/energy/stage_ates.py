"""Read-only authenticated acquisition of one ATES checkpoint/scenario bundle."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tarfile

from common.storage import Storage


def main():
    p=argparse.ArgumentParser();p.add_argument('--host',default='euyueyanl@efp-login.vega.izum.si');p.add_argument('--identity',type=Path,required=True);p.add_argument('--certificate',type=Path,required=True);p.add_argument('--scenario',type=int,default=1002);p.add_argument('--destination',type=Path,required=True);a=p.parse_args()
    root='/ceph/hpc/data/d2026d08-025-users/Geothermal_surrogate'
    ssh=['ssh','-i',str(a.identity),'-o','CertificateFile='+str(a.certificate),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','ConnectTimeout=15',a.host]
    subprocess.run(ssh+['test -r '+shlex.quote(root+'/expout/confirmation_20260929/field/best.pt')],check=True)
    a.destination.mkdir(parents=True,exist_ok=False)
    for rel,name in [('field/best.pt','field.pt'),('readout/temperature.pt','temperature.pt'),('readout/pressure.pt','pressure.pt'),('protocol.json','protocol.json'),('verification.json','upstream_verification.json')]:
        with (a.destination/name).open('xb') as f:
            subprocess.run(ssh+['cat '+shlex.quote(root+'/expout/confirmation_20260929/'+rel)],stdout=f,check=True)
    with (a.destination/'upstream.tar').open('xb') as f:
        subprocess.run(ssh+['tar -C '+shlex.quote(root)+' -cf - src DATA_ATES.md docs/MODELS.md'],stdout=f,check=True)
    with tarfile.open(a.destination/'upstream.tar') as archive:
        archive.extractall(a.destination/'upstream',filter='data')
    script=f'''import h5py,json
from pathlib import Path
p=Path({root!r})/'data/grid_ates_8m/scenario{a.scenario}.h5'
with h5py.File(p,'r') as f:
 names=f['params'].attrs.get('param_names',f.attrs.get('param_names'))
 if isinstance(names,bytes):names=names.decode()
 if isinstance(names,str):names=json.loads(names)
 names=[x.decode() if isinstance(x,bytes) else str(x) for x in names]
 print(json.dumps(dict(scenario_id={a.scenario},param_names=names,params=f['params'][:].tolist(),times_s=f['times'][:].tolist(),rates_m3_s=f['well_outputs'][:,:2].tolist(),reference_wells=f['well_outputs'][:].tolist())))
'''
    command='module load h5py/3.9.0-foss-2023a >/dev/null 2>&1 && python3 -'
    result=subprocess.run(ssh+[command],input=script,text=True,capture_output=True,check=True)
    data=json.loads(result.stdout)
    (a.destination/'scenario.json').write_text(json.dumps(data,indent=2)+'\n')
    info=dict(remote_host=a.host,remote_root=root,scenario=a.scenario,retrieved_at=datetime.now(timezone.utc).isoformat(),placement='No geographic registration in upstream model; city placement is hypothetical')
    (a.destination/'acquisition.json').write_text(json.dumps(info,indent=2)+'\n')
    sums={}
    for file in sorted(a.destination.rglob('*')):
        if file.is_file():
            with file.open('rb') as f:sums[str(file.relative_to(a.destination))]=hashlib.file_digest(f,'sha256').hexdigest()
    (a.destination/'checksums.json').write_text(json.dumps(sums,indent=2)+'\n')
    print(a.destination)


if __name__=='__main__':main()
