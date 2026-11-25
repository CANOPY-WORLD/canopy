"""Recorded local inspection values; calculation stays on the model side."""
import math
import numpy as np


def sample(rows, seconds, key, step=False):
    if not rows or seconds < rows[0]['seconds'] or seconds > rows[-1]['seconds']:
        return None
    a = rows[0]
    for b in rows[1:]:
        if seconds < b['seconds']:
            if not finite(a.get(key)) or (not step and not finite(b.get(key))):
                return None
            return a[key] if step else a[key] + (b[key]-a[key])*(seconds-a['seconds'])/(b['seconds']-a['seconds'])
        a = b
    return a.get(key) if finite(a.get(key)) else None


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def health_details(pollution, thermal, breathing, reference):
    if not reference or not all(finite(v) for v in [pollution, thermal, breathing, reference.get('lower'), reference.get('upper'), reference.get('scale')]) or reference['scale'] <= 0 or pollution < 0 or breathing <= 0 or reference['lower'] <= 0 or reference['upper'] < reference['lower']:
        return None
    p = max(0, pollution)/15
    t = max(18-thermal, thermal-26, 0)/8
    b = 1.5*max(reference['lower']-breathing, breathing-reference['upper'], 0)/reference['scale']
    burdens = {'pollution': .35*p*p, 'temperature': .15*t*t, 'breathing': .50*b*b}
    total = sum(burdens.values())
    score = 100*math.exp(-math.log(100/90)*total)
    return {'score': score, 'contributions': {k: (100-score)*v/total if total else 0. for k,v in burdens.items()}}


def record(route, sampler=None):
    selected = route['routes'][1]
    timeline = selected['timeline']
    times = {float(row['seconds']) for key in ['profile', 'breathing_profile', 'breathing_reference'] for row in selected.get(key, [])}
    times.update(np.arange(0, timeline[-1]['end'], 1.).tolist())
    previous = 0.
    for event in timeline:
        a,b = float(event['start']),float(event['end'])
        points = np.asarray(event['points'], dtype=float)
        if not np.isfinite([a,b]).all() or a != previous or b <= a or points.ndim != 2 or points.shape[1] != 3 or not len(points) or not np.isfinite(points).all():
            raise ValueError('Recorded route requires finite contiguous events and ENU positions')
        previous = b
        times.update([a,b])
        if event['kind'] != 'Waiting':
            distance = np.asarray(event['distance'],dtype=float)
            if distance.shape != (len(points),) or not np.isfinite(distance).all() or distance[0] != 0 or distance[-1] <= 0 or (np.diff(distance)<0).any():
                raise ValueError('Invalid route distances')
            times.update((a+(b-a)*distance/distance[-1]).tolist())
    times = sorted(times)
    if not times or times[0] < 0 or times[-1] > previous:
        raise ValueError('Recording samples outside trajectory')
    rows=[]; index=0; travelled=0.; waited=0.
    for t in times:
        while index < len(timeline)-1 and t >= timeline[index]['end']:
            old=timeline[index]
            if old['kind']=='Waiting': waited += old['end']-old['start']
            else: travelled += old['distance'][-1]
            index += 1
        event=timeline[index];waiting=event['kind']=='Waiting';points=np.asarray(event['points'])
        f=(t-event['start'])/(event['end']-event['start'])
        position=points[0].tolist() if waiting else [float(np.interp(f*event['distance'][-1],event['distance'],points[:,j])) for j in range(3)]
        fields = sampler(position, route.get('departure_s',0)+t) if sampler else {key:sample(selected['profile'],t,key) for key in ['pollution','temperature','sunlight','thermal_proxy']}
        fields={key:float(value) if finite(value) else None for key,value in fields.items()}
        breathing=sample(selected.get('breathing_profile',[]),t,'breathing',True)
        reference=next((r for r in reversed(selected.get('breathing_reference',[])) if r['seconds']<=t),None)
        details=health_details(fields.get('pollution'),fields.get('thermal_proxy'),breathing,reference) if finite(fields.get('temperature')) else None
        rows.append(dict(seconds=t,position=position,status=event['kind'],distance=travelled+(0 if waiting else f*event['distance'][-1]),wait=waited+(t-event['start'] if waiting else 0),breathing=breathing,reference=reference,health=details,**fields))
    return {'format':'canopy.health-recording.v1','samples':rows,'departure_s':route.get('departure_s',0),
        'travel_mode':route.get('travel_mode','walk'),'solar_day':route.get('solar_day'),
        'sampling':'Recorded at one-second intervals and exact route/physiology/reference boundaries; display holds samples, without filling unavailable values.',
        'environment_sampling':'Native fields at recorded position/time' if sampler else 'Profile interpolation; absent endpoints remain unavailable',
        'clock':'Relative seconds after departure; scenario clock 08:50 + departure + elapsed. Traffic and temperature/pollution repeat every 600 s; solar does not.',
        'limits':'Standalone historical research preview. City vertical alignment unresolved. Modelled pedestrian signals are independent of recorded vehicle signals. Health score and thermal proxy are heuristic, not clinical advice. Running physiology is uncalibrated. Filled environmental cells are estimates; solar zero extension is an assumption.'}
