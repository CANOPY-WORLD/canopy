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
    from .methods import Heightfield, Solar, Wind
    from .health_inference import HealthInference
    from .city_exposure import CityExposure
    from .city_physiology import CityPhysiology
    from .city_walk import CityWalk
    from .flood import Flood
    from .geometry import RasterizeGLB
    from .transport import Temperature,SteadyPollution
    from .transient_pollution import TransientPollution
    trusted={'city_exposure':CityExposure,'city_physiology':CityPhysiology,'city_walk':CityWalk,'health_inference':HealthInference,'traffic_transient':TransientPollution,'glb_rasterize':RasterizeGLB,'temperature_numpy':Temperature,'temperature_torch':Temperature,'steady_tracer':SteadyPollution,'heightfield':Heightfield,'solar_shadow':Solar,'nn4pdes_linear':Flood,'wind_mac':Wind}
    if spec['adapter'] not in trusted: raise ValueError('Unregistered implementation')
    return trusted[spec['adapter']](spec)
