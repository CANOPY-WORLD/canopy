import base64
import copy
import gzip
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
from healthy_route.city_physiology import EstimatedCityFields, health_details, evaluate, check_model_coverage, MissingCityInput


class CityPhysiologyTests(unittest.TestCase):
    def test_coverage_check_identifies_temperature_and_keeps_zero_pollution_valid(self):
        class Fields:
            def estimate(self,key,x,y,t,radius):
                return (None if key=='temperature' and t>=1 else 0),{'method':'no_valid_donor_within_limit' if key=='temperature' and t>=1 else 'native_cell'}
        policy=dict(followup_until_elapsed_s=0,max_pmx_fill_m=16,max_temperature_fill_m=128,assumed_background_pm25_ug_m3=6,pmx_to_pm25_proxy_fraction=1)
        recording=dict(duration_s=2,departure_s=0,samples=[dict(seconds=0,enu_m=[0,0,0],scene_m=[0,0,0]),dict(seconds=2,enu_m=[2,0,0],scene_m=[2,0,0])])
        with self.assertRaises(MissingCityInput) as caught:check_model_coverage(recording,Fields(),policy)
        self.assertEqual(caught.exception.details['fields'],['temperature'])
        self.assertEqual(caught.exception.details['world_seconds'],1)
        self.assertEqual(caught.exception.details['xy_m'],[1,0])
        self.assertIn('128 m',str(caught.exception))
        self.assertIn('spatial gap',str(caught.exception))

    def test_bounded_donor_preserves_native_mask_and_never_extrapolates_time(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name,data in [('field.gz',np.array([[20,30],[40,50]],'<f2')),('mask.gz',np.array([[1,0],[0,0]],'u1'))]:
                (root/name).write_bytes(gzip.compress(data.tobytes()))
            f=EstimatedCityFields(root,{'temperature':dict(shape=[2,2],dtype='<f2',parts=['field.gz','field.gz'],mask='mask.gz',times_s=[0,600],origin_xy_m=[0,0],cell_m=8)})
            self.assertIsNone(f.sample('temperature',4,4,300))
            self.assertIsNone(f.estimate('temperature',4,4,300,7)[0])
            value,audit=f.estimate('temperature',4,4,300,8)
            self.assertEqual(value,30);self.assertEqual(audit['distance_m'],8)
            self.assertEqual(audit['donor_cell_yx'],[0,1])
            self.assertIsNone(f.sample('temperature',4,4,300))
            self.assertIsNone(f.estimate('temperature',4,4,601,100)[0])

    def test_score_equation_and_shared_loss_allocation(self):
        ref=dict(lower=12,upper=20,scale=4)
        good=health_details(0,22,0,16,ref);self.assertEqual(good['score'],100)
        result=health_details(15,30,800,24,ref)
        thermal=36.;burden=.35+.15*((thermal-26)/8)**2+.5*1.5**2
        self.assertAlmostEqual(result['score'],100*np.exp(-np.log(100/90)*burden))
        self.assertAlmostEqual(sum(result['contributions'].values()),100-result['score'])
        self.assertIsNone(health_details(15,None,800,24,ref))

    def test_original_transition_only_updates_at_300_seconds_and_inputs_are_used(self):
        class Runtime:
            start=pd.Timestamp('2022-01-01',tz='UTC')
            columns=['pm2_5','temperature','humidity','act_level','step_count','walking','hour_sin','hour_cos']
            def __init__(self):
                self.mean=np.zeros(9);self.states={0:SimpleNamespace(phase=0.,updates=0,last=16.,accumulated=np.zeros(8)),600:None}
            def br(self,s):return np.array([s.last,s.last])
            def features(self,t):return np.array([999,999,50,1,20,1,0,1.])
            def advance(self,s,x,d):
                a=s.accumulated+x*d;phase=s.phase+d;updates=s.updates;last=s.last
                if phase>=300-1e-7:last=16+a[0]/300*.1;phase=0;updates+=1;a=np.zeros(8)
                return SimpleNamespace(phase=phase,updates=updates,last=last,accumulated=a)
        class Fields:
            metadata={'pmx':{'times_s':[0,600]},'temperature':{'times_s':[0,600]}}
            def __init__(self,pm):self.pm=pm
            def estimate(self,k,*args):return (self.pm if k=='pmx' else 20),{'method':'native_cell','distance_m':0}
            def sample(self,k,*args):return {'pmx':None,'temperature':None,'sunlight':0}[k]
        policy=dict(followup_until_elapsed_s=600,breathing_history_offset_s=0,max_pmx_fill_m=16,max_temperature_fill_m=128,assumed_background_pm25_ug_m3=6,pmx_to_pm25_proxy_fraction=1,solar_warming_c_per_800=6)
        recording=dict(samples=[dict(seconds=0,enu_m=[0,0,0],scene_m=[0,0,0]),dict(seconds=100,enu_m=[10,0,0],scene_m=[10,0,0])],departure_s=0,duration_s=100,missing_policy='raw null')
        baseline=[dict(q10=12,q90=20,scale=4,mode='test',count=5)]
        low=evaluate(recording,Fields(0),Runtime(),baseline,policy)
        high=evaluate(recording,Fields(10),Runtime(),baseline,policy)
        self.assertEqual([s['seconds'] for s in low['breathing_trace']],[0,300,600])
        self.assertEqual(low['samples'][299]['breathing'],16)
        self.assertAlmostEqual(low['samples'][300]['breathing'],16.6)
        self.assertAlmostEqual(high['samples'][300]['breathing'],17.6)
        self.assertEqual(low['samples'][-1]['scene_m'],[10,0,0])
        self.assertEqual(low['samples'][-1]['phase'],'assumed_stationary_followup')
        self.assertIsNone(low['samples'][0]['temperature'])
        self.assertEqual(low['samples'][0]['temperature_estimate'],20)
        self.assertEqual(recording['duration_s'],100)
        # A stationary crossing wait advances dose and the same recurrent clock.
        waited=copy.deepcopy(recording)
        waited['samples']=[dict(seconds=0,enu_m=[0,0,0],scene_m=[0,0,0]),dict(seconds=350,enu_m=[0,0,0],scene_m=[0,0,0]),dict(seconds=450,enu_m=[10,0,0],scene_m=[10,0,0])]
        waited.update(duration_s=450,route_timeline=[dict(kind='Waiting',start=0,end=350,crossing_id='synthetic'),dict(kind='Crossing',start=350,end=450,crossing_id='synthetic')],crossing_summary={})
        computed=evaluate(waited,Fields(10),Runtime(),baseline,policy)
        self.assertAlmostEqual(computed['crossing_summary']['waiting_pollution_proxy_ug_s_m3'],350*16)
        self.assertAlmostEqual(computed['crossing_summary']['integrated_pollution_proxy_ug_s_m3'],600*16)
        self.assertEqual(computed['samples'][300]['movement_state'],'Waiting')
        self.assertEqual(computed['samples'][300]['scene_m'],[0,0,0])
        self.assertEqual(computed['samples'][300]['model_updates'],1)
        self.assertEqual(computed['samples'][350]['movement_state'],'Crossing')
        self.assertTrue(all(r['health_score'] is not None for r in computed['samples']))
        # A later departure can collapse adjacent elapsed floats on the world
        # clock. The generated result must still satisfy the Asset contract.
        shifted=copy.deepcopy(recording);shifted['departure_s']=14400
        a=23.653542490217554;b=float(np.nextafter(a,np.inf))
        shifted['samples'][1:1]=[dict(seconds=t,enu_m=[t/10,0,0],scene_m=[t/10,0,0]) for t in [a,b]]
        runtime=Runtime();runtime.states[14400]=runtime.states[0];runtime.states[15000]=None
        fields=Fields(10);fields.horizon_s=15000
        shifted_result=evaluate(shifted,fields,runtime,baseline,policy)
        clock=[r['world_seconds'] for r in shifted_result['samples']]
        self.assertTrue(all(x<y for x,y in zip(clock,clock[1:])))
        self.assertEqual(clock[0],14400);self.assertEqual(clock[-1],15000)
        self.assertEqual(shifted_result['samples'][-1]['scene_m'],[10,0,0])
        self.assertEqual(shifted_result['physiology_audit']['updates'],[300,600])
