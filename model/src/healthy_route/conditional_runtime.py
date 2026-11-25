"""Packaged CVAE on explicitly supplied covariates; no route optimization.

The input is a checksummed physiology Asset. The public example is synthetic.
Authorized history can be supplied locally but is never a bundled default.
"""
from dataclasses import dataclass
import json
import numpy as np
import pandas as pd
import torch
from .inference import ASSETS, load_model


@dataclass
class PhysState:
    hidden: object
    last: object
    elapsed: float
    accumulated: object
    phase: float
    updates: int


def read_profile(folder):
    profile = json.loads((folder / 'physiology.json').read_text(encoding='utf-8'))
    required = {'format', 'input_kind', 'start_utc', 'features', 'initial_breathing_bpm', 'reference'}
    if set(profile) - (required | {'history'}) or not required <= profile.keys():
        raise ValueError('Invalid explicit physiology profile keys')
    if profile['format'] != 'canopy-health-physiology-v1' or profile['input_kind'] not in ('synthetic', 'authorized_history'):
        raise ValueError('Declare synthetic or authorized_history physiology inputs')
    features = np.asarray(profile['features'], dtype=float)
    if features.shape not in ((1, 8), (289, 8)) or not np.isfinite(features).all():
        raise ValueError('Expected one explicitly constant or 289 five-minute feature rows')
    initial = profile['initial_breathing_bpm']
    if not isinstance(initial, (int, float)) or not np.isfinite(initial) or initial <= 0:
        raise ValueError('Initial breathing must be finite and positive')
    stamp = pd.Timestamp(profile['start_utc'])
    if stamp.tzinfo is None:
        raise ValueError('Physiology template needs an explicit timezone')
    reference = profile['reference']
    if set(reference) != {'q10', 'q90', 'scale'} or not np.isfinite(list(reference.values())).all() or not 0 < reference['q10'] <= reference['q90'] or reference['scale'] <= 0:
        raise ValueError('Invalid explicitly assumed breathing reference')
    if 'history' in profile:
        history = np.asarray(profile['history'], dtype=float)
        if history.shape != (12, 9) or not np.isfinite(history).all() or (history[:, 8] <= 0).any():
            raise ValueError('History must contain twelve complete past five-minute rows')
    if profile['input_kind'] == 'authorized_history' and 'history' not in profile:
        raise ValueError('Authorized-history mode requires explicit history')
    return profile


class Runtime:
    template_horizon_s = 288 * 300

    def __init__(self, folder, seed=42, particles=16, checkpoint=lambda: None):
        profile = read_profile(folder)
        self.model, self.mean, self.scale, self.model_manifest = load_model()
        self.columns = json.loads((ASSETS / 'scaler.json').read_text())['columns'][:8]
        self.particles = particles
        self.input_kind = profile['input_kind']
        self.start = pd.Timestamp(profile['start_utc'])
        self.template = np.asarray(profile['features'], dtype=float)
        self.eps = torch.tensor(np.random.default_rng(seed).normal(size=(400, particles, 4)), dtype=torch.float32)
        if 'history' in profile:
            normalized = (np.asarray(profile['history']) - self.mean) / self.scale
            with torch.no_grad():
                hidden, last = self.model.warm(torch.tensor(normalized[None, :, :8], dtype=torch.float32).repeat(particles, 1, 1), torch.tensor(normalized[None, :, 8], dtype=torch.float32).repeat(particles, 1))
        else:
            hidden, last = self.model.initial(particles)
            last[:] = (profile['initial_breathing_bpm'] - self.mean[8]) / self.scale[8]
        self.initial = PhysState(hidden, last, 0., np.zeros(8), 0., 0)
        self.states = {0: self.initial}
        self.baseline = [{**profile['reference'], 'mode': profile['input_kind'], 'count': 0} for _ in range(49)]
        state = self.initial
        for k in range(288):
            checkpoint()
            state = self.advance(state, self.features(self.start + pd.Timedelta(seconds=(k + 1) * 300)), 300.)
            self.states[(k + 1) * 300] = state

    def features(self, stamp):
        seconds = (pd.Timestamp(stamp) - self.start).total_seconds()
        if not 0 <= seconds <= self.template_horizon_s:
            raise ValueError('Outside explicit covariate template coverage')
        index = 0 if len(self.template) == 1 else int(seconds // 300)
        values = self.template[index].copy()
        local = pd.Timestamp(stamp).tz_convert('Europe/London')
        hour = local.hour + local.minute / 60
        values[6:] = [np.sin(hour * 2 * np.pi / 24), np.cos(hour * 2 * np.pi / 24)]
        return values

    def br(self, state):
        values = state.last[:, 0].detach().numpy() * self.scale[8] + self.mean[8]
        if not np.isfinite(values).all() or (values <= 0).any():
            raise ValueError('Nonphysical breathing prediction; inspect input domain')
        return values

    def advance(self, state, features, duration):
        hidden, last = state.hidden, state.last
        elapsed, phase, accumulated, updates = state.elapsed, state.phase, state.accumulated.copy(), state.updates
        remaining = float(duration)
        while remaining > 1e-8:
            take = min(remaining, 300 - phase)
            accumulated += np.asarray(features) * take
            phase += take; elapsed += take; remaining -= take
            if phase >= 300 - 1e-7:
                inputs = torch.tensor(((accumulated / 300 - self.mean[:8]) / self.scale[:8])[None, :], dtype=torch.float32).repeat(self.particles, 1)
                with torch.no_grad():
                    _, _, (hidden, last), _ = self.model.step(inputs, (hidden, last), self.eps[updates])
                updates += 1; phase = 0.; accumulated = np.zeros(8)
        return PhysState(hidden, last, elapsed, accumulated, phase, updates)
