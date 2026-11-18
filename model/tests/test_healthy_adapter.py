import unittest,tempfile,json
from pathlib import Path
from types import SimpleNamespace
from canopy.models.registry import describe,implementation
from common.contract import validate

class AdapterTests(unittest.TestCase):
    def test_registry_and_boundary_samples(self):
        spec=describe('healthy_route','wave_cvae')
        method=implementation(spec)
        with tempfile.TemporaryDirectory() as d:
            c=SimpleNamespace(workspace=Path(d),scenario={'scenario_id':'sample','spatial':{'frame':'ENU','units':'m','georeferenced':False,'origin':{'longitude':0,'latitude':0,'height_m':0,'vertical_datum':'synthetic'},'bounds_m':{'min':[0,0,0],'max':[10,10,10]}}},request={'model_id':'healthy_route'},run_id='test_route',created_at='2026-11-18T00:00:00Z',provenance={'code_revision':'test','dirty':False,'parameters':{},'inputs':[]})
            result={'route':{'routes':[{}, {'profile':[{'seconds':0},{'seconds':1},{'seconds':1},{'seconds':2}]}]}}
            out=method.export(result,c)
            self.assertEqual(json.loads((out/'manifest.json').read_text())['time']['samples'],[0.,1.,2.])
            self.assertEqual(len(json.loads((out/'route.json').read_text())['routes'][1]['profile']),4)
            validate(out/'manifest.json')
    def test_cpu_only(self):
        method=implementation(describe('healthy_route','wave_cvae'))
        with self.assertRaisesRegex(ValueError,'CPU'):
            method.validate({'execution':{'device':'cuda'}},None)
