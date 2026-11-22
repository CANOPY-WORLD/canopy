import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import gzip
import numpy as np

spec = importlib.util.spec_from_file_location('pollution_export', Path(__file__).parents[1]/'tools/export_pollution_snapshot.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class PollutionPresentationTest(unittest.TestCase):
    def test_recorded_values_mask_and_subdomain_survive_export(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);run=root/'run';source=root/'old';out=root/'new'
            run.mkdir();(source/'physics').mkdir(parents=True)
            data=np.array([[[0, 1, 2], [3, 4, 5]]], dtype='f4')
            np.save(run/'frame.npy', data);np.save(run/'invalid.npy', np.array([[0,1,0],[0,0,0]],dtype='u1'))
            write=module.write
            write(run/'manifest.json', dict(status='complete',run_id='test',time=dict(samples=[0]),provenance={},layers=[dict(field=dict(name='PMx',unit='ug/m3'),encoding=dict(coordinate_frame='ENU',axes='TYX',spacing_m=[8,8],origin_m=[-12,-8,4],shape=[1,2,3],frame_assets=['frame.npy'],mask_asset='invalid.npy'))]))
            # Two recorded samples exercise the independent clock.
            m=json.loads((run/'manifest.json').read_text());m['time']['samples']=[0,6];m['layers'][0]['encoding']['shape'][0]=2;m['layers'][0]['encoding']['frame_assets']*=2;write(run/'manifest.json',m)
            write(source/'scene.json',dict(grid=dict(x0=-4096,z_south=4096),layers={},protocol_display=dict(npy_transport={}),preview_fields_8m={}))
            write(source/'physics/manifest.json',dict(arrays={}))
            write(source/'manifest.json',dict(snapshot='old',files=[dict(path='physics/manifest.json',viewer_path='physics/manifest.json',bytes=0,sha256='unused')]))
            module.export(run,source,out)
            scene=json.loads((out/'scene.json').read_text());layer=scene['layers']['poll']
            self.assertEqual((layer['cols'],layer['rows'],layer['offset_x_m'],layer['offset_z_m']),(3,2,4084,-4088))
            self.assertEqual(layer['time_s'],[0,6]);self.assertTrue(layer['own_clock'])
            transport=scene['protocol_display']['npy_transport']
            part=transport['poll.npy']['parts'][0]
            decoded=np.frombuffer(gzip.decompress((out/'physics'/part['file']).read_bytes()),dtype='<f2')
            np.testing.assert_array_equal(decoded,data.ravel())
            mask=transport['masks/poll_invalid.npy']['parts'][0]
            self.assertEqual(list(gzip.decompress((out/'physics'/mask['file']).read_bytes())),[0,1,0,0,0,0])
