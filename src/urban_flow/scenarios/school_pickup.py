"""Controlled school pickup source scenarios; arbitrary units, not exposure forecasts."""
import numpy as np
from urban_flow.scenarios.near_ground_tracer import PlanarTracer

CASES=('baseline','reduced_idling','reduced_car_trips','peripheral_dropoff')

def source_rate(weights, invalid, total_rate, cell_m):
    """Normalize an assumed aggregate emission rate onto mapped-road cells."""
    w=np.asarray(weights,dtype=float).copy();w[np.asarray(invalid,bool)]=0
    if not np.isfinite(w).all() or (w<0).any() or total_rate<0:raise ValueError('Invalid source weights/rate')
    if total_rate and not w.any():raise ValueError('No valid mapped road source support')
    return w*(total_rate/(w.sum()*cell_m**2)) if w.any() else w

def scenario_sources(rolling, gate_idle, peripheral_idle, invalid, cfg):
    result={};duration=cfg['duration_s'];dx=cfg['cell_m'];n=cfg['vehicle_trips'];dwell=cfg['idle_seconds_per_trip']
    for name in CASES:
        trips=n*cfg['reduced_trip_fraction'] if name=='reduced_car_trips' else n
        idle=cfg['reduced_idle_seconds_per_trip'] if name=='reduced_idling' else dwell
        roll_rate=trips*cfg['rolling_seconds_per_trip']*cfg['rolling_emission_au_per_vehicle_s']/duration
        idle_rate=trips*idle*cfg['idling_emission_au_per_vehicle_s']/duration
        # Peripheral intervention relocates idling only; unchanged approach traffic is explicit.
        iw=peripheral_idle if name=='peripheral_dropoff' else gate_idle
        result[name]={'rolling':source_rate(rolling,invalid,roll_rate,dx),'idling':source_rate(iw,invalid,idle_rate,dx),'assumed_trips':trips,'assumed_idle_seconds_per_trip':idle,'aggregate_emission_au_s':roll_rate+idle_rate}
    return result

def simulate(uv, invalid, sources, cfg):
    times=np.arange(0,cfg['duration_s']+1e-8,cfg['save_interval_s']);outputs={};diagnostics={}
    for name,parts in sources.items():
        model=PlanarTracer(uv,invalid,cfg['cell_m'],cfg['diffusion_m2_s']);source=parts['rolling']+parts['idling'];frames=[model.c.astype('f4')];rows=[];t=0.;emitted=outflow=0.
        for target in times[1:]:
            while t<target-1e-9:
                dt=min(1.,model.dt_max,target-t);r=model.step(dt,source);t+=dt;emitted+=r['emitted'];outflow+=r['outflow']
            error=r['mass']-emitted+outflow
            if abs(error)>1e-8*max(1,emitted):raise RuntimeError('Mass balance failed')
            frames.append(model.c.astype('f4'));rows.append({'time_s':t,'mass_au':r['mass'],'emitted_au':emitted,'outflow_au':outflow,'balance_error_au':error})
        outputs[name]=np.stack(frames);diagnostics[name]=rows
    return times,outputs,diagnostics

def receptor_series(frames, point, origin_xy, cell_m, invalid):
    """No nearest-air relocation: an unresolved/solid receptor stays explicitly invalid."""
    ix,iy=np.floor((np.asarray(point[:2])-origin_xy)/cell_m).astype(int)
    if not(0<=iy<invalid.shape[0] and 0<=ix<invalid.shape[1]) or invalid[iy,ix]:return {'valid':False,'reason':'Outside crop or inside coarse building mask','requested_enu_m':list(point[:2])}
    return {'valid':True,'requested_enu_m':list(point[:2]),'cell_center_enu_m':(np.asarray(origin_xy)+(np.array([ix,iy])+.5)*cell_m).tolist(),'concentration_au':frames[:,iy,ix].astype(float).tolist()}
