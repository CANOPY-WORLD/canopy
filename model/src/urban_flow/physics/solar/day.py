"""Reproducible full-local-day experiment using the imported clear-sky kernels.

This streaming experiment is not the prescribed-direction registered solar Method.
Native terrain stays private. Frames retain south-to-north Y and west-to-east X.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
from .model import ShadowNet, HorizonNet, sun_position, ground_irradiance, clear_sky


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def day_samples(day, zone, count, latitude, longitude):
    if count < 2:
        raise ValueError('At least two samples are required')
    d = date.fromisoformat(day)
    tz = ZoneInfo(zone)
    start = datetime.combine(d, time(), tz).astimezone(timezone.utc)
    end = datetime.combine(d + timedelta(days=1), time(), tz).astimezone(timezone.utc)
    frames = []
    for seconds in np.linspace(0, (end-start).total_seconds(), count):
        utc = start + timedelta(seconds=float(seconds))
        hour = utc.hour + utc.minute/60 + (utc.second + utc.microsecond/1e6)/3600
        alt, az = sun_position(latitude, longitude, utc.year, utc.month, utc.day, hour)
        frames.append(dict(seconds=float(seconds), utc=utc.isoformat(), local=utc.astimezone(tz).isoformat(), altitude_deg=alt, azimuth_deg=az))
    return frames


def aggregate(values, valid, factor=2, binary=False):
    ny, nx = values.shape
    shape = (ny//factor, factor, nx//factor, factor)
    count = valid.reshape(shape).sum((1, 3))
    total = np.where(valid, values, 0).reshape(shape).sum((1, 3))
    mean = total / np.maximum(count, 1)
    result = (mean >= .5).astype('u1') if binary else mean.astype('<f2')
    return result, (count == 0).astype('u1')


def run(terrain, output, day='2026-06-21', zone='Europe/London', count=100, device='cuda'):
    import torch
    terrain, output = Path(terrain), Path(output)
    metadata = json.loads((terrain/'metadata.json').read_text())
    grid = metadata['grid']; lon, lat = grid['frame']['origin_lon_lat']
    bed = np.load(terrain/'bed_4m_yx.npy', allow_pickle=False)
    foot = np.load(terrain/'footprint_4m_yx.npy', allow_pickle=False).astype(bool)
    canopy = np.load(terrain/'canopy_4m_yx.npy', allow_pickle=False).astype(bool) & ~foot
    if bed.shape != tuple(grid['shape_yx']) or foot.shape != bed.shape or canopy.shape != bed.shape or not np.isfinite(bed).all() or any(n%2 for n in bed.shape):
        raise ValueError('Invalid or unaligned native geometry')
    frames = day_samples(day, zone, count, lat, lon)
    output.mkdir(parents=True, exist_ok=False)
    native = output/'native'; native.mkdir()
    web = output/'web'; web.mkdir()
    provenance = output/'provenance'; provenance.mkdir()
    inputs = []
    for name in ['metadata.json', 'bed_4m_yx.npy', 'footprint_4m_yx.npy', 'canopy_4m_yx.npy']:
        inputs.append(dict(name=name, sha256=digest(terrain/name)))
        shutil.copy2(terrain/name, provenance/name)
    for name in ['day.py', 'model.py']:
        shutil.copy2(Path(__file__).with_name(name), provenance/name)
    config = dict(day=day, timezone=zone, frames=count, device=device, torch=torch.__version__, numpy=np.__version__, inputs=inputs,
                  cell_m=grid['dx_m'], origin_xy_m=[grid['x0_m'], grid['y0_m']], origin_lon_lat=[lon,lat], vertical_datum='ODN',
                  albedo=.2, canopy_transmittance=.3, horizon_directions=16, horizon_altitudes_deg=list(range(2,90,5)),
                  model='ShadowNet + HorizonNet + ASHRAE monthly clear sky; NOAA solar position',
                  limits=['Clear-sky simulation, not observed weather', '2.5D horizontal surfaces; no facades', 'No obstacles outside the input domain', 'Tree attenuation in canopy cells only', '8 m display averages valid non-building ground cells; binary shadows use majority, ties shaded'])
    (provenance/'request.json').write_text(json.dumps(config,indent=2)+'\n')
    (output/'frames.json').write_text(json.dumps(frames,indent=2)+'\n')
    sn = ShadowNet(bed, grid['dx_m'], device)
    print('Computing 16-direction sky view', flush=True)
    svf, horizon = HorizonNet(sn, n_azimuth=16)()
    np.save(native/'svf.npy', svf.cpu().numpy())
    np.save(native/'horizon.npy', horizon.cpu().numpy().astype('<f2'))
    del horizon
    trans = torch.as_tensor(np.where(canopy,.3,1).astype('f4'),device=device)
    roof = torch.as_tensor(foot,device=device)
    energy = np.zeros_like(bed,dtype='f8'); previous = None
    stats=[]; valid=~foot
    _, invalid = aggregate(bed, valid)
    np.save(web/'invalid.npy',invalid)
    transports = {k:dict(meta=dict(descr=dtype,shape=[count,*invalid.shape],itemsize=size,offset=0,block=invalid.size),total_bytes=count*invalid.size*size,parts=[]) for k,dtype,size in [('ghi','<f2',2),('shadow','|u1',1)]}
    with torch.inference_mode():
        for i,f in enumerate(frames):
            alt,az=f['altitude_deg'],f['azimuth_deg']
            shadow=sn(alt,az)
            ghi,_,_=ground_irradiance(shadow,svf,alt,date.fromisoformat(day).month,trans,.2)
            dni,dhi=clear_sky(alt,date.fromisoformat(day).month)
            open_ghi=dni*np.sin(np.deg2rad(alt))+dhi
            ghi=torch.where(roof,ghi-.2*open_ghi*(1-svf),ghi)
            a=ghi.cpu().numpy(); b=shadow.cpu().numpy().astype('u1')
            if not np.isfinite(a).all() or a.min() < -1e-5 or (alt<=0 and np.any(a)):
                raise ValueError('Nonfinite, negative or nonzero nighttime irradiance')
            if previous is not None:
                energy += (previous.astype('f8')+a)*(f['seconds']-frames[i-1]['seconds'])/2/3.6e6
            previous=a
            # Incremental lossless native retention avoids collecting a 100-frame GPU tensor.
            for name,arr in [('ghi',a.astype('<f4')),('shadow',b)]:
                with gzip.GzipFile(filename=str(native/f'{name}_{i:03d}.npy.gz'),mode='wb',mtime=0) as stream: np.save(stream,arr)
                small,_=aggregate(arr,valid,binary=name=='shadow')
                part=f'{name}_{i:03d}.bin.gz'
                (web/part).write_bytes(gzip.compress(small.tobytes(),compresslevel=6,mtime=0))
                transports[name]['parts'].append(dict(file=part,offset=i*small.nbytes,bytes=small.nbytes))
            stats.append(dict(frame=i,minimum=float(a.min()),maximum=float(a.max()),mean_ground=float(a[valid].mean()),altitude_deg=alt))
            print(f'{i+1}/{count} {f["local"]} max={a.max():.2f} W/m2',flush=True)
    np.save(native/'daily_kwh_m2.npy',energy.astype('<f4'))
    (web/'transport.json').write_text(json.dumps(transports,indent=2)+'\n')
    summary=dict(frames=count,night_frames=sum(f['altitude_deg']<=0 for f in frames),peak_w_m2=max(s['maximum'] for s in stats),mean_ground_daily_kwh_m2=float(energy[valid].mean()),stats=stats)
    (output/'validation.json').write_text(json.dumps(summary,indent=2)+'\n')
    files=[dict(path=p.relative_to(output).as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(output.rglob('*')) if p.is_file()]
    (output/'inventory.json').write_text(json.dumps(dict(kind='canopy.solar-day-experiment',status='complete',files=files),indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='stats'}),flush=True)
    return summary
