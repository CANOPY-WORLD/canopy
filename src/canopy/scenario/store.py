"""Scenario ownership. Data roots remain separate from repository metadata."""
from contextlib import contextmanager
import os
from common.storage import scene_id, within
from canopy._io import read, write, check, relative

@contextmanager
def lock(storage, scenario):
    directory = storage.metadata(scenario)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / '.canopy.lock'
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(fd)
        yield
    finally:
        path.unlink()

def load(storage, scenario):
    scenario = scene_id(scenario)
    data = read(storage.metadata(scenario) / 'scenario.json')
    check(data, 'scenario')
    if data['scenario_id'] != scenario: raise ValueError('Scenario identity mismatch')
    lo, hi = data['spatial']['bounds_m']['min'], data['spatial']['bounds_m']['max']
    if any(a > b for a,b in zip(lo,hi)): raise ValueError('Reversed scenario bounds')
    for task in data['tasks'].values():
        if task['scenario_id'] != scenario: raise ValueError('Task belongs to another scenario')
    for location in data['assets'].values(): relative(data_root(storage, scenario), location)
    return data

def data_root(storage, scenario):
    return within(storage.data_root, 'project', scene_id(scenario))

def create(storage, scenario, title, spatial):
    scenario = scene_id(scenario)
    data = dict(schema_version='2.0.0', scenario_id=scenario, title=title,
                spatial=spatial, assets={}, tasks={}, visualization={'template':'standard','preset':'engineering','layers':[], 'time_alignment':'relative'})
    check(data, 'scenario')
    if any(a > b for a,b in zip(spatial['bounds_m']['min'],spatial['bounds_m']['max'])): raise ValueError('Reversed scenario bounds')
    with lock(storage, scenario):
        target = storage.metadata(scenario) / 'scenario.json'
        if target.exists(): raise FileExistsError(target)
        write(target, data)
    return data

def register(storage, scenario, descriptors):
    with lock(storage, scenario):
        data = load(storage, scenario)
        for key, location in descriptors.items():
            if key in data['assets'] and data['assets'][key] != location:
                raise ValueError(f'Asset version already registered: {key}')
            relative(data_root(storage, scenario), location)
            data['assets'][key] = location
        check(data, 'scenario')
        write(storage.metadata(scenario) / 'scenario.json', data)
