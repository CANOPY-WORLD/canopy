"""Publication boundary tests use tiny fixtures, never retained research data."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('build_pages', Path(__file__).parents[1] / 'tools/build_pages.py')
pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / 'scenario/test/data'
        self.data.mkdir(parents=True)
        (self.data.parent / 'scenario.json').write_text('{}')
        (self.data / 'sample.bin').write_bytes(b'public')
        self.manifest = {'schema_version': '1.0.0', 'kind': 'canopy.publication',
            'scenario_id': 'test', 'bytes': 6, 'files': [
                {'path': 'sample.bin', 'viewer_path': 'scenes/test/sample.bin',
                 'bytes': 6, 'sha256': hashlib.sha256(b'public').hexdigest()}]}
        self.save()

    def save(self):
        (self.data / 'manifest.json').write_text(json.dumps(self.manifest))

    def test_only_declared_scenario_data_is_selected(self):
        private = self.root / 'asset/data/project/test/secret.bin'
        private.parent.mkdir(parents=True)
        private.write_bytes(b'private')
        resources, manifests = pages.publications(self.root)
        self.assertEqual(list(resources), ['scenes/test/sample.bin'])
        self.assertEqual(resources['scenes/test/sample.bin']['path'], 'scenario/test/data/sample.bin')
        self.assertEqual(len(manifests), 1)

    def test_tampering_and_unlisted_files_are_rejected(self):
        (self.data / 'sample.bin').write_bytes(b'broken')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            pages.publications(self.root)
        (self.data / 'sample.bin').write_bytes(b'public')
        (self.data / 'private.bin').write_bytes(b'private')
        with self.assertRaisesRegex(ValueError, 'Unlisted'):
            pages.publications(self.root)

    def test_path_escape_and_symlinks_are_rejected(self):
        for name in ('../secret', '/secret', 'data/%2e%2e/secret', 'a\\b', 'https://host/data'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                pages.bounded(self.data, name)
        (self.root / 'secret').write_text('secret')
        (self.data / 'escape').symlink_to(self.root / 'secret')
        with self.assertRaises(ValueError):
            pages.bounded(self.data, 'escape')

    def test_duplicate_routes_and_wrong_owner_are_rejected(self):
        self.manifest['files'] *= 2
        self.save()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            pages.publications(self.root)
        self.manifest['scenario_id'] = 'someone_else'
        self.save()
        with self.assertRaisesRegex(ValueError, 'Invalid public Scenario'):
            pages.publications(self.root)


if __name__ == '__main__':
    unittest.main()
