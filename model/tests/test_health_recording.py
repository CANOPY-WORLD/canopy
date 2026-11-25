import math
import unittest
from healthy_route.recording import record, health_details


def route():
    return {'departure_s':540,'routes':[{},dict(
        profile=[dict(seconds=t,pollution=p,temperature=22,sunlight=0,thermal_proxy=22) for t,p in [(0,15),(2,None),(4,15)]],
        timeline=[dict(start=0,end=2,kind='Walking',points=[[0,0,0],[2,0,0]],distance=[0,2]),dict(start=2,end=4,kind='Waiting',points=[[2,0,0]])],
        breathing_profile=[dict(seconds=t,breathing=b) for t,b in [(0,16),(3,30),(4,30)]],
        breathing_reference=[dict(seconds=0,lower=14,upper=18,scale=4),dict(seconds=3,lower=15,upper=20,scale=5)])]}


class RecordingTests(unittest.TestCase):
    def test_personal_score_formula(self):
        x=health_details(15,22,16,dict(lower=14,upper=18,scale=4))
        self.assertAlmostEqual(x['score'],100*math.exp(-math.log(100/90)*.35))
        self.assertAlmostEqual(sum(x['contributions'].values()),100-x['score'])
        self.assertIsNone(health_details(None,22,16,dict(lower=14,upper=18,scale=4)))

    def test_wait_reference_and_missing_samples(self):
        result=record(route());rows=result['samples']
        self.assertEqual([r['seconds'] for r in rows],[0,1,2,3,4])
        self.assertEqual([r['distance'] for r in rows],[0,1,2,2,2])
        self.assertEqual([r['wait'] for r in rows],[0,0,0,1,2])
        self.assertEqual(rows[3]['breathing'],30)
        self.assertEqual(rows[3]['reference']['upper'],20)
        self.assertIsNone(rows[2]['health'])
        self.assertIsNotNone(rows[4]['health'])

    def test_native_sampler_receives_absolute_scenario_seconds(self):
        calls=[]
        def sampler(point,t):
            calls.append((point,t))
            return dict(pollution=15,temperature=22,sunlight=0,thermal_proxy=22)
        data=record(route(),sampler)
        self.assertEqual([t for _,t in calls],[540,541,542,543,544])
        self.assertEqual(calls[-1][0],[2,0,0])
        self.assertTrue(all(r['health'] for r in data['samples']))

    def test_refuses_missing_trajectory_segment(self):
        data=route();data['routes'][1]['timeline'][1]['start']=3
        with self.assertRaisesRegex(ValueError,'contiguous'):record(data)
