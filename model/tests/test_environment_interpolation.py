import gzip
import tempfile
import unittest
from pathlib import Path
import numpy as np
from healthy_route.city_physiology import EstimatedCityFields, solar_input, MissingCityInput
from healthy_route.health_time import HealthReplayFields


class EnvironmentInterpolationTests(unittest.TestCase):
    def make(self,root,mask,values=None):
        values=np.array(values if values is not None else [[0,10,0],[20,999,30],[0,40,0]],'<f4')
        (root/'frame.gz').write_bytes(gzip.compress(values.tobytes()))
        (root/'mask.gz').write_bytes(gzip.compress(np.array(mask,'u1').tobytes()))
        m=dict(shape=[3,3],dtype='<f4',parts=['frame.gz','frame.gz'],mask='mask.gz',times_s=[0,600],origin_xy_m=[0,0],cell_m=8)
        f=EstimatedCityFields(root,{k:dict(m) for k in ['pmx','sunlight','temperature']});f.estimation_method='idw4';return f

    def test_missing_center_is_weighted_from_four_valid_neighbours(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=self.make(Path(tmp),[[1,0,1],[0,1,0],[1,0,1]])
            for key in ['pmx','sunlight']:
                self.assertIsNone(f.sample(key,12,12,300))
                value,a=f.estimate(key,12,12,300,8)
                self.assertEqual(value,25);self.assertEqual(a['method'],'inverse_distance_weighted_estimate')
                self.assertEqual(len(a['donors']),4);self.assertEqual(sum(d['weight'] for d in a['donors']),1)
                self.assertEqual(a['distance_m'],8)
                self.assertIsNone(f.sample(key,12,12,300))
                self.assertIsNone(f.estimate(key,12,12,300,7.9)[0])
                self.assertIsNone(f.estimate(key,12,12,601,100)[0])

    def test_valid_zero_is_preserved_and_all_missing_stays_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=self.make(Path(tmp),np.zeros((3,3)),np.zeros((3,3)))
            for key in ['pmx','sunlight']:
                value,a=f.estimate(key,12,12,300,256);self.assertEqual(value,0);self.assertEqual(a['method'],'native_cell')
            f=self.make(Path(tmp),np.ones((3,3)))
            with self.assertRaises(MissingCityInput):solar_input(f,[12,12,0],300,dict(max_sunlight_fill_m=256,max_pmx_fill_m=64,max_temperature_fill_m=256))

    def test_solar_day_clock_and_pmx_replay_remain_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=self.make(Path(tmp),[[1,0,1],[0,1,0],[1,0,1]])
            metadata=base.metadata;metadata['sunlight']['clock_offset_s']=100
            f=HealthReplayFields(Path(tmp),metadata,dict(horizon_s=1200,native_intervals_s={'pmx':[0,600],'temperature':[0,600]},blend_s=60));f.estimation_method='idw4'
            value,a=f.estimate('pmx',12,12,650,8);self.assertEqual(value,25);self.assertEqual(a['time_transform']['source_seconds'],50)
            value,a=f.estimate('sunlight',12,12,200,8);self.assertEqual(value,25);self.assertEqual(a['source_seconds'],300)
            self.assertIsNone(f.estimate('sunlight',12,12,650,8)[0])
            self.assertIsNone(f.sample('pmx',12,12,650))


if __name__=='__main__':unittest.main()
