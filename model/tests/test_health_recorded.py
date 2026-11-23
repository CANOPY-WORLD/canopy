"""The selected public recording replays exact bytes without model execution."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('health_example_launcher', ROOT/'model/tools/run_health_example.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class RecordedHealthTests(unittest.TestCase):
    def test_replay_preserves_identity_and_never_executes_model(self):
        from canopy.assets.store import load
        from common.storage import Storage
        with tempfile.TemporaryDirectory() as folder, patch.object(launcher, 'run', side_effect=AssertionError('Replay ran inference')):
            workspace, scene, result = launcher.prepare(Path(folder)/'replay', recorded=True)
            pin = json.loads((ROOT/'model/healthy_route/DEMO_RESULT.json').read_text())
            self.assertEqual(result['assets'], [pin['asset_ref']])
            asset, manifest, _ = load(Storage.load(workspace), scene, pin['asset_ref'])
            self.assertEqual(asset['derived_from'], [])
            self.assertEqual(manifest['time']['samples'], list(range(0, 3601, 300)))
            self.assertFalse(manifest['spatial']['georeferenced'])
            self.assertEqual(asset['payload']['sha256'], pin['files']['manifest.json'])

    def test_corrupt_recording_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copytree(ROOT/'model/tests/fixtures/health_recorded', root/'model/tests/fixtures/health_recorded')
            (root/'model/healthy_route').mkdir(parents=True)
            shutil.copyfile(ROOT/'model/healthy_route/DEMO_RESULT.json', root/'model/healthy_route/DEMO_RESULT.json')
            (root/'model/tests/fixtures/health_recorded/trajectory.json').write_text('{}')
            with patch.object(launcher, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'checksum mismatch: trajectory.json'):
                    launcher.recorded_input()
