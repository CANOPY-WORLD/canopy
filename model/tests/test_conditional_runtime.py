"""Fictional physiology and Health-only policy boundaries."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from healthy_route.conditional_runtime import Runtime, read_profile
from canopy.models.registry import describe


class ConditionalRuntimeTests(unittest.TestCase):
    def test_explicit_synthetic_profile_and_partition_invariance(self):
        import torch
        torch.set_num_threads(1)
        profile=json.loads((Path(__file__).parent/'fixtures/canopy/city_physiology_inputs.json').read_text())
        before=copy.deepcopy(profile)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'physiology.json').write_text(json.dumps(profile))
            runtime=Runtime(root,particles=2)
            features=np.asarray(profile['features'][0])
            initial=runtime.initial
            split=runtime.advance(runtime.advance(initial,features,75),features,225)
            whole=runtime.advance(initial,features,300)
            np.testing.assert_allclose(runtime.br(split),runtime.br(whole))
            self.assertEqual(split.updates,1)
            self.assertEqual(initial.updates,0)
            self.assertEqual(runtime.input_kind,'synthetic')
            self.assertEqual(read_profile(root),before)
            for change in [{'input_kind':'authorized_history'},{'features':[[0]*7]}, {'start_utc':'2026-01-01'}, {'history':[[0]*9]*12}]:
                (root/'physiology.json').write_text(json.dumps({**profile,**change}))
                with self.assertRaises(ValueError):read_profile(root)

    def test_replay_is_not_a_global_or_other_method_parameter(self):
        walk=describe('healthy_route','city_walk')
        self.assertEqual(walk['parameters']['properties']['field_time_policy']['default'],'native')
        for model,method in [('healthy_route','breathing_cvae'),('temperature','finite_difference_numpy'),('solar','shadow')]:
            spec=describe(model,method)
            self.assertNotIn('field_time_policy',spec['parameters']['properties'])
            self.assertNotIn('spatial_missing_method',spec['parameters']['properties'])
