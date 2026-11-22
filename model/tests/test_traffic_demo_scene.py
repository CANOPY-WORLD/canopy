import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('scene_export',Path(__file__).resolve().parents[1]/'tools/export_traffic_demo_scene.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class NativeReviewTests(unittest.TestCase):
    def test_retains_height_slope_and_sparse_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'config.json').write_text(json.dumps({'command':['sumo','-n','/old/location/network.xml','-r','/old/location/routes.xml']}))
            (root/'network.xml').write_text('<net><edge id="a" from="west" to="east"><lane id="a_0" shape="0,0,5 10,0,6"/></edge></net>')
            (root/'routes.xml').write_text('<routes><vType id="car" length="4.5" width="1.8" height="1.5"/></routes>')
            with gzip.open(root/'traffic.fcd.xml.gz','wt') as f:f.write('<fcd-export><timestep time="10"><vehicle id="x" type="car" x="1" y="2" z="5" angle="90" slope="10" speed="3"/></timestep><timestep time="10.1"/></fcd-export>')
            with patch.object(module,'assess_run',return_value={'diagnostic_pass':True}):
                module.export(root,root/'scene.json',10,10.2,[0,0],50)
                with self.assertRaises(ValueError):module.export(root,root/'missing.json',10,10.3,[0,0],50)
            data=json.loads((root/'scene.json').read_text())
            self.assertEqual(data['frames'][0]['vehicles'][0][4],5)
            self.assertAlmostEqual(data['frames'][0]['vehicles'][0][6],.17453292519943295)
            self.assertEqual(data['frames'][1]['vehicles'],[])
            self.assertEqual(data['lanes'][0]['from_junction'],'west')
            self.assertEqual(data['lanes'][0]['to_junction'],'east')
            self.assertFalse((root/'missing.json').exists())

    def test_failed_diagnostic_cannot_be_exported(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(module,'assess_run',return_value={'diagnostic_pass':False,'failed_checks':['collision']}):
                with self.assertRaises(ValueError):module.export(root,root/'scene.json',0,1,[0,0],50)
            self.assertFalse((root/'scene.json').exists())
