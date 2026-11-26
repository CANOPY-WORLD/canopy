"""Conditional private CVAE replay with explicitly estimated current-city inputs."""
import copy
import math
import numpy as np
from .city_alignment import CityFields


class EstimatedCityFields(CityFields):
    def estimate(self, key, x, y, seconds, radius_m):
        raw=self.sample(key,x,y,seconds)
        if raw is not None:
            return raw,dict(method='native_cell',distance_m=0.)
        m=self.metadata[key];t=seconds+m.get('clock_offset_s',0)
        if not m['times_s'][0]<=t<=m['times_s'][-1]:
            return None,dict(method='outside_time_coverage')
        i=math.floor((x-m['origin_xy_m'][0])/m['cell_m']);j=math.floor((y-m['origin_xy_m'][1])/m['cell_m'])
        h,w=m['shape']
        if not 0<=i<w or not 0<=j<h:
            return None,dict(method='outside_spatial_coverage')
        radius=math.ceil(radius_m/m['cell_m'])+1;candidates=[]
        for yy in range(max(0,j-radius),min(h,j+radius+1)):
            for xx in range(max(0,i-radius),min(w,i+radius+1)):
                if self.mask(key)[yy,xx]:continue
                px=m['origin_xy_m'][0]+(xx+.5)*m['cell_m'];py=m['origin_xy_m'][1]+(yy+.5)*m['cell_m']
                distance=math.hypot(px-x,py-y)
                if distance<=radius_m:candidates.append((distance,yy,xx,px,py))
        donors=[]
        interpolate=getattr(self,'estimation_method','nearest')=='idw4' and key in ('pmx','sunlight')
        for distance,yy,xx,px,py in sorted(candidates):
            value=self.sample(key,px,py,seconds)
            if value is not None:
                if not interpolate:
                    return value,dict(method='nearby_valid_cell_estimate',distance_m=distance,donor_cell_yx=[yy,xx],donor_xy_m=[px,py])
                donors.append(dict(value=float(value),distance_m=distance,cell_yx=[yy,xx],xy_m=[px,py]))
                if len(donors)==4:break
        if donors:
            weights=np.array([1/max(d['distance_m'],1e-9)**2 for d in donors]);weights/=weights.sum()
            for d,w in zip(donors,weights):d['weight']=float(w)
            return float(sum(d['value']*d['weight'] for d in donors)),dict(
                method='inverse_distance_weighted_estimate' if len(donors)>1 else 'single_donor_estimate',
                distance_m=max(d['distance_m'] for d in donors),donors=donors,limit_m=radius_m,
                source_seconds=float(t),clock_offset_s=m.get('clock_offset_s',0),
                limitation='Health-only spatial estimate; local gradients and shadow boundaries are not resolved')
        return None,dict(method='no_valid_donor_within_limit',limit_m=radius_m)


class MissingCityInput(ValueError):
    def __init__(self, missing, point, seconds, audits, policy):
        self.details=dict(fields=missing,world_seconds=float(seconds),xy_m=[float(v) for v in point[:2]],
                          estimates={key:audits[key] for key in missing})
        labels={'pmx':'pollution','temperature':'temperature','sunlight':'sunlight'}
        limits={'pmx':policy['max_pmx_fill_m'],'temperature':policy['max_temperature_fill_m'],'sunlight':policy.get('max_sunlight_fill_m',0)}
        description=', '.join(f"{labels[k]} (no valid input within {limits[k]:g} m)" for k in missing)
        super().__init__(f"Environmental coverage gap: {description} at Health time {seconds:g} s, "
                         f"map position {point[0]:.1f} E, {point[1]:.1f} N. "
                         'The road is connected, but breathing and health scores need these inputs. '
                         'Repeating the time sequence cannot fill a spatial gap.')


def model_inputs(fields, point, world, policy):
    pm,audit_pm=fields.estimate('pmx',*point[:2],world,policy['max_pmx_fill_m'])
    air,audit_air=fields.estimate('temperature',*point[:2],world,policy['max_temperature_fill_m'])
    missing=[key for key,value in [('pmx',pm),('temperature',air)] if value is None]
    if missing:
        raise MissingCityInput(missing,point,world,{'pmx':audit_pm,'temperature':audit_air},policy)
    proxy=policy['assumed_background_pm25_ug_m3']+policy['pmx_to_pm25_proxy_fraction']*pm
    return proxy,air,audit_pm,audit_air


