"""Synthetic numerical parity against the original Health temporal extension."""
import gzip
import tempfile
import unittest
from pathlib import Path
import numpy as np
from healthy_route.city_physiology import EstimatedCityFields
from healthy_route.health_time import HealthReplayFields, replay_clock, time_coverage


class HealthTimeTests(unittest.TestCase):
    def test_coverage_follows_model_and_solar_not_short_source_fields(self):
        fields={k:dict(times_s=[0,300,600]) for k in ['pmx','temperature']}
        fields['sunlight']=dict(times_s=[0,43200,86400],clock_offset_s=31800)
        policy=dict(breathing_history_offset_s=39600,field_time_policy='health_replay',field_replay_blend_s=60)
        self.assertEqual(time_coverage(fields,policy,86400)['horizon_s'],46800)
        self.assertEqual(time_coverage(fields,{**policy,'field_time_policy':'native'},86400)['horizon_s'],600)
        self.assertEqual(time_coverage(fields,{**policy,'breathing_history_offset_s':86000},86400)['horizon_s'],400)
        fields['sunlight']['times_s'][-1]=33000
        self.assertEqual(time_coverage(fields,policy,86400)['horizon_s'],1200)

    def test_replay_matches_original_blending_without_changing_native_samples(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);metadata={}
            for key,values,times in [('temperature',[20,30,40],[0,300,600]),('pmx',[1,3,5],[0,300,600]),('sunlight',[0,800,0],[0,43200,86400])]:
                parts=[]
                for i,v in enumerate(values):
                    name=f'{key}{i}.gz';(root/name).write_bytes(gzip.compress(np.array([[v]],'<f2').tobytes()));parts.append(name)
                name=key+'mask.gz';(root/name).write_bytes(gzip.compress(b'\x00'))
                metadata[key]=dict(shape=[1,1],origin_xy_m=[0,0],cell_m=8,dtype='<f2',parts=parts,mask=name,times_s=times,clock_offset_s=31800 if key=='sunlight' else 0)
            policy=dict(breathing_history_offset_s=39600,field_time_policy='health_replay',field_replay_blend_s=60)
            coverage=time_coverage(metadata,policy,86400);f=HealthReplayFields(root,metadata,coverage)
            native=EstimatedCityFields(root,metadata)
            before={p.name:p.read_bytes() for p in root.iterdir()}
            for t in [0,539.9,540,570,599.99,600,601,1170,1200,3600,46799,46800]:
                value,audit=f.estimate('temperature',4,4,t,0)
                source=t%600;weight=max(0,min(1,(source-540)/60));weight=weight*weight*(3-2*weight)
                self.assertAlmostEqual(value,(20+source/30)*(1-weight)+20*weight)
                self.assertEqual(audit['time_transform']['cycle_index'],int(t//600))
                self.assertAlmostEqual(audit['time_transform']['source_seconds'],t%600)
            self.assertEqual(f.sample('temperature',4,4,600),40)
            self.assertIsNone(f.sample('temperature',4,4,601))
            self.assertIsNone(native.estimate('temperature',4,4,601,0)[0])
            self.assertIsNone(f.estimate('temperature',4,4,46801,0)[0])
            self.assertEqual(f.sample('sunlight',4,4,3600),native.sample('sunlight',4,4,3600))
            self.assertNotEqual(f.sample('sunlight',4,4,600),f.sample('sunlight',4,4,1200))
            self.assertEqual(before,{p.name:p.read_bytes() for p in root.iterdir()})

    def test_blend_is_continuous_at_cycle_boundary_and_rejects_invalid_times(self):
        for boundary in [600,1200,46800]:
            source,weight,_=replay_clock(boundary-1e-5,0,600,60)
            v=(20+source/30)*(1-weight)+20*weight
            self.assertAlmostEqual(v,20,places=8)
            self.assertEqual(replay_clock(boundary,0,600,60)[:2],(0,0))
        for t in [-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):replay_clock(t,0,600,60)
