"""Analysis semantics are documented in docs/framework/world-api.md."""
from __future__ import annotations

from bisect import bisect_right
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cached_property
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

from ..contract import read_json, validate
from ..storage import Storage


def _seconds(value):
    value = float(value)
    if not np.isfinite(value):
        raise ValueError('Time must be finite seconds')
    return value


def _epoch(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Epoch requires an explicit timezone')
    return parsed.astimezone(timezone.utc)


def _array(value):
    result = np.array(value, copy=True)
    result.flags.writeable = False
    return result


@dataclass(frozen=True)
class Result:
    """A query value or explicit missing observation, with source identity."""
    key: tuple[str, str]
    time: float
    local_time: float
    value: Any = None
    unit: str | None = None
    reason: str | None = None
    source_times: tuple[float, ...] = ()
    position: tuple[float, float, float] | None = None
    distance_m: float | None = None
    entity_id: str | None = None

    @property
    def available(self):
        return self.reason is None


class Layer:
    """One run-qualified geometry, field, trajectory or channel collection."""
    def __init__(self, path, manifest, descriptor, offset):
        self._path = path
        self._manifest = manifest
        self._descriptor = descriptor
        self.key = (manifest['run_id'], descriptor['id'])
        self.kind = descriptor['kind']
        self.unit = descriptor.get('field', {}).get('unit')
        self.offset = offset
        self._times = tuple(manifest['time']['samples'])
        self._mode = descriptor['sampling']
        self._format = descriptor['format']
        self._encoding = descriptor.get('encoding', {})

    @property
    def metadata(self):
        return deepcopy(self._descriptor)

    @property
    def provenance(self):
        return deepcopy(self._manifest['provenance'])

    @property
    def spatial(self):
        return deepcopy(self._manifest['spatial'])

    @property
    def times(self):
        """Recorded sample times in world-relative seconds (empty for static)."""
        return tuple(t + self.offset for t in self._times) if self._mode != 'static' else ()

    @cached_property
    def _payload(self):
        return read_json(self._path.parent / self._descriptor['asset'])

    def _npy(self, reference):
        return np.load(self._path.parent / reference, mmap_mode='r', allow_pickle=False)

    def _bracket(self, local):
        if self._mode == 'static':
            return (None, None, 0.0)
        if local < self._times[0] or local > self._times[-1]:
            return None
        lo = bisect_right(self._times, local) - 1
        if self._mode == 'step' or local == self._times[lo]:
            return (lo, lo, 0.0)
        return (lo, lo + 1, (local-self._times[lo])/(self._times[lo+1]-self._times[lo]))

    def _result(self, time, bracket, value=None, reason=None, **kwargs):
        source = () if bracket is None or bracket[0] is None else tuple(
            self._times[i] for i in dict.fromkeys(bracket[:2]))
        return Result(self.key, time, time-self.offset, value, self.unit, reason, source, **kwargs)

    def _frame(self, index):
        if self._format == 'npy_frames':
            return self._npy(self._encoding['frame_assets'][index])[0]
        if self._format == 'npy':
            data = self._npy(self._descriptor['asset'])
        else:
            name = 'vectors' if self.kind == 'vector_field' else 'values'
            data = np.asarray(self._payload[name])
        return data if index is None else data[index]

    def _blend(self, bracket, select=lambda x: x):
        lo, hi, weight = bracket
        a = np.asarray(select(self._frame(lo)), dtype=float)
        if lo == hi:
            return _array(a)
        b = np.asarray(select(self._frame(hi)), dtype=float)
        return _array(a + (b-a)*weight)

    def _entities(self, bracket):
        def frame(index):
            if self._format == 'trajectory_frames':
                payload = self._payload['frames'][index]
                return dict(zip(payload['ids'], payload['positions']))
            return dict(zip(self._payload['ids'], self._payload['positions'][index]))
        lo, hi, weight = bracket
        a = frame(lo)
        if lo == hi:
            return {key: _array(position) for key, position in a.items()}
        b = frame(hi)
        # An absent endpoint is not an observation of a stationary vehicle.
        return {key: _array(np.asarray(pos) + (np.asarray(b[key])-pos)*weight)
                for key, pos in a.items() if key in b}

    def at(self, time):
        """Materialize one layer at world-relative time; outside time is missing."""
        time = _seconds(time)
        bracket = self._bracket(time-self.offset)
        if bracket is None:
            return self._result(time, bracket, reason='outside_time')
        if self.kind == 'mesh':
            if self._format == 'glb':
                value = {'asset': self._path.parent / self._descriptor['asset'],
                         'coordinate_frame': 'glTF-y-up',
                         'to_enu': ((1, 0, 0), (0, 0, -1), (0, 1, 0))}
            else:
                value = {key: _array(val) for key, val in self._payload.items()}
                value['coordinate_frame'] = 'ENU'
        elif self.kind == 'trajectories':
            value = self._entities(bracket)
        elif self._format in ('npy', 'npy_frames'):
            values = self._blend(bracket)
            valid = np.ones(values.shape[-2:], dtype=bool)
            if 'mask_asset' in self._encoding:
                valid &= self._npy(self._encoding['mask_asset']) == 0
            value = {'values': values, 'valid': _array(valid),
                     'encoding': deepcopy(self._encoding)}
            if 'height_asset' in self._encoding:
                value['height_m'] = _array(self._npy(self._encoding['height_asset']))
        else:
            value = {'values': self._blend(bracket)}
            if self.kind == 'time_series':
                value['labels'] = tuple(self._payload['labels'])
            else:
                value['positions'] = _array(self._payload['positions'])
        return self._result(time, bracket, value)

    def state(self, entity_id, time):
        """Query an entity in this trajectory layer, preserving its local identity."""
        if self.kind != 'trajectories':
            raise TypeError('state() requires a trajectories layer')
        result = self.at(time)
        value = result.value.get(entity_id) if result.available else None
        reason = result.reason or ('entity_absent' if value is None else None)
        return self._result(result.time, self._bracket(result.local_time), value, reason,
                            entity_id=entity_id,
                            position=tuple(value) if value is not None else None)

    def sample(self, position, time, *, max_distance_m=0.0):
        """Nearest recorded point (JSON), or containing XY cell (NPY).

        Radius is an explicit 3D acceptance distance, NOT a volume extrapolator.
        Grid masks are never bypassed by searching for a different valid cell.
        """
        if self.kind not in ('scalar_field', 'vector_field'):
            raise TypeError('sample() requires a scalar or vector field')
        position = np.asarray(position, dtype=float)
        radius = float(max_distance_m)
        if position.shape != (3,) or not np.isfinite(position).all():
            raise ValueError('Position must contain three finite ENU coordinates')
        if not np.isfinite(radius) or radius < 0:
            raise ValueError('max_distance_m must be finite and nonnegative')
        time = _seconds(time)
        bracket = self._bracket(time-self.offset)
        if bracket is None:
            return self._result(time, bracket, reason='outside_time')
        masked = False
        if self._format in ('npy', 'npy_frames'):
            origin = np.asarray(self._encoding['origin_m'])
            spacing = np.asarray(self._encoding['spacing_m'])
            cell = np.floor((position[:2]-origin[:2])/spacing)
            rows, cols = self._encoding['shape'][-2:]
            if not (0 <= cell[0] < cols and 0 <= cell[1] < rows):
                return self._result(time, bracket, reason='outside_domain')
            col, row = map(int, cell)
            sampled = origin.astype(float).copy()
            sampled[:2] += (np.array([col, row]) + .5)*spacing
            if 'height_asset' in self._encoding:
                sampled[2] += self._npy(self._encoding['height_asset'])[row, col]
            if 'mask_asset' in self._encoding:
                masked = bool(self._npy(self._encoding['mask_asset'])[row, col])
            select = lambda frame: frame[..., row, col]
        else:
            positions = np.asarray(self._payload['positions'])
            index = int(np.argmin(np.linalg.norm(positions-position, axis=1)))
            sampled = positions[index]
            select = lambda frame: frame[index]
        distance = float(np.linalg.norm(sampled-position))
        meta = {'position': tuple(float(v) for v in sampled), 'distance_m': distance}
        if masked:
            return self._result(time, bracket, reason='masked', **meta)
        if distance > radius:
            return self._result(time, bracket, reason='outside_support', **meta)
        return self._result(time, bracket, self._blend(bracket, select), **meta)


@dataclass(frozen=True)
class Snapshot:
    """Lazy snapshot: indexing reads only the requested layer."""
    world: World
    time: float

    def __getitem__(self, key):
        return self.world.layers[key].at(self.time)

    def sample(self, field, position, **kwargs):
        return self.world.fields[field].sample(position, self.time, **kwargs)

    def state(self, trajectories, entity_id):
        return self.world.entities[trajectories].state(entity_id, self.time)


class World:
    """Compose validated recorded runs without changing their asset encoding."""
    def __init__(self, paths, *, time_alignment=None):
        if isinstance(paths, (str, Path)):
            paths = [paths]
        paths = [Path(path).resolve() for path in paths]
        if not paths:
            raise ValueError('World requires at least one manifest')
        if time_alignment not in (None, 'relative', 'absolute'):
            raise ValueError('time_alignment must be relative or absolute')
        if len(paths) > 1 and time_alignment is None:
            raise ValueError('Multiple runs require explicit time_alignment')
        manifests = []
        for path in paths:
            validate(path)
            manifest = read_json(path)
            if manifest['status'] != 'complete':
                raise ValueError('World requires complete runs')
            manifests.append(manifest)
        first = manifests[0]
        self.scene_id = first['scene_id']
        self._spatial = first['spatial']
        ids = set()
        for manifest in manifests:
            if manifest['run_id'] in ids:
                raise ValueError('Duplicate run ID')
            ids.add(manifest['run_id'])
            space = manifest['spatial']
            if manifest['scene_id'] != self.scene_id or any(
                space[k] != self._spatial[k] for k in ('frame', 'units', 'origin')
            ) or space.get('georeferenced', True) != self._spatial.get('georeferenced', True):
                raise ValueError('Runs require the same scene and spatial frame')
        self.time_alignment = time_alignment or 'relative'
        self.epoch = None
        epochs = {}
        if self.time_alignment == 'absolute':
            for manifest in manifests:
                if manifest['time']['samples']:
                    if 'epoch' not in manifest['time']:
                        raise ValueError('Absolute alignment requires run epochs')
                    epochs[manifest['run_id']] = _epoch(manifest['time']['epoch'])
            self.epoch = min(epochs.values()) if epochs else None
        layers = {}
        for path, manifest in zip(paths, manifests):
            epoch = epochs.get(manifest['run_id'])
            offset = (epoch-self.epoch).total_seconds() if epoch is not None else 0.0
            for descriptor in manifest['layers']:
                layer = Layer(path, manifest, descriptor, offset)
                layers[layer.key] = layer
        self._set_layers(layers)

    @classmethod
    def from_manifests(cls, paths, *, time_alignment=None):
        return cls(paths, time_alignment=time_alignment)

    @classmethod
    def from_view(cls, scene, name, *, storage=None):
        from ..catalog import view
        storage = storage or Storage.load()
        descriptor, runs = view(storage, scene, name, check_assets=False)
        world = cls([storage.run(scene, run)/'manifest.json' for run in runs],
                    time_alignment=descriptor['time_alignment'])
        # Visibility is presentation state; all explicitly selected layers are queryable.
        keys = [(item['run_id'], item['layer_id']) for item in descriptor['layers']]
        world._set_layers({key: world.layers[key] for key in keys})
        return world

    def _set_layers(self, layers):
        self.layers = MappingProxyType(layers)
        self.fields = MappingProxyType({k: v for k, v in layers.items()
                                       if v.kind in ('scalar_field', 'vector_field')})
        self.entities = MappingProxyType({k: v for k, v in layers.items() if v.kind == 'trajectories'})
        self.geometry = MappingProxyType({k: v for k, v in layers.items() if v.kind == 'mesh'})
        self.series = MappingProxyType({k: v for k, v in layers.items() if v.kind == 'time_series'})

    @property
    def spatial(self):
        return deepcopy(self._spatial)

    @property
    def times(self):
        return tuple(sorted({t for layer in self.layers.values() for t in layer.times}))

    def at(self, time):
        return Snapshot(self, _seconds(time))

    def sample_along(self, field, trajectories, entity_id, times, *, max_distance_m=0.0):
        """Yield one Result per requested time, including missing observations."""
        field_layer = self.fields[field]
        entity_layer = self.entities[trajectories]
        for time in times:
            state = entity_layer.state(entity_id, time)
            if not state.available:
                yield field_layer._result(state.time, None,
                                          reason=f'trajectory:{state.reason}', entity_id=entity_id)
            else:
                result = field_layer.sample(state.value, time, max_distance_m=max_distance_m)
                yield Result(**{**result.__dict__, 'entity_id': entity_id})