def check_model_coverage(recording, fields, policy, checkpoint=lambda:None):
    """Check the actual output and integration samples before loading private state."""
    rows=recording['samples'];end=max(recording['duration_s'],policy['followup_until_elapsed_s'])
    original_times=np.asarray([r['seconds'] for r in rows])
    times=set(original_times.tolist()+np.arange(0,end,1.).tolist()+[end])
    elapsed=0.
    boundaries=sorted({e['end'] for e in recording.get('route_timeline',[])})
    while elapsed<end-1e-8:
        phase=(policy.get('breathing_history_offset_s',0)+recording['departure_s']+elapsed)%300
        boundary=next((t for t in boundaries if t>elapsed+1e-8),end)
        duration=min(2.-elapsed%2,300.-phase,end-elapsed,boundary-elapsed)
        times.add(elapsed+duration/2);elapsed+=duration
    for t in sorted(times):
        checkpoint()
        point=position_at(rows,t,original_times)['enu_m'];world=recording['departure_s']+t
        model_inputs(fields,point,world,policy)
        if policy.get('max_sunlight_fill_m',0)>0:
            solar_input(fields,point,world,policy)


def solar_input(fields,point,world,policy):
    radius=policy.get('max_sunlight_fill_m',0)
    if radius<=0:return fields.sample('sunlight',*point[:2],world),dict(method='native_only')
    value,audit=fields.estimate('sunlight',*point[:2],world,radius)
    if value is None:raise MissingCityInput(['sunlight'],point,world,{'sunlight':audit},policy)
    return value,audit


def health_details(pollution, air, sunlight, breathing, reference, warming=6.):
    """The original local display equation, not a calibrated clinical risk model."""
    values=[pollution,air,sunlight,breathing,reference['lower'],reference['upper'],reference['scale']]
    if any(v is None or not np.isfinite(v) for v in values) or pollution<0 or breathing<=0 or reference['lower']<=0 or reference['upper']<reference['lower'] or reference['scale']<=0:
        return None
    thermal=air+warming*min(1.5,max(0.,sunlight/800))
    p=pollution/15;t=max(18-thermal,thermal-26,0)/8
    b=1.5*max(reference['lower']-breathing,breathing-reference['upper'],0)/reference['scale']
    burdens={'pollution':.35*p*p,'temperature':.15*t*t,'breathing':.50*b*b}
    total=sum(burdens.values());score=100*math.exp(-math.log(100/90)*total)
    return dict(score=score,thermal_proxy=thermal,contributions={k:(100-score)*v/total if total else 0. for k,v in burdens.items()})


def position_at(rows,seconds,times=None):
    if times is None:times=[s['seconds'] for s in rows]
    hi=int(np.searchsorted(times,seconds))
    if hi==len(rows):return rows[-1]  # Explicit stationary follow-up only.
    if times[hi]==seconds:return rows[hi]
    lo=hi-1;f=(seconds-times[lo])/(times[hi]-times[lo]);a,b=rows[lo],rows[hi]
    return {key:np.asarray(a[key])*(1-f)+np.asarray(b[key])*f for key in ['enu_m','scene_m']}


