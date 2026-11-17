"""Exploratory timed traffic tracer, prescribed-flow room network and route exposure.

All source strengths and room ventilation are hypotheses. Concentration is a.u.,
not a named pollutant. The indoor formulation follows multizone mass conservation,
not the CONTAM implementation or its pressure-network solver.
"""
import numpy as np
from .near_ground_tracer import PlanarTracer

CASES=('baseline','reduced_idling','reduced_car_trips','peripheral_dropoff')
COMPONENTS=('tailpipe_proxy','non_exhaust_proxy')

def trip_schedule(cfg,case):
    if case not in CASES:raise ValueError('Unknown intervention')
    n=cfg['vehicle_trips'];n=int(round(n*cfg['reduced_trip_fraction'])) if case=='reduced_car_trips' else n
    if n<1:raise ValueError('At least one modeled trip required')
    arrivals=np.linspace(*cfg['arrival_window_s'],n,endpoint=False)
    roll=cfg['rolling_seconds_per_trip']/2
    dwell=cfg['reduced_idle_seconds_per_trip'] if case=='reduced_idling' else cfg['idle_seconds_per_trip']
    return [{'id':f'trip_{i:03d}','approach':[float(a),float(a+roll)],'idle':[float(a+roll),float(a+roll+dwell)],'departure':[float(a+roll+dwell),float(a+2*roll+dwell)]}for i,a in enumerate(arrivals)]

def occupancy(schedule,t0,t1):
    if t1<=t0:raise ValueError('Positive interval required')
    def overlaps(key):return sum(max(0.,min(t1,r[key][1])-max(t0,r[key][0]))for r in schedule)/(t1-t0)
    return overlaps('approach')+overlaps('departure'),overlaps('idle')

def normalized_support(a,invalid,dx):
    w=np.asarray(a,dtype=float).copy();w[invalid]=0
    if not np.isfinite(w).all() or (w<0).any() or w.sum()<=0:raise ValueError('Invalid source support')
    return w/(w.sum()*dx*dx)

def outdoor(uv,invalid,supports,cfg,case,progress=None):
    """Two independently transported components, exact interval-averaged event sources."""
    schedule=trip_schedule(cfg,case);times=np.linspace(0,cfg['duration_s'],cfg['output_frames'])
    models=[PlanarTracer(uv,invalid,cfg['cell_m'],cfg['diffusion_m2_s'])for _ in COMPONENTS]
    roll=normalized_support(supports['rolling'],invalid,cfg['cell_m'])
    idle=normalized_support(supports['peripheral' if case=='peripheral_dropoff' else 'near'],invalid,cfg['cell_m'])
    output=np.empty((2,len(times),*invalid.shape),dtype='<f4');output[:,0]=0
    emitted=np.zeros(2);outflow=np.zeros(2);steps=0;t=0.;max_error=0.;rows=[]
    for k,target in enumerate(times[1:],1):
        while t<target-1e-9:
            dt=min(cfg.get('max_dt_s',2),*(m.dt_max for m in models),target-t)
            moving,standing=occupancy(schedule,t,t+dt)
            src=(roll*(moving*cfg['tailpipe_moving_au_per_vehicle_s'])+idle*(standing*cfg['tailpipe_idle_au_per_vehicle_s']),roll*(moving*cfg['non_exhaust_moving_au_per_vehicle_s']))
            for j,m in enumerate(models):
                r=m.step(dt,src[j]);emitted[j]+=r['emitted'];outflow[j]+=r['outflow'];error=r['mass']-emitted[j]+outflow[j];max_error=max(max_error,abs(error))
                if abs(error)>1e-8*max(1,emitted[j]):raise RuntimeError('Outdoor mass balance failed')
            t+=dt;steps+=1
        for j,m in enumerate(models):output[j,k]=m.c
        rows.append({'time_s':float(target),'emitted_au':emitted.tolist(),'outflow_au':outflow.tolist(),'mass_au':[(m.c.sum()*cfg['cell_m']**2).item()for m in models]})
        if progress and k%20==0:progress(k,len(times),steps)
    return times,output,{'internal_steps':steps,'dt_limit_s':min(m.dt_max for m in models),'max_mass_balance_error_au':max_error,'emitted_au':dict(zip(COMPONENTS,emitted.tolist())),'schedule':schedule,'mass_history':rows}

