import unittest
import numpy as np
try:
    import torch
except ImportError:
    torch = None

@unittest.skipIf(torch is None, 'PyTorch required for solar kernels')
class SolarDayTests(unittest.TestCase):
    def test_local_day_has_night_and_correct_utc_epoch(self):
        from urban_flow.physics.solar.day import day_samples
        frames=day_samples('2026-06-21','Europe/London',100,51.506427,-.200473)
        self.assertEqual(len(frames),100)
        self.assertEqual(frames[0]['utc'],'2026-06-20T23:00:00+00:00')
        self.assertEqual(frames[-1]['seconds'],86400)
        self.assertLess(frames[0]['altitude_deg'],0)
        peak=max(frames,key=lambda f:f['altitude_deg'])
        self.assertTrue(60<peak['altitude_deg']<63)
        self.assertTrue(12.5*3600<peak['seconds']<13.5*3600)
        self.assertTrue(all(b['seconds']>a['seconds'] for a,b in zip(frames,frames[1:])))

    def test_dst_day_duration(self):
        from urban_flow.physics.solar.day import day_samples
        self.assertEqual(day_samples('2026-03-29','Europe/London',100,51.5,0)[-1]['seconds'],23*3600)

    def test_ground_aggregation_excludes_building_and_marks_unavailable(self):
        from urban_flow.physics.solar.day import aggregate
        values=np.array([[100,300],[1000,1000]],dtype='f4')
        valid=np.array([[1,1],[0,0]],dtype=bool)
        mean,mask=aggregate(values,valid)
        self.assertEqual(mean.item(),200)
        self.assertEqual(mask.item(),0)
        self.assertEqual(aggregate(values,~np.ones((2,2),dtype=bool))[1].item(),1)
        self.assertEqual(aggregate(np.array([[0,1],[0,0]]),valid,binary=True)[0].item(),1)

    def test_obstacle_casts_shadow_away_from_east_sun(self):
        from urban_flow.physics.solar.model import ShadowNet,ground_irradiance
        h=np.zeros((32,32),dtype='f4');h[16,16]=10
        sn=ShadowNet(h,1,'cpu');mask=sn(45,90)
        self.assertTrue(mask[16,12]);self.assertFalse(mask[16,20])
        night=ground_irradiance(sn(-10,180),torch.ones((32,32)),-10,6)[0]
        self.assertFalse(torch.any(night))