def evaluate(recording, fields, runtime, baseline, policy, checkpoint=lambda:None):
    from .conditional_breathing import BreathingCosts
    original=recording['samples'];departure=float(recording['departure_s']);arrival=recording['duration_s']
    original_times=np.asarray([s['seconds'] for s in original])
    end=max(arrival,float(policy['followup_until_elapsed_s']))
    horizon=getattr(fields,'horizon_s',min(fields.metadata[k]['times_s'][-1] for k in ['pmx','temperature']))
    if departure+end>horizon:
        raise ValueError('Conditional inference cannot exceed the declared Health time coverage')
    offset=policy['breathing_history_offset_s']+departure
    if offset+end>max(runtime.states):raise ValueError('Outside private template coverage')
    costs=BreathingCosts(departure,{},policy,runtime,baseline)
    def inputs_at(point,world):
        return model_inputs(fields,point,world,policy)
    # Reuse the original model transition, two-second quadrature and private
    # history/template clock. No new planner and no higher-frequency CVAE step.
    costs.pollution_sampler=lambda p,t:inputs_at(p,t)[0]
    costs.temperature_sampler=lambda p,t:inputs_at(p,t)[1]
    costs.trace=[costs.prediction(costs.initial,0.)]
    state=costs.initial;elapsed=0.;total_exposure=0.;waiting_exposure=0.
    events=recording.get('route_timeline',[])
    boundaries=sorted({e['end'] for e in events})
    while elapsed<end-1e-8:
        checkpoint();duration=min(2.-elapsed%2,300.-state.phase,end-elapsed)
        boundary=next((t for t in boundaries if t>elapsed+1e-8),end)
        duration=min(duration,boundary-elapsed)
        state,_,exposure=costs.transition(state,elapsed,duration,0.,lambda t:position_at(original,elapsed+t,original_times)['enu_m'])
        total_exposure+=exposure
        if any(e['kind']=='Waiting' and e['start']<=elapsed+duration/2<e['end'] for e in events):waiting_exposure+=exposure
        elapsed+=duration
    trace=costs.trace
    # Preserve native masked values alongside separately named estimated inputs.
    from .city_alignment import distinct_world_times
    times=distinct_world_times([s['seconds'] for s in original]+np.arange(0,end,1.).tolist()+[end]+[s['seconds'] for s in trace],departure)
    rows=[]
    for t in times:
        checkpoint();p=position_at(original,t,original_times);world=departure+t
        pm,air,pm_audit,temp_audit=inputs_at(p['enu_m'],world)
        native={k:fields.sample(k,*p['enu_m'][:2],world) for k in ['pmx','temperature','sunlight']}
        sun,sun_audit=solar_input(fields,p['enu_m'],world,policy)
        prediction=next(row for row in reversed(trace) if row['seconds']<=t+1e-7)
        b=baseline[min(len(baseline)-1,int((offset+t)//1800))]
        reference=dict(lower=b['q10'],upper=b['q90'],scale=max(b['scale'],.1),mode=b['mode'],count=b['count'])
        details=health_details(pm,air,sun,prediction['breathing'],reference,policy['solar_warming_c_per_800'])
        rows.append(dict(seconds=t,world_seconds=world,enu_m=np.asarray(p['enu_m']).tolist(),scene_m=np.asarray(p['scene_m']).tolist(),**native,
            pollution_proxy=pm,temperature_estimate=air,sunlight_estimate=sun,thermal_proxy=details['thermal_proxy'] if details else None,
            breathing=prediction['breathing'],latent_sd=prediction['latent_sd'],model_updates=prediction['updates'],
            health_score=details['score'] if details else None,contributions=details['contributions'] if details else None,
            breathing_reference=reference,input_estimates={'pmx':pm_audit,'temperature':temp_audit,'sunlight':sun_audit},
            phase='recorded_route' if t<=arrival else 'assumed_stationary_followup'))
    # Retain the prediction schedule and input policy without copying private
    # activity/humidity records into the browser.
    result=copy.deepcopy(recording)
    result.update(samples=rows,route_duration_s=arrival,duration_s=end,breathing_trace=trace,
        physiology_policy=policy,health_score=None,breathing=None,
        inference_status='conditional_cvae_with_current_city_estimates',
        physiology_note='Packaged recurrent CVAE and explicitly supplied reference; 300-second updates. City PMx plus assumed background is a PM2.5 input proxy; bounded nearby cells estimate masked inputs. Supplied humidity/activity is a counterfactual template, not synchronized city observations. Score and thermal proxy are heuristic; latent spread is not calibrated total uncertainty.',
        followup_note='After the recorded arrival, an optional stationary scenario continues at the destination through the selected field horizon. It is not recorded movement or a recovery validation.')
    for row in rows:
        event=next((e for e in events if e['start']<=row['seconds']<e['end']),None)
        row['movement_state']=event['kind'] if event else ('Arrived' if row['seconds']>=arrival else 'Walking')
        row['crossing_id']=event.get('crossing_id') if event else None
        row['wait_remaining_s']=event['end']-row['seconds'] if event and event['kind']=='Waiting' else 0.
    if events:
        result['crossing_summary']['integrated_pollution_proxy_ug_s_m3']=total_exposure
        result['crossing_summary']['waiting_pollution_proxy_ug_s_m3']=waiting_exposure
    result['missing_policy']=recording['missing_policy']+' Conditional model inputs are stored separately with donor coordinates/distances; raw missing values are unchanged.'
    result['physiology_audit']=dict(model_interval_s=300,history_offset_s=policy['breathing_history_offset_s'],seed=42,particles=16,
        updates=[r['seconds'] for r in trace[1:]],template_clock='Explicit template start + history offset + relative city seconds; independent of city observation UTC',
        model_input_features=list(runtime.columns),model_input_policy='Replace pollution and air temperature only; retain original humidity/activity/time template',
        max_temperature_donor_distance_m=max(r['input_estimates']['temperature'].get('distance_m',0) for r in rows),
        max_pmx_donor_distance_m=max(r['input_estimates']['pmx'].get('distance_m',0) for r in rows),
        max_sunlight_donor_distance_m=max(r['input_estimates']['sunlight'].get('distance_m',0) for r in rows))
    return result
