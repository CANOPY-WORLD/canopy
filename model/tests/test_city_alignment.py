"""Numerical checks for current-city coordinates, masks and time coverage."""
import base64
import copy
import gzip
import tempfile
import unittest
from pathlib import Path
import numpy as np
from healthy_route.city_alignment import CityFields, Terrain, align_recording, decode, distinct_world_times


class CityAlignmentTests(unittest.TestCase):
    def test_departure_offset_does_not_create_duplicate_generated_clock_samples(self):
        a=23.653542490217554
        b=np.nextafter(a, np.inf)
        self.assertNotEqual(a,b)
        self.assertEqual(14400+a,14400+b)
        times=distinct_world_times([0,a,b,24,25],14400)
        self.assertEqual(times,[0,b,24,25])
        self.assertTrue(all(14400+x<14400+y for x,y in zip(times,times[1:])))
        # No blanket rounding: values distinct on the output clock remain so.
        self.assertEqual(distinct_world_times([a,b],0),[a,b])

    def test_log_quantization_and_invalid_code(self):
        values=decode([0,10,255],{'transform':'log1p','scale':.1,'offset':0,'reference':1e-6,'invalid_code':255})
        self.assertEqual(values[0],0)
        self.assertAlmostEqual(values[1],1e-6*(np.e-1))
        self.assertTrue(np.isnan(values[2]))
        with self.assertRaises(ValueError):decode([1],{'transform':'unknown','scale':1})

    def test_grid_origin_masks_and_no_extrapolation_or_repeating(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name,data in [('a.gz',np.array([[1,2],[3,4]],'<f2')),('b.gz',np.array([[5,6],[7,8]],'<f2')),('mask.gz',np.array([[0,1],[0,0]],'u1'))]:
                (root/name).write_bytes(gzip.compress(data.tobytes()))
            fields=CityFields(root,{'temperature':dict(shape=[2,2],origin_xy_m=[-4000,-4000],cell_m=8,dtype='<f2',parts=['a.gz','b.gz'],mask='mask.gz',times_s=[0,600])})
            sample=lambda x,y,t:fields.sample('temperature',x,y,t)
            self.assertEqual(sample(-3999,-3999,300),3)
            self.assertEqual(sample(-3999,-3999,600),5)
            for xyz in [(-4096,-4096,0),(-3984,-3999,0),(-3989,-3999,0),(-3999,-3999,601),(-3999,-3999,-1)]:
                self.assertIsNone(sample(*xyz))

    def fixture(self):
        terrain=Terrain(dict(x0=0,y0=0,dx=10,nx=2,ny=2,base_m=10,scale_m=.1,z=base64.b64encode(np.array([[0,10],[20,30]],'<i2').tobytes()).decode()))
        pts=[[0,0,10],[10,0,11]]
        route=dict(edge_keys=[['a','b']],timeline=[dict(kind='Walking',start=0,end=10,points=[[0,0,999],[10,0,999]])])
        source=dict(routes=[route,route],departure_s=0)
        network={'edges':[dict(u='a',v='b',points=pts)]}
        class Fields:
            metadata={'pmx':{}}
            def sample(self,*args):return None
        return source,network,terrain,Fields()

    def test_native_heights_replace_old_z_with_explicit_ground_conversion(self):
        source,network,terrain,fields=self.fixture()
        result=align_recording(source,network,terrain,fields)
        middle=result['samples'][5]
        self.assertEqual(middle['scene_m'],[5,10.5,0])
        self.assertEqual(middle['enu_m'],[5,0,0])
        self.assertIsNone(middle['pmx']);self.assertIsNone(result['health_score'])
        self.assertEqual(source['routes'][1]['timeline'][0]['points'][0][2],999)
        self.assertEqual(terrain.sample(10,10),13)
        with self.assertRaises(ValueError):terrain.sample(-1,0)

    def test_absent_edge_geometry_change_and_time_gap_fail_closed(self):
        source,network,terrain,fields=self.fixture()
        for broken in ['edge','xy','gap','nan']:
            changed=copy.deepcopy(source)
            route=changed['routes'][1]
            if broken=='edge':route['edge_keys']=[['missing','b']]
            if broken=='xy':route['timeline'][0]['points'][0][0]=1
            if broken=='gap':route['timeline'][0]['start']=1
            if broken=='nan':route['timeline'][0]['points'][0][0]=float('nan')
            with self.subTest(broken=broken),self.assertRaises(ValueError):align_recording(changed,network,terrain,fields)
