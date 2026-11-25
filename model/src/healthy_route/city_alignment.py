"""Strict sampling of pinned city presentation fields; no physiological inference."""
import base64
import gzip
import math
from functools import lru_cache
from pathlib import Path
import numpy as np
from canopy._io import read, relative


def distinct_world_times(times, departure):
    """One generated sample per representable scenario-clock instant.

    Adding a nonzero departure can map adjacent floating-point elapsed times
    onto the same clock value. Retain the later elapsed sample (right-hand
    event state), without rounding distinct world instants or shifting times.
    This applies to generated display samples, not source observations.
    """
    by_world = {}
    for elapsed in sorted(times):
        world = departure + elapsed
        if not math.isfinite(world):
            raise ValueError('Non-finite generated sample time')
        by_world[world] = elapsed
    return list(by_world.values())


def decode(values, quantization):
    values = np.asarray(values)
    if not quantization:
        return values.astype(float)
    q = quantization
    out = values.astype(float) * q['scale'] + q.get('offset', 0)
    if q.get('transform') == 'log1p':
        out = q['reference'] * np.expm1(out)
    elif q.get('transform', 'linear') != 'linear':
        raise ValueError('Unsupported quantization')
    return np.where(values == q.get('invalid_code', 255), np.nan, out)


class Terrain:
    def __init__(self, meta):
        self.meta = meta
        self.values = np.frombuffer(base64.b64decode(meta['z']), '<i2').reshape(meta['ny'], meta['nx'])

    def sample(self, x, y):
        m = self.meta
        u, v = (x-m['x0'])/m['dx'], (y-m['y0'])/m['dx']
        if not 0 <= u <= m['nx']-1 or not 0 <= v <= m['ny']-1:
            raise ValueError('Position outside pinned terrain')
        i, j = min(math.floor(u), m['nx']-2), min(math.floor(v), m['ny']-2)
        a, b = u-i, v-j
        z = self.values
        return float(m['base_m']+m['scale_m']*(z[j,i]*(1-a)*(1-b)+z[j,i+1]*a*(1-b)+z[j+1,i]*(1-a)*b+z[j+1,i+1]*a*b))


class CityFields:
    def __init__(self, root, metadata):
        self.root, self.metadata = Path(root), metadata

    @lru_cache(maxsize=12)
    def frame(self, key, index):
        m = self.metadata[key]
        data = gzip.decompress(relative(self.root, m['parts'][index]).read_bytes())
        values = np.frombuffer(data, m['dtype']).reshape(m['shape'])
        return decode(values, m.get('quantization'))

    @lru_cache(maxsize=3)
    def mask(self, key):
        m = self.metadata[key]
        return np.frombuffer(gzip.decompress(relative(self.root, m['mask']).read_bytes()), 'u1').reshape(m['shape'])

    def sample(self, key, x, y, t):
        m = self.metadata[key]
        t += m.get('clock_offset_s', 0)
        times = np.asarray(m['times_s'])
        i = math.floor((x-m['origin_xy_m'][0])/m['cell_m'])
        j = math.floor((y-m['origin_xy_m'][1])/m['cell_m'])
        if not times[0] <= t <= times[-1] or not 0 <= i < m['shape'][1] or not 0 <= j < m['shape'][0]:
            return None
        if self.mask(key)[j,i]:
            return None
        hi = min(int(np.searchsorted(times, t)), len(times)-1)
        lo = max(0, hi-1)
        if times[hi] == t:
            value = self.frame(key, hi)[j,i]
        else:
            f = (t-times[lo])/(times[hi]-times[lo])
            value = self.frame(key, lo)[j,i]*(1-f)+self.frame(key, hi)[j,i]*f
        return float(value) if np.isfinite(value) else None


