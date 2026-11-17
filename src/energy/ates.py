"""ATES checkpoint inference and a one-way, explicitly assumed heat-pump adapter.

The fixed upstream injection schedule is never controlled by building demand.
Training-time normalisation uses 365.25-day years; operation/plots use the
recorded timestamps and the upstream 365-day forcing cycle. Do not mix these.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

YEAR = 365 * 86400
TRAINING_TIME_SCALE = 10 * 365.25 * 86400
RATE_SCALE = 1.3888889e-2
WELL_KEYS = ('Wellspacing [m]', 'Well1_depth [m]', 'Well1_screenlength [m]',
             'Well2_depth [m]', 'Well2_screenlength [m]')
DESIGN_KEYS = ('Wellspacing [m]', 'Well1_screenlength [m]',
               'Screenseparation_vertical [m]', 'Aquifer_Kz [mD]')


def heat_dispatch(well_temperature, rates, *, demand_kw, cop, return_deg_c,
                  density=1000., heat_capacity=4185.):
    """Warm-well production only. Surplus rejected; backup is resistance heat.

This is accounting under the fixed ATES schedule, not a coupled reservoir solve.
Raw well temperatures remain unmodified; only usable heat is bounded below by 0.
Pumping power, distribution losses and summer cooling are excluded.
"""
    temp = np.asarray(well_temperature, float); rates = np.asarray(rates, float)
    if temp.ndim != 2 or temp.shape[1] != 2 or temp.shape != rates.shape:
        raise ValueError('Expected [time, cold/warm well] arrays')
    if not np.isfinite(temp).all() or not np.isfinite(rates).all():
        raise ValueError('Nonfinite wells')
    if not all(np.isfinite(v) for v in (demand_kw,cop,return_deg_c,density,heat_capacity)) or demand_kw<0 or cop<=1 or density<=0 or heat_capacity<=0:
        raise ValueError('Invalid heat-pump assumptions')
    production = np.where(rates[:,1]>1e-6,rates[:,1],0.)
    available = density*heat_capacity*production*np.maximum(temp[:,1]-return_deg_c,0)/1000
    delivered = np.minimum(demand_kw,available/(1-1/cop))
    electricity = delivered/cop
    source_used = delivered-electricity
    backup = demand_kw-delivered
    return dict(available_kw=available, source_used_kw=source_used,
                surplus_kw=available-source_used, delivered_kw=delivered,
                hp_electric_kw=electricity, backup_heat_kw=backup,
                backup_electric_kw=backup, total_electric_kw=electricity+backup)


def screen_stencil(field, axes, raw, names):
    """Upstream 8-depth × 4-radius × 4-azimuth stencil, align_corners=True."""
    import torch
    import torch.nn.functional as F
    g={k:float(raw[names.index(k)]) for k in WELL_KEYS}
    points=np.zeros((2,8,4,4,3),dtype=np.float32)
    for w,sign in enumerate((-1,1)):
        depth=g[f'Well{w+1}_depth [m]']; length=g[f'Well{w+1}_screenlength [m]']
        for j,z in enumerate(np.linspace(depth,depth+length,8)):
            for k,r in enumerate((0,16,32,64)):
                points[w,j,k]=[[sign*g['Wellspacing [m]']/2+dx,dy,z] for dx,dy in [(r,0),(-r,0),(0,r),(0,-r)]]
    low=np.array([a[0] for a in axes]); high=np.array([a[-1] for a in axes])
    grid=2*(points-low)/(high-low)-1
    grid=torch.as_tensor(grid[..., [2,1,0]],dtype=field.dtype,device=field.device)
    grid=grid.reshape(1,2,8,16,3).expand(len(field),-1,-1,-1,-1)
    return F.grid_sample(field[:,None],grid,mode='bilinear',padding_mode='border',align_corners=True)[:,0].reshape(len(field),2,8,4,4).mean(-1)


def infer(source, output, device='cpu', threads=4):
    """Use a staged, hash-verified upstream code/weight/scenario snapshot."""
    import torch
    source=Path(source); output=Path(output)
    for name,expected in json.loads((source/'checksums.json').read_text()).items():
        with (source/name).open('rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
        if actual!=expected:raise ValueError('Changed source: '+name)
    spec=importlib.util.spec_from_file_location('ates_upstream',source/'upstream/src/__init__.py',submodule_search_locations=[str(source/'upstream/src')])
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    from ates_upstream.models.unet3d import UNet3d
    from ates_upstream.models.well_readout import PressureReadout, JointTemperatureReadout
    from ates_upstream.config import grid_spec, grid_axes
    torch.set_num_threads(threads)
    ck=torch.load(source/'field.pt',map_location='cpu',weights_only=False)
    args=ck['args']; meta=json.loads((source/'scenario.json').read_text())
    if args['model']!='unet' or args.get('roi') or args['grid']!='fine8':raise ValueError('This adapter expects the confirmed fine8 UNet without ROI')
    raw=np.asarray(meta['params'],float); names=meta['param_names'];times=np.asarray(meta['times_s'],float)
    if len(raw)!=57 or len(names)!=57 or not np.isfinite(raw).all() or not np.isfinite(times).all() or len(times)!=241 or not np.all(np.diff(times)>0):raise ValueError('Invalid recorded input')
    mean,std=ck['param_stats'];mean=np.asarray(mean);std=np.asarray(std)
    if not np.isfinite(mean).all() or not np.isfinite(std).all() or (std<=0).any():raise ValueError('Invalid training normalisation')
    wg=dict(p_mean=mean.tolist(),p_std=std.tolist(),idx=[names.index(k)for k in WELL_KEYS])
    grid=grid_spec(args['grid']);axes=grid_axes(args['grid'])
    model=UNet3d(57,grid['shape'],base=args['base'],levels=args['levels'],cond_dim=args['cond_dim'],well_geom=wg,bounds=grid['bounds'])
    model.load_state_dict(ck['model'],strict=True);model.to(device).eval()
    heads=[]
    for branch,cls in [('temperature',JointTemperatureReadout),('pressure',PressureReadout)]:
        c=torch.load(source/(branch+'.pt'),map_location='cpu',weights_only=False)
        h=cls(hidden=c['args']['hidden']);h.load_state_dict(c['model'],strict=True);h.to(device).eval();heads.append((h,c))
    output.mkdir(parents=True,exist_ok=False)
    fields=np.lib.format.open_memmap(output/'temperature.npy',mode='w+',dtype='<f4',shape=(len(times),*grid['shape']))
    wells=np.zeros((len(times),8),dtype='<f4'); wells[:,:2]=np.asarray(meta['rates_m3_s'])
    params=torch.tensor((raw-mean)/std,dtype=torch.float32,device=device)[None]
    design=torch.tensor([[raw[names.index(k)]for k in DESIGN_KEYS]],dtype=torch.float32,device=device)
    with torch.inference_mode():
        for i,t in enumerate(times):
            f=model(params,torch.tensor([t/TRAINING_TIME_SCALE],dtype=torch.float32,device=device))
            f=f*float(ck['field_stats'][1])+float(ck['field_stats'][0])
            stencil=screen_stencil(f,axes,raw,names)[None]
            rate=torch.tensor([[wells[i,0]/RATE_SCALE]],dtype=torch.float32,device=device)
            for j,(h,c)in enumerate(heads):
                y=h(stencil,design,rate) if j==0 else h(design,rate)
                y=y*torch.as_tensor(c['target_std'],device=device)+torch.as_tensor(c['target_mean'],device=device)
                wells[i,2:4] = y.cpu().numpy()[0,0] if j==0 else wells[i,2:4]
                if j==1:wells[i,4:]=y.cpu().numpy()[0,0]
            a=f[0].cpu().numpy()
            if not np.isfinite(a).all() or not np.isfinite(wells[i]).all():raise ValueError('Nonfinite inference')
            fields[i]=a
            if i%24==0:print(f'ATES {i}/{len(times)-1}, t={t/YEAR:.3f} model years',flush=True)
    fields.flush(); np.save(output/'wells.npy',wells)
    for key,a in zip(('x','y','z'),axes):np.save(output/(key+'.npy'),a)
    np.save(output/'times.npy',times)
    report=dict(scenario_id=meta['scenario_id'],temperature_shape=list(fields.shape),field_range_deg_c=[float(fields.min()),float(fields.max())],trainable_parameters=sum(p.numel()for p in model.parameters()),device=device,torch_version=torch.__version__,training_time_scale_s=TRAINING_TIME_SCALE,forcing_year_s=YEAR,rate_source='Recorded prescribed rates copied unchanged; not predicted',source=str(source.resolve()))
    (output/'inference.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--device',default='cpu');a=p.parse_args();infer(a.source,a.output,a.device)
