"""Trusted method registry; scenario JSON never supplies executable entrypoints."""
from pathlib import Path
from jsonschema import Draft202012Validator
from canopy._io import read, check

DIRECTORY = Path(__file__).parent / 'specs'

def catalog():
    result=[]
    for path in sorted(DIRECTORY.glob('*/*.json')):
        if path.name == 'model.json': continue
        data=read(path);check(data,'method');Draft202012Validator.check_schema(data['parameters'])
        model=read(path.parent/'model.json');check(model,'model')
        if model['model_id'] != data['model_id'] or model['category'] != data['category']:
            raise ValueError('Model/method identity mismatch')
        if model['methods'].get(data['method_id']) != {'version':data['version'],'spec':path.name}:
            raise ValueError('Model method version/entry mismatch')
        result.append(data)
    return result

def describe(model, method):
    for spec in catalog():
        if (spec['model_id'],spec['method_id']) == (model,method): return spec
    raise ValueError(f'Unknown model/method: {model}/{method}')

def implementation(spec):
    from .methods import Heightfield, Solar, Flood, Wind
    trusted={'heightfield':Heightfield,'solar_shadow':Solar,'flood_swe':Flood,'wind_mac':Wind}
    if spec['adapter'] not in trusted: raise ValueError('Unregistered implementation')
    return trusted[spec['adapter']](spec)