def align_recording(source, network, terrain, fields, checkpoint=lambda: None):
    """Keep the chosen route/times; reject unverified topology instead of snapping."""
    route = source['routes'][1]
    lookup = {}
    for edge in network['edges']:
        lookup[tuple([edge['u'], edge['v']])] = edge['points']
        lookup[tuple([edge['v'], edge['u']])] = edge['points'][::-1]
    selected = [lookup.get(tuple(k)) for k in route['edge_keys']]
    if any(e is None for e in selected):
        raise ValueError('Recorded route has an edge absent from the pinned city network')
    walking = iter(selected)
    events, controls = [], []
    end, previous = 0., None
    for event in route['timeline']:
        checkpoint()
        start, stop = float(event['start']), float(event['end'])
        if not np.isfinite([start, stop]).all() or abs(start-end)>1e-7 or stop<=start:
            raise ValueError('Missing or invalid trajectory segment; no gap interpolation permitted')
        old = np.asarray(event['points'], dtype=float)
        if old.ndim != 2 or old.shape[1] != 3 or not np.isfinite(old).all():
            raise ValueError('Missing trajectory positions')
        if event['kind'] == 'Waiting':
            # A wait must occur at a verified endpoint on this selected route.
            candidates = [p for e in selected for p in [e[0], e[-1]] if np.linalg.norm(np.asarray(p[:2])-old[0,:2]) < 1e-5]
            if not candidates:
                raise ValueError('Wait is not on the selected city route')
            points = np.asarray([candidates[0]])
            residual = np.linalg.norm(points[0,:2]-old[0,:2])
        else:
            points = np.asarray(next(walking), dtype=float)
            if points.shape != old.shape or np.max(np.linalg.norm(points[:,:2]-old[:,:2], axis=1)) > 1e-5:
                raise ValueError('Route geometry differs from the pinned city; remapping needs review')
            residual = np.max(np.linalg.norm(points[:,:2]-old[:,:2], axis=1))
        if previous is not None and np.linalg.norm(points[0]-previous)>1e-5:
            raise ValueError('Route has an absent segment; refusing to draw a connecting line')
        distances = np.r_[0., np.cumsum(np.linalg.norm(np.diff(points[:,:2],axis=0),axis=1))]
        if event['kind'] != 'Waiting' and distances[-1]<=0:
            raise ValueError('Zero-length movement')
        events.append(dict(start=start,end=stop,kind=event['kind'],points=points.tolist(),distance=distances.tolist()))
        for p in points:
            ground = terrain.sample(*p[:2])
            controls.append(dict(east_m=p[0],north_m=p[1],native_scene_height_m=p[2],terrain_height_m=ground,
                height_above_ground_m=p[2]-ground,xy_residual_m=float(residual),
                reconstructed_scene_z_residual_m=float((p[2]-ground)+ground-p[2])))
        end, previous = stop, points[-1]
    if next(walking, None) is not None:
        raise ValueError('Unmatched route edges')
    times = set(np.arange(0, end, 1.).tolist()+[end])
    for e in events:
        times.update([e['start'],e['end']])
        if e['distance'][-1]>0:
            times.update(e['start']+(e['end']-e['start'])*d/e['distance'][-1] for d in e['distance'])
    samples=[]
    for t in distinct_world_times(times, float(source['departure_s'])):
        checkpoint()
        e=next((e for e in events if e['start']<=t<e['end']),events[-1])
        points=np.asarray(e['points']);d=np.asarray(e['distance'])
        f=(t-e['start'])/(e['end']-e['start'])
        p=points[0] if e['kind']=='Waiting' else np.array([np.interp(f*d[-1],d,points[:,i]) for i in range(3)])
        # Ordinary ground routes follow the current DEM between vertices too.
        if np.allclose(points[:,2],[terrain.sample(*q[:2]) for q in points],atol=1e-6):
            p=p.copy();p[2]=terrain.sample(*p[:2])
        ground=terrain.sample(*p[:2]); world=float(source['departure_s'])+t
        values={k:fields.sample(k,*p[:2],world) for k in fields.metadata}
        samples.append(dict(seconds=t,world_seconds=world,enu_m=[float(p[0]),float(p[1]),float(p[2]-ground)],
            scene_m=[float(p[0]),float(p[2]),float(-p[1])],**values))
    return dict(samples=samples,duration_s=end,departure_s=source['departure_s'],control_points=controls,
        route_start_enu_m=samples[0]['enu_m'],route_end_enu_m=samples[-1]['enu_m'],
        original_timing_preserved=True,health_score=None,breathing=None,
        inference_status='unavailable: no compatible total PM2.5 or synchronized humidity/activity inputs; PMx is not substituted',
        signal_status='No signal state displayed. Original route waits are retained historical planning assumptions, not current recorded vehicle clearance.',
        missing_policy='Null remains unavailable. No spatial filling, repeating, extrapolation or drawing across absent route segments.',
        coordinate_conversion='ENU [east,north,height above pinned local ground]; scene [east,ground+height,-north]. Display lift only: 0.15 m.',
        vertical_limit='Aligned to the pinned scene native terrain/decks. Terrarium datum conversion is undocumented; no certified ODN/ellipsoidal accuracy claim.')
