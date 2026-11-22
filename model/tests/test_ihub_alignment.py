"""Geographic adapter checks independent of retained real-world payloads."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import json
import numpy as np
spec=importlib.util.spec_from_file_location('ihub_export',Path(__file__).parents[1]/'tools/export_ihub_interior.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class IhubAlignmentTests(unittest.TestCase):
    def test_inverse_fit_keeps_height_and_geographic_origin(self):
        angle=.2
        geo=dict(lat0=51.5,lon0=-.2,scale=1.01,R=[[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]],t=[37.,-53.])
        matrix=module.alignment(geo,dict(latitude=51.5,longitude=-.2))
        # The fitted translation is exactly the source geographic origin.
        np.testing.assert_allclose(matrix@[37,32,53,1],[0,32,0,1],atol=1e-10)
        en=np.array([100.,200.]);authored=geo['scale']*np.array(geo['R'])@en+geo['t']
        np.testing.assert_allclose(matrix@[authored[0],32,-authored[1],1],[100,32,-200,1],atol=1e-10)

    def test_root_transform_preserves_binary_payload_and_nodes(self):
        doc=dict(asset={'version':'2.0'},scenes=[{'nodes':[0]}],nodes=[{'name':'Original','translation':[1,2,3]}])
        encoded=json.dumps(doc).encode();encoded+=b' '*(-len(encoded)%4)
        binary=struct.pack('<II',4,0x004e4942)+b'1234'
        raw=struct.pack('<4sII',b'glTF',2,20+len(encoded)+len(binary))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+binary
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/'source.glb';dst=Path(d)/'result.glb';src.write_bytes(raw)
            matrix=np.eye(4);matrix[0,3]=99
            module.transform_glb(src,dst,matrix);result=dst.read_bytes();length=struct.unpack_from('<I',result,12)[0];actual=json.loads(result[20:20+length])
            self.assertEqual(result[20+length:],binary);self.assertEqual(actual['nodes'][0],doc['nodes'][0]);self.assertEqual(actual['scenes'][0]['nodes'],[1]);self.assertEqual(actual['nodes'][1]['matrix'][12],99)
