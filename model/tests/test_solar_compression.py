import importlib.util
from pathlib import Path
import unittest
import numpy as np
spec=importlib.util.spec_from_file_location('export_solar_snapshot',Path(__file__).parents[1]/'tools/export_solar_snapshot.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SolarCompressionTests(unittest.TestCase):
    def test_quantization_bound_endpoints_and_no_clipping(self):
        a=np.linspace(0,950,1024,dtype='<f2').reshape(32,32)
        q,stats=m.compact_frame(a.tobytes(),'ghi',a.shape)
        self.assertLessEqual(stats['max_error_w_m2'],950/508+1e-4)
        self.assertEqual(q.flat[0],0);self.assertEqual(q.flat[-1],254)
        for value in [-1,951,float('nan')]:
            with self.assertRaises(ValueError):m.compact_frame(np.array([[value]],dtype='<f2').tobytes(),'ghi',(1,1))
    def test_shadow_is_exact_with_row_padding(self):
        a=np.array([[0,1,0],[1,0,1]],dtype='u1')
        q,_=m.compact_frame(a.tobytes(),'shadow',a.shape)
        np.testing.assert_array_equal(np.unpackbits(q,axis=1,count=3),a)
        with self.assertRaises(ValueError):m.compact_frame(bytes([2]),'shadow',(1,1))
