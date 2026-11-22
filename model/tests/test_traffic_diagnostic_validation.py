import importlib.util
from pathlib import Path
import tempfile
import unittest

path = Path(__file__).resolve().parents[1] / 'src/traffic/diagnostic_validation.py'
spec = importlib.util.spec_from_file_location('diagnostic_validation', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DiagnosticValidationTests(unittest.TestCase):
    def assess(self, log='', collisions='', summary=None):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'collisions.xml').write_text('<collisions>' + collisions + '</collisions>')
            (root / 'summary.xml').write_text(summary or '<summary><step time="1" teleports="0" discarded="0"/></summary>')
            (root / 'sumo.log').write_text(log)
            (root / 'config.json').write_text('{"command":["--end","1.1","--step-length","0.1"]}')
            return module.assess_run(root)

    def test_zero_collisions_does_not_certify_system(self):
        result = self.assess()
        self.assertTrue(result['diagnostic_pass'])
        self.assertFalse(result['traffic_system_validated'])

    def test_zero_collisions_with_invalid_route_fails(self):
        result = self.assess("Warning: Vehicle 'a' performs emergency stop at the end of lane 'b' because there is no connection to the next edge")
        self.assertFalse(result['diagnostic_pass'])
        self.assertEqual(result['emergency_stops'], 1)
        self.assertEqual(len(result['invalid_route_warnings']), 1)

    def test_missing_signal_detector_requires_review(self):
        result = self.assess("Warning: At actuated tlLogic 'a', linkIndex 1 has no controlling detector.")
        self.assertFalse(result['diagnostic_pass'])

    def test_collision_and_discard_are_not_hidden(self):
        result = self.assess(collisions='<collision/>', summary='<summary><step time="1" teleports="1" discarded="2"/></summary>')
        self.assertEqual([x['check'] for x in result['failed_checks']], ['collisions', 'teleports', 'discarded'])

    def test_empty_summary_rejected(self):
        with self.assertRaisesRegex(ValueError, 'no summary'):
            self.assess(summary='<summary/>')

    def test_summary_collision_cannot_be_hidden_by_empty_collision_file(self):
        result = self.assess(summary='<summary><step time="1" collisions="2"/></summary>')
        self.assertFalse(result['diagnostic_pass'])
        self.assertEqual(result['collisions'], 2)

    def test_truncated_run_is_not_accepted(self):
        result = self.assess(summary='<summary><step time="0.5" teleports="0"/></summary>')
        self.assertFalse(result['diagnostic_pass'])
        self.assertFalse(result['requested_interval_complete'])

    def test_invalid_departure_is_not_silently_repositioned(self):
        result = self.assess("Warning: Invalid departPos 7 given for vehicle 'a'. Inserting at lane end instead.")
        self.assertFalse(result['diagnostic_pass'])
