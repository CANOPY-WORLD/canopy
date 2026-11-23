"""Verify, build and rerun a portable recorded LISFLOOD-FP case.

This case utility is not a registered Canopy Method and never changes a Scenario.
Native results retain their original CRS, datum and actual solver timestamps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath

SCHEMA = 'lisflood-fp-recorded-case/1'
INPUTS = ('DSM_final.dem', 'normal.start', 'rain.nc', 'rain.par', 'open.bci', 'monitor.stage', 'rainfall.csv')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bounded(root, name):
    if not isinstance(name, str) or not name or '\\' in name:
        raise ValueError(f'Invalid case path: {name!r}')
    parts = name.split('/')
    if PurePosixPath(name).is_absolute() or any(p in ('', '.', '..') for p in parts):
        raise ValueError(f'Invalid case path: {name!r}')
    path = root.joinpath(*parts)
    if any(p.is_symlink() for p in [path, *path.parents] if p != root and p.is_relative_to(root)):
        raise ValueError(f'Symlinks are not portable case files: {name}')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Case path escapes root: {name}')
    return path


def verify(case):
    case = Path(case).resolve()
    manifest = json.loads((case / 'reproduction.json').read_text())
    if manifest.get('schema') != SCHEMA:
        raise ValueError('Unsupported recorded-case schema')
    names = set()
    for record in manifest['files']:
        name = record['path']
        if name in names or name == 'reproduction.json':
            raise ValueError(f'Duplicate or self-referential case entry: {name}')
        names.add(name)
        path = bounded(case, name)
        if not path.is_file() or path.stat().st_size != record['bytes'] or digest(path) != record['sha256']:
            raise ValueError(f'Case checksum/size mismatch: {name}')
    actual = {p.relative_to(case).as_posix() for p in case.rglob('*') if p.is_file() or p.is_symlink()}
    if actual != names | {'reproduction.json'}:
        raise ValueError('Unlisted or missing case files')
    for name in INPUTS:
        if f'inputs/{name}' not in names:
            raise ValueError(f'Missing native input: {name}')
    if 'solver/acc_conservation.patch' not in names:
        raise ValueError('Missing recorded solver correction')
    return manifest


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build(case, work, arch, prefix=None, upstream=None, jobs=4):
    case = Path(case).resolve()
    manifest = verify(case)
    work = Path(work).resolve()
    if work.exists() or work.is_relative_to(case):
        raise ValueError('Choose a new build directory outside the input case')
    if not re.fullmatch(r'[0-9]+(?:;[0-9]+)*', arch) or jobs < 1:
        raise ValueError('Use explicit numeric CUDA architectures and positive jobs')
    work.mkdir(parents=True)
    repository = work / 'upstream'
    upstream_url = manifest['solver']['repository']
    revision = manifest['solver']['revision']
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('The upstream revision must be pinned')
    if upstream:
        upstream = Path(upstream).resolve()
        actual = subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != revision:
            raise ValueError('Local upstream checkout has the wrong revision')
        subprocess.run(['git', 'clone', '--no-hardlinks', '--no-checkout', str(upstream), str(repository)], check=True)
    else:
        subprocess.run(['git', 'init', str(repository)], check=True)
        subprocess.run(['git', '-C', str(repository), 'fetch', '--depth', '1', upstream_url, revision], check=True)
    subprocess.run(['git', '-C', str(repository), 'checkout', '--detach', revision], check=True)
    source = repository / 'source'
    patch = case / 'solver/acc_conservation.patch'
    for name, record in manifest['solver']['source_hashes'].items():
        if digest(bounded(source, name)) != record['original_sha256']:
            raise ValueError(f'Unexpected upstream source: {name}')
    # The recorded patch was generated through Python text IO. Match its LF
    # conversion only after verifying the original upstream CRLF bytes.
    for name in manifest['solver']['source_hashes']:
        path = bounded(source, name)
        path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
    subprocess.run(['git', 'apply', '--check', str(patch)], cwd=source, check=True)
    subprocess.run(['git', 'apply', str(patch)], cwd=source, check=True)
    for name, record in manifest['solver']['source_hashes'].items():
        if digest(bounded(source, name)) != record['patched_sha256']:
            raise ValueError(f'Patched source does not match the accepted solver: {name}')
    if digest(source / 'config.default.cmake') != manifest['solver']['config_sha256']:
        raise ValueError('FP64 configuration does not match the accepted solver')
    cuda = shutil.which('nvcc')
    if prefix:
        prefix = Path(prefix).resolve()
        candidate = prefix / 'bin/nvcc'
        if candidate.is_file():
            cuda = str(candidate)
    if not cuda:
        raise ValueError('CUDA nvcc is required; CPU parity is not claimed for this case')
    command = ['cmake', '-S', str(source), '-B', str(work / 'build'), '-DCMAKE_BUILD_TYPE=Release',
               f'-DCMAKE_CUDA_ARCHITECTURES={arch}', f'-DCMAKE_CUDA_COMPILER={cuda}']
    cc = os.environ.get('CC', shutil.which('gcc'))
    cxx = os.environ.get('CXX', shutil.which('g++'))
    if not cc or not cxx:
        raise ValueError('Set CC and CXX to CUDA-compatible host compilers')
    command += [f'-DCMAKE_C_COMPILER={cc}', f'-DCMAKE_CXX_COMPILER={cxx}',
                f'-DCMAKE_CUDA_HOST_COMPILER={cxx}']
    if prefix:
        command += [f'-DCMAKE_PREFIX_PATH={prefix}', f'-DCUDAToolkit_ROOT={prefix}',
                    f'-DNUMA_ROOT_DIR={prefix}', f'-DCMAKE_BUILD_RPATH={prefix / "lib"}']
    subprocess.run(command, check=True)
    subprocess.run(['cmake', '--build', str(work / 'build'), '--parallel', str(jobs)], check=True)
    binary = work / 'build/lisflood'
    record = {'schema': 'lisflood-fp-build/1', 'upstream_revision': revision,
              'patch_sha256': digest(patch), 'config_sha256': digest(source / 'config.default.cmake'),
              'source_hashes': manifest['solver']['source_hashes'], 'binary_sha256': digest(binary),
              'cuda_architectures': arch, 'configure_command': command}
    write_json(work / 'build-record.json', record)
    return {'binary': str(binary), 'record': str(work / 'build-record.json')}


def check_binary(case, manifest, binary, build_record=None):
    actual = digest(binary)
    if actual == manifest['solver']['reference_binary_sha256']:
        return actual
    if build_record is None:
        raise ValueError('Binary differs from the recorded build; supply its verified --build-record')
    record = json.loads(Path(build_record).read_text())
    expected = {'schema': 'lisflood-fp-build/1', 'upstream_revision': manifest['solver']['revision'],
                'patch_sha256': digest(case / 'solver/acc_conservation.patch'),
                'config_sha256': manifest['solver']['config_sha256'],
                'source_hashes': manifest['solver']['source_hashes'], 'binary_sha256': actual}
    for key, value in expected.items():
        if record.get(key) != value:
            raise ValueError(f'Incompatible solver build record: {key}')
    return actual


def run(case, output, binary, build_record=None, seconds=None, dry_run=False):
    case, output, binary = map(lambda p: Path(p).resolve(), (case, output, binary))
    manifest = verify(case)
    if output.exists() or output.is_relative_to(case):
        raise ValueError('Choose a new run directory outside the immutable input case')
    binary_hash = check_binary(case, manifest, binary, build_record)
    duration = manifest['simulation_seconds'] if seconds is None else seconds
    if not 0 < duration <= manifest['simulation_seconds']:
        raise ValueError('Run duration must be positive and no longer than the recorded event')
    parameters = (case / 'inputs/rain.par').read_text()
    replacements = {'dirroot': 'results', 'sim_time': str(duration)}
    values = {}
    lines = []
    for line in parameters.splitlines():
        parts = line.split(maxsplit=1)
        if parts:
            key = parts[0]
            if key in values:
                raise ValueError(f'Duplicate parameter: {key}')
            values[key] = parts[1] if len(parts) == 2 else None
            if key in replacements:
                line = f'{key} {replacements[key]}'
        lines.append(line)
    expected = {'DEMfile':'DSM_final.dem', 'startfile':'normal.start', 'dynamicrainfile':'rain.nc',
                'bcifile':'open.bci', 'stagefile':'monitor.stage', 'resroot':'rain'}
    if any(values.get(k) != v for k, v in expected.items()) or 'cuda' not in values or 'acceleration' not in values:
        raise ValueError('Unexpected native input references or solver mode')
    report = {'case_id':manifest['case_id'], 'reproduction_sha256':digest(case / 'reproduction.json'),
              'binary_sha256':binary_hash, 'requested_seconds':duration,
              'is_full_event':duration == manifest['simulation_seconds'], 'numerical_acceptance':'not_checked',
              'command':[str(binary), '-v', 'rain.par']}
    if dry_run:
        return report
    output.mkdir(parents=True)
    for name in INPUTS:
        if name != 'rain.par':
            shutil.copy2(case / 'inputs' / name, output / name)
    (output / 'rain.par').write_text('\n'.join(lines) + '\n')
    report['status'] = 'running'
    write_json(output / 'run-record.json', report)
    with (output / 'rain.log').open('w') as log:
        try:
            process = subprocess.run(report['command'], cwd=output, stdout=log, stderr=subprocess.STDOUT)
        except BaseException:
            report['status'] = 'interrupted'
            write_json(output / 'run-record.json', report)
            raise
    report.update(status='finished' if process.returncode == 0 else 'failed', exit_code=process.returncode,
                  parameters_sha256=digest(output / 'rain.par'), log_sha256=digest(output / 'rain.log'))
    write_json(output / 'run-record.json', report)
    if process.returncode:
        raise RuntimeError(f'LISFLOOD-FP failed; inspect {output / "rain.log"}')
    return report


def audit(case, output):
    # The accepted ACC order applies rain using the previous step's dt; the first
    # increment is zero. Preserve that ordering rather than nominal rain totals.
    import numpy as np
    import rasterio
    from netCDF4 import Dataset
    case, output = Path(case).resolve(), Path(output).resolve()
    manifest = verify(case)
    record = json.loads((output / 'run-record.json').read_text())
    if record.get('status') != 'finished' or record['reproduction_sha256'] != digest(case / 'reproduction.json'):
        raise ValueError('Run is incomplete or belongs to a different input case')
    for name in INPUTS:
        if name != 'rain.par' and digest(output / name) != digest(case / 'inputs' / name):
            raise ValueError(f'Run input changed: {name}')
    if digest(output / 'rain.log') != record['log_sha256'] or digest(output / 'rain.par') != record['parameters_sha256']:
        raise ValueError('Recorded log or parameters changed')
    text = (output / 'rain.log').read_text()
    if 'ACC shared-face donor limiter and boundary volume budget enabled; double precision' not in text:
        raise ValueError('Expected corrected double-precision ACC marker is absent')
    steps = np.array(re.findall(r'^t=([\deE+\-.]+)\s+dt=([\deE+\-.]+)$',text,re.M),float)
    if steps.ndim != 2 or len(steps) == 0 or not np.isfinite(steps).all() or np.any(steps[:,1] <= 0):
        raise ValueError('Missing or invalid precise ACC timestep records')
    t, dt = steps.T
    ends = t + dt
    if ends[-1] < record['requested_seconds']:
        raise ValueError('Solver did not reach the requested duration')
    with Dataset(case / 'inputs/rain.nc') as ds:
        hours = np.asarray(ds['time'][:],float)
        rainfall = np.asarray(ds['rainfall_depth'][:],float)
    depth = rainfall[:,0,0]
    if not np.allclose(rainfall, depth[:,None,None], rtol=0, atol=0):
        raise ValueError('This independent audit supports spatially uniform rainfall only')
    duration = np.r_[np.diff(hours), hours[-1]-hours[-2]] * 3600
    idx = np.searchsorted(hours,t/3600,side='right')-1
    if (idx < 0).any() or (idx >= len(depth)).any() or (duration <= 0).any():
        raise ValueError('Invalid rainfall clock')
    with rasterio.Env(AAIGRID_DATATYPE='Float64'):
        with rasterio.open(case / 'inputs/normal.start') as ds:
            h0=ds.read(1); cell_area=abs(ds.transform.a*ds.transform.e); shape=ds.shape
    v0=float(h0.sum(dtype=np.float64)*cell_area)
    cumulative=np.cumsum((depth/duration/1000)[idx]*np.r_[0.,dt[:-1]])*h0.size*cell_area
    saved=np.array(re.findall(r'Writing snapshot at t=([\deE+\-.]+)',text),float)
    if not len(saved):
        raise ValueError('No saved depth states to audit')
    budget=np.atleast_2d(np.loadtxt(output/'results/rain.boundary_budget.csv',delimiter=',',skiprows=1))
    if budget.shape[1] != 3 or not np.isfinite(budget).all() or np.any(budget[:, 1:] < 0):
        raise ValueError('Invalid boundary-volume records')
    rows=[]
    for k,time in enumerate(saved):
        i=int(np.argmin(abs(ends-time)))
        if abs(ends[i]-time)>1e-5:
            raise ValueError('Depth snapshot does not match a solver step')
        b=budget[np.argmin(abs(budget[:,0]-ends[i]))]
        if abs(b[0]-ends[i])>1e-6:
            raise ValueError('Boundary budget does not match a depth snapshot')
        with rasterio.Env(AAIGRID_DATATYPE='Float64'):
            with rasterio.open(output/f'results/rain-{k:04d}.wd') as ds:
                h=ds.read(1)
        if h.shape != shape or not np.isfinite(h).all() or float(h.min())<0:
            raise ValueError('Invalid or mismatched water-depth field')
        volume=float(h.sum(dtype=np.float64)*cell_area)
        residual=volume-v0-cumulative[i]-b[1]+b[2]
        rows.append({'time_s':float(ends[i]),'volume_m3':volume,'rain_m3':float(cumulative[i]),
                     'boundary_in_m3':float(b[1]),'boundary_out_m3':float(b[2]),'residual_m3':float(residual),
                     'max_depth_m':float(h.max())})
    worst=max(abs(r['residual_m3']) for r in rows)
    report={'passed':worst < 0.1,'absolute_tolerance_m3':0.1,'max_absolute_residual_m3':worst,
            'completed_seconds':float(ends[-1]),'snapshots':rows,
            'scope':'Numerical consistency; not calibration or observed-depth validation.'}
    write_json(output/'verification.json',report)
    if not report['passed']:
        raise ValueError('Independent water balance failed; see verification.json')
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('verify','build','run','audit'):
        p=sub.add_parser(name);p.add_argument('--case',type=Path,required=True)
        if name=='build':
            p.add_argument('--work-dir',type=Path,required=True);p.add_argument('--cuda-arch',required=True)
            p.add_argument('--dependency-prefix',type=Path);p.add_argument('--upstream-checkout',type=Path)
            p.add_argument('--jobs',type=int,default=4)
        elif name=='run':
            p.add_argument('--output',type=Path,required=True);p.add_argument('--binary',type=Path,required=True)
            p.add_argument('--build-record',type=Path);p.add_argument('--seconds',type=float)
            p.add_argument('--dry-run',action='store_true')
        elif name=='audit':
            p.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=='verify':
            m=verify(args.case);result={'case_id':m['case_id'],'verified_files':len(m['files'])}
        elif args.command=='build':
            result=build(args.case,args.work_dir,args.cuda_arch,args.dependency_prefix,args.upstream_checkout,args.jobs)
        elif args.command=='run':
            result=run(args.case,args.output,args.binary,args.build_record,args.seconds,args.dry_run)
        else:
            result=audit(args.case,args.output)
    except (ValueError, OSError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1,f'{error}\n')
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
