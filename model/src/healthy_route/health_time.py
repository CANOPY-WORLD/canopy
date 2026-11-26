"""Explicit Health-only temporal replay; native city samples remain unchanged."""
import math
from .city_physiology import EstimatedCityFields


def time_coverage(fields, policy, template_horizon_s):
    mode = policy.get('field_time_policy', 'native')
    if mode not in ('native', 'health_replay'):
        raise ValueError('Unsupported Health field time policy')
    model_end = template_horizon_s - policy['breathing_history_offset_s']
    solar = fields['sunlight']
    solar_end = solar['times_s'][-1] - solar.get('clock_offset_s', 0)
    native_end = min(fields[k]['times_s'][-1] for k in ['pmx', 'temperature'])
    end = min(model_end, solar_end, native_end if mode == 'native' else math.inf)
    native = {k: [fields[k]['times_s'][0], fields[k]['times_s'][-1]] for k in ['pmx', 'temperature']}
    blend = policy.get('field_replay_blend_s', 60.)
    if mode == 'health_replay':
        for start, stop in native.values():
            if start != 0 or stop <= start or not 0 <= blend <= stop-start:
                raise ValueError('Health replay requires a zero-based source sequence and a valid blend interval')
    return dict(mode=mode, horizon_s=end, model_horizon_s=model_end,
                native_intervals_s=native, blend_s=blend if mode == 'health_replay' else 0,
                sunlight='Native day timeline at its declared clock offset; not repeated',
                physiology='Continuous history and five-minute updates; never reset at field cycle boundaries',
                source_data_unchanged=True)


def replay_clock(seconds, start, stop, blend_s):
    """Same smooth periodic clock as the original local Environment.sample."""
    period = stop-start
    if not math.isfinite(seconds) or seconds < 0 or period <= 0 or not 0 <= blend_s <= period:
        raise ValueError('Invalid replay clock')
    source = start + seconds % period
    u = max(0., min(1., (source-(stop-blend_s))/blend_s)) if blend_s else 0.
    return source, u*u*(3-2*u), int(seconds//period)


class HealthReplayFields(EstimatedCityFields):
    """Estimate model covariates on a replay clock; sample() stays native."""
    def __init__(self, root, metadata, coverage):
        super().__init__(root, metadata)
        self.coverage = coverage
        self.horizon_s = coverage['horizon_s']

    def estimate(self, key, x, y, seconds, radius_m):
        if key not in ('pmx', 'temperature'):
            return super().estimate(key, x, y, seconds, radius_m)
        if not math.isfinite(seconds) or not 0 <= seconds <= self.horizon_s:
            return None, dict(method='outside_health_model_coverage')
        start, stop = self.coverage['native_intervals_s'][key]
        source, weight, cycle = replay_clock(seconds, start, stop, self.coverage['blend_s'])
        value, audit = super().estimate(key, x, y, source, radius_m)
        audit = dict(audit)
        transform = dict(policy='health_replay', source_seconds=source,
                         cycle_index=cycle, period_s=stop-start, first_frame_weight=weight)
        if weight > 0:
            first, first_audit = super().estimate(key, x, y, start, radius_m)
            transform['first_frame_estimate'] = first_audit
            audit['distance_m'] = max(audit.get('distance_m', 0), first_audit.get('distance_m', 0))
            value = None if value is None or first is None else value*(1-weight)+first*weight
        audit['time_transform'] = transform
        return value, audit
