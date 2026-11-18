"""Original upstream-loop parity and Canopy integration boundary checks."""
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import torch

from canopy.models.nn4pdes import UpstreamLinear, SOURCE, UPSTREAM_SHA256, source_identity


FIXTURES = Path(__file__).parent / "fixtures/nn4pdes"


class NN4PDEsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.threads = torch.get_num_threads()
        torch.set_num_threads(1)

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.threads)

    def test_original_standalone_loop_reference(self):
        record = json.loads((FIXTURES / "reference.json").read_text())
        self.assertEqual(record["upstream_sha256"], UPSTREAM_SHA256)
        for case in record["cases"]:
            with self.subTest(case=case["name"]):
                path = FIXTURES / case["file"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), case["sha256"])
                with np.load(path, allow_pickle=False) as arrays:
                    solver = UpstreamLinear(arrays["height"], arrays["solid"], case["spacing"],
                                            case["dt"], case["initial_depth"], case["rain_mm_h"])
                    for step in range(1, max(case["steps"]) + 1):
                        solver.step()
                        solver.diagnostics()
                        if step in case["steps"]:
                            depth, velocity = solver.snapshot()
                            np.testing.assert_allclose(depth, arrays[f"depth_{step}"], rtol=2e-6, atol=2e-8)
                            np.testing.assert_allclose(velocity[0], -arrays[f"native_u_{step}"], rtol=2e-6, atol=2e-8)
                            np.testing.assert_allclose(velocity[1], arrays[f"native_v_{step}"], rtol=2e-6, atol=2e-8)
                            self.assertFalse(velocity[2].any())

    def solver(self, spacing=2):
        return UpstreamLinear(np.zeros((8, 12), np.float32), np.zeros((8, 12), np.uint8), spacing, .1, 0, 20)

    def test_original_stencil_directions_and_export(self):
        solver = self.solver()
        y, x = torch.meshgrid(torch.arange(10.) * 2, torch.arange(14.) * 2, indexing="ij")
        with torch.no_grad():
            np.testing.assert_allclose(solver.model.xadv(x[None, None]).numpy(), -1, atol=1e-6)
            np.testing.assert_allclose(solver.model.yadv(y[None, None]).numpy(), 1, atol=1e-6)
        solver.state["values_u"].fill_(-3)
        solver.state["values_v"].fill_(5)
        _, vector = solver.snapshot()
        np.testing.assert_equal(vector[0], 3); np.testing.assert_equal(vector[1], 5)

    def test_instances_do_not_share_upstream_globals(self):
        first = self.solver(spacing=2)
        second = self.solver(spacing=7)
        reference = self.solver(spacing=2)
        for _ in range(5):
            first.step(); second.step(); reference.step()
        for actual, expected in zip(first.snapshot(), reference.snapshot()):
            np.testing.assert_array_equal(actual, expected)
        self.assertIsNot(first.model.forward.__globals__, second.model.forward.__globals__)

    def test_nonfinite_negative_and_upstream_correction_failure(self):
        for field, value, message in [("values_u", float("nan"), "nonfinite"),
                                       ("values_h", -.1, "negative water depth"),
                                       ("values_hh", 11, "upstream 10 m limit")]:
            with self.subTest(field=field):
                solver = self.solver()
                solver.state[field].fill_(value)
                with self.assertRaisesRegex(ValueError, message):
                    solver.diagnostics()

    def test_modified_upstream_code_is_rejected(self):
        original = Path.read_bytes
        def tampered(path):
            value = original(path)
            return value + b"\n# changed" if path == SOURCE else value
        with patch.object(Path, "read_bytes", tampered):
            with self.assertRaisesRegex(ValueError, "pinned upstream revision"):
                source_identity()


if __name__ == "__main__":
    unittest.main()