def room_network(rooms,vent):
    volumes=[]
    for r in rooms:
        p=np.asarray(r['polygon_enu_m']);area=.5*abs(np.sum(p[:,0]*np.roll(p[:,1],-1)-p[:,1]*np.roll(p[:,0],-1)))
        volumes.append(area*vent['assumed_height_m'])
    volumes=np.asarray(volumes);n=len(rooms)
    if not np.isfinite(volumes).all() or np.any(volumes<=0):raise ValueError('Invalid room volumes')
    corridors=[i for i,r in enumerate(rooms)if 'corridor' in r['id']]
    if len(corridors)!=1:raise ValueError('Exactly one conceptual corridor required')
    corridor=corridors[0];ach=np.full(n,vent['outdoor_ach']);ach[corridor]*=vent['corridor_ach_factor']
    if min(vent['outdoor_ach'],vent['deposition_per_hour'],vent['filter_removal_per_hour'],vent['exchange_m3_s'])<0 or not 0<=vent['penetration']<=1:raise ValueError('Invalid ventilation assumptions')
    removal=(ach+vent['deposition_per_hour']+vent['filter_removal_per_hour'])/3600
    A=-np.diag(removal);exchange=vent['exchange_m3_s']
    for i in range(n):
        if i==corridor:continue
        A[i,i]-=exchange/volumes[i];A[i,corridor]+=exchange/volumes[i]
        A[corridor,corridor]-=exchange/volumes[corridor];A[corridor,i]+=exchange/volumes[corridor]
    forcing=ach/3600*vent['penetration']
    return volumes,A,forcing,removal

def indoor(times,boundary,rooms,vent):
    """Euler with positivity-limited substeps and linearly interpolated boundary series.

Boundary is one valid near-school outdoor proxy for all rooms; no invented
facade sampling or indoor pressure/wind prediction is performed.
"""
    times=np.asarray(times,float);boundary=np.asarray(boundary,float)
    if boundary.shape!=(len(times),)or not np.isfinite(boundary).all()or(boundary<0).any()or len(times)<2 or(np.diff(times)<=0).any():raise ValueError('Invalid boundary series')
    V,A,f,removal=room_network(rooms,vent);c=np.zeros(len(rooms));out=[c.copy()];steps=0;incoming=removed=0.;max_error=0.
    dtmax=min(2.,.9/max(float((-np.diag(A)).max()),1e-12))
    for k,(t0,t1)in enumerate(zip(times[:-1],times[1:])):
        t=t0
        while t<t1-1e-9:
            dt=min(dtmax,t1-t);alpha=(t+dt*.5-t0)/(t1-t0);bc=(1-alpha)*boundary[k]+alpha*boundary[k+1]
            incoming+=dt*float(np.dot(V,f))*bc;removed+=dt*float(np.dot(V*removal,c))
            c=c+dt*(A@c+f*bc);steps+=1;t+=dt
            if not np.isfinite(c).all()or c.min()<-1e-12:raise RuntimeError('Room positivity failed')
            error=float(V@c)-incoming+removed;max_error=max(max_error,abs(error))
            if abs(error)>1e-8*max(1.,incoming):raise RuntimeError('Room mass balance failed')
        out.append(c.copy())
    return np.asarray(out),{'volumes_m3':V.tolist(),'internal_steps':steps,'max_mass_balance_error_au_m3':max_error,'incoming_au_m3':incoming,'removed_au_m3':removed}

def sample_field(frames,times,t,xy,origin,dx,invalid):
    """Time interpolation at the containing cell; never snap an invalid sample."""
    ix,iy=np.floor((np.asarray(xy)-origin)/dx).astype(int)
    if t<times[0]or t>times[-1]or not(0<=iy<invalid.shape[0]and 0<=ix<invalid.shape[1])or invalid[iy,ix]:return None
    hi=min(len(times)-1,max(1,int(np.searchsorted(times,t))));lo=hi-1;a=(t-times[lo])/(times[hi]-times[lo])
    return float((1-a)*frames[lo,iy,ix]+a*frames[hi,iy,ix])

def exposure(frames,times,route,wait_point,origin,dx,invalid,start_s,speed,wait_s):
    """Walk then wait as two explicitly separated model segments, with missing coverage."""
    points=np.asarray(route,float);lengths=np.linalg.norm(np.diff(points,axis=0),axis=1);cum=np.r_[0,np.cumsum(lengths)];walk=float(cum[-1]/speed)
    records=[];integral=valid_seconds=0.
    for segment,duration in [('walk',walk),('wait',wait_s)]:
        n=max(1,int(np.ceil(duration/2)));dt=duration/n
        for j in range(n):
            elapsed=(j+.5)*dt;t=start_s+elapsed+(walk if segment=='wait'else 0)
            if segment=='walk':
                distance=elapsed*speed;k=min(len(lengths)-1,int(np.searchsorted(cum,distance,side='right')-1));xy=points[k]+(distance-cum[k])/max(lengths[k],1e-12)*(points[k+1]-points[k])
            else:xy=np.asarray(wait_point)
            value=sample_field(frames,times,t,xy,origin,dx,invalid)
            if value is not None:integral+=value*dt;valid_seconds+=dt
            records.append({'time_s':float(t),'segment':segment,'position_enu_m':xy.tolist(),'concentration_au':value,'duration_s':dt,'cumulative_au_s':integral})
    return {'start_s':start_s,'speed_m_s':speed,'walk_s':walk,'wait_s':wait_s,'end_s':start_s+walk+wait_s,'exposure_au_s':integral,'valid_seconds':valid_seconds,'requested_seconds':walk+wait_s,'valid_fraction':valid_seconds/(walk+wait_s),'series':records,'transition_note':'Walk and waiting point are separate assumed activity segments; their connecting path is unknown and excluded.'}
