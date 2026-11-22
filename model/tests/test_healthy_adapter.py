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
            result={'route':{'routes':[{}, {'profile':[{'seconds':0},{'seconds':1},{'seconds':1},{'seconds':2}],
                'timeline':[{'start':0,'end':2,'kind':'Walking','points':[[0,0,0],[2,0,0]],'distance':[0,2]}]}]}}
            out=method.export(result,c)
            self.assertEqual(json.loads((out/'manifest.json').read_text())['time']['samples'],[0.,1.,2.])
            self.assertEqual(len(json.loads((out/'route.json').read_text())['routes'][1]['profile']),4)
            validate(out/'manifest.json')
    def test_export_preserves_turns_waits_and_breathing_updates(self):
        spec=describe('healthy_route','wave_cvae');method=implementation(spec)
        self.assertIn('trajectories',spec['outputs'])
        selected={'profile':[{'seconds':t,'temperature':22,'pollution':10,'sunlight':400,'thermal_proxy':25} for t in [0,7,7,9,12]],
            'timeline':[{'start':0,'end':7,'kind':'Walking','points':[[0,0,0],[4,0,0],[4,3,0]],'distance':[0,4,7]},
                        {'start':7,'end':9,'kind':'Waiting','points':[[4,3,0]]},
                        {'start':9,'end':12,'kind':'Walking','points':[[4,3,0],[7,3,0]],'distance':[0,3]}],
            'breathing_profile':[{'seconds':t,'breathing':v} for t,v in [(0,16),(5,20),(12,17)]]}
        with tempfile.TemporaryDirectory() as d:
            c=SimpleNamespace(workspace=Path(d),scenario={'scenario_id':'sample','spatial':{'frame':'ENU','units':'m','georeferenced':False,'origin':{'longitude':0,'latitude':0,'height_m':0,'vertical_datum':'synthetic'},'bounds_m':{'min':[0,0,0],'max':[10,10,10]}}},request={'model_id':'healthy_route'},run_id='test_route',created_at='2026-11-22T00:00:00Z',provenance={'code_revision':'test','dirty':False,'parameters':{},'inputs':[]})
            out=method.export({'route':{'routes':[{},selected]}},c);validate(out/'manifest.json')
            m=json.loads((out/'manifest.json').read_text())
            self.assertEqual(m['time']['samples'],[0,4,5,7,9,12])
            positions=json.loads((out/'trajectory.json').read_text())['positions']
            self.assertEqual(positions,[[[0,0,0]],[[4,0,0]],[[4,1,0]],[[4,3,0]],[[4,3,0]],[[7,3,0]]])
            self.assertEqual(json.loads((out/'breathing.json').read_text())['values'],[[16],[16],[20],[20],[20],[17]])
            self.assertEqual(json.loads((out/'route.json').read_text())['routes'][1],selected)
    def test_cpu_only(self):
        method=implementation(describe('healthy_route','wave_cvae'))
        with self.assertRaisesRegex(ValueError,'CPU'):
            method.validate({'execution':{'device':'cuda'}},None)
