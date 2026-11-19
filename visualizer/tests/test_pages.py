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

    def remote(self):
        self.manifest['snapshot'] = 'test-v1'
        self.save()
        (self.data / 'sample.bin').unlink()
        reference = {'schema_version': '1.0.0', 'kind': 'canopy.publication-reference',
            'scenario_id': 'test', 'snapshot': 'test-v1', 'revision': 'a' * 40,
            'repository': 'https://github.com/example/canopy-test',
            'website': 'https://example.github.io/canopy-test/',
            'base_url': 'https://example.github.io/canopy-test/snapshots/test-v1/',
            'manifest': {'path': 'data/manifest.json', 'sha256': pages.checksum(self.data / 'manifest.json')}}
        (self.data.parent / 'publication.json').write_text(json.dumps(reference))
        return reference

    def frontend(self):
        for name in ('index.html', 'preload.js', 'asset-router.js', 'scenes/index.json'):
            path = self.root / 'visualizer/site' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'default': 'test', 'scenes': [{'id': 'test'}]}) if name.endswith('.json') else 'fixture')
        path = self.root / 'visualizer/src/visualization/public-scenes.json'
        path.parent.mkdir(parents=True)
        path.write_text('{}')
        for name in ('scenario-tabs.mjs', 'scenario-tabs.css'):
            path = self.root / 'visualizer/src/visualization/shared' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture')
        for name in ('index.html', 'style.css', 'app.js', 'inventory.json', 'architecture.svg'):
            path = self.root / 'visualizer/guide' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{}')

    def test_remote_payloads_are_referenced_but_never_packaged(self):
        reference = self.remote()
        self.frontend()
        output = self.root / 'output'
        report = pages.build(self.root, output, refresh=True)
        self.assertEqual(report['bundled_data_bytes'], 0)
        self.assertEqual(report['remote_data_bytes'], 6)
        self.assertFalse((output / 'scenario/test/data/sample.bin').exists())
        routes = json.loads((output / 'asset-sources.json').read_bytes())
        self.assertEqual(routes['remote_bases'], [reference['base_url']])
        self.assertEqual(routes['resources']['scenes/test/sample.bin'], reference['base_url'] + 'sample.bin')
        index = json.loads((output / 'scenario-index.json').read_bytes())
        self.assertEqual(index['scenarios'][0]['repository'], reference['repository'])
        self.assertEqual(report['bytes'], sum(p.stat().st_size for p in output.rglob('*') if p.is_file()))

    def test_remote_reference_is_locked_to_the_manifest(self):
        self.remote()
        self.manifest['files'][0]['sha256'] = 'b' * 64
        self.save()
        with self.assertRaisesRegex(ValueError, 'manifest checksum'):
            pages.publications(self.root)

    def test_remote_reference_rejects_credentials_traversal_and_unpinned_versions(self):
        reference = self.remote()
        for url in ('http://data.test/snapshots/test-v1/', 'https://user:password@data.test/snapshots/test-v1/',
                    'https://data.test/../snapshots/test-v1/', 'https://data.test/%2e%2e/snapshots/test-v1/',
                    'https://data.test/snapshots/test-v1/?token=secret', 'https://data.test/latest/'):
            with self.subTest(url=url):
                reference['base_url'] = url
                (self.data.parent / 'publication.json').write_text(json.dumps(reference))
                with self.assertRaises(ValueError):
                    pages.publications(self.root)

    def test_remote_scenario_does_not_allow_a_shadow_payload(self):
        self.remote()
        (self.data / 'sample.bin').write_bytes(b'public')
        with self.assertRaisesRegex(ValueError, 'Unlisted'):
            pages.publications(self.root)

    def test_disabled_website_features_leave_snapshot_intact_and_skip_downloads(self):
        reference = self.remote()
        self.frontend()
        original_manifest = (self.data / 'manifest.json').read_bytes()
        profile = {'schema_version': '1.0.0', 'kind': 'canopy.website-profile',
                   'scenario_id': 'test', 'features': {
                       'traffic': {'enabled': False, 'resources': ['sample.bin']}}}
        path = self.data.parent / 'website.json'
        path.write_text(json.dumps(profile))
        _, files, routing, download = pages.generated(self.root)
        self.assertEqual((self.data / 'manifest.json').read_bytes(), original_manifest)
        self.assertEqual(json.loads(routing)['resources']['scenes/test/sample.bin'], reference['base_url'] + 'sample.bin')
        self.assertNotIn('scenes/test/sample.bin', {r['path'] for r in json.loads(download)['files']})
        index = json.loads(files['scenario-index.json'])['scenarios'][0]
        self.assertEqual((index['bytes'], index['files'], index['snapshot_bytes'], index['excluded_bytes']), (0, 0, 6, 6))
        scene = json.loads(files['scenes/index.json'])['scenes'][0]
        self.assertEqual(json.loads(files[scene['website_profile']]), profile)
        profile['features']['traffic']['enabled'] = True
        path.write_text(json.dumps(profile))
        _, _, _, download = pages.generated(self.root)
        self.assertIn('scenes/test/sample.bin', {r['path'] for r in json.loads(download)['files']})

    def test_website_profile_rejects_unknown_features_and_unlisted_resources(self):
        profile = {'schema_version': '1.0.0', 'kind': 'canopy.website-profile',
                   'scenario_id': 'test', 'features': {}}
        path = self.data.parent / 'website.json'
        for name, feature in (
            ('unknown', {'enabled': False, 'resources': []}),
            ('birds', {'enabled': 'false', 'resources': []}),
            ('birds', {'enabled': False, 'resources': ['not-in-the-snapshot.bin']}),
            ('birds', {'enabled': False, 'resources': ['../private.bin']}),
            ('birds', {'enabled': False, 'resources': ['sample.bin', 'sample.bin']}),
        ):
            profile['features'] = {name: feature}
            path.write_text(json.dumps(profile))
            with self.subTest(feature=feature), self.assertRaises(ValueError):
                pages.website_profile(self.data.parent, self.manifest)

    def test_downloads_are_scoped_to_the_selected_scenario(self):
        reference = self.remote()
        self.frontend()
        other = self.root / 'scenario/another/data'
        other.mkdir(parents=True)
        (other.parent / 'scenario.json').write_text('{}')
        second = json.loads(json.dumps(self.manifest))
        second['scenario_id'] = 'another'
        second['files'][0]['viewer_path'] = 'scenes/another/sample.bin'
        (other / 'manifest.json').write_text(json.dumps(second))
        reference.update(scenario_id='another', base_url='https://example.github.io/another/snapshots/test-v1/')
        reference['manifest']['sha256'] = pages.checksum(other / 'manifest.json')
        (other.parent / 'publication.json').write_text(json.dumps(reference))
        output = self.root / 'output'
        pages.build(self.root, output, refresh=True)
        for owner, excluded in [('test', 'another'), ('another', 'test')]:
            download = json.loads((output / f'download-manifests/{owner}.json').read_bytes())
            names = {f['path'] for f in download['files']}
            self.assertIn(f'scenes/{owner}/sample.bin', names)
            self.assertNotIn(f'scenes/{excluded}/sample.bin', names)


if __name__ == '__main__':
    unittest.main()
