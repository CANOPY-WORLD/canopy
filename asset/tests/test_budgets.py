"""Exercise budget boundaries and publication bypasses using tiny synthetic manifests."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
import check_budgets as budgets


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def scenario(self, name='test', geometry=(75_000_000, 75_000_000), physics=()):
        scene = self.root / 'scenario' / name
        files = [{'path': f'{group}/{i}.gz', 'viewer_path': f'scenes/{name}/{group}/{i}.gz',
                  'bytes': size, 'sha256': 'b' * 64}
                 for group, sizes in [('geometry', geometry), ('physics', physics)]
                 for i, size in enumerate(sizes)]
        manifest = {'schema_version': '1.0.0', 'kind': 'canopy.publication', 'scenario_id': name,
                    'snapshot': 'v1', 'files': files, 'bytes': sum(f['bytes'] for f in files)}
        write(scene / 'scenario.json', {'id': name})
        write(scene / 'asset-budget.json', {'schema_version': '1.0.0', 'scenario_id': name, 'groups': {
            'geometry': {'prefixes': ['geometry/'], 'files': []},
            'physics_state': {'prefixes': ['physics/'], 'files': []}}})
        reference = {'schema_version': '1.0.0', 'kind': 'canopy.publication-reference', 'scenario_id': name,
                     'repository': 'https://github.com/example/data', 'revision': 'a' * 40,
                     'website': 'https://example.github.io/data/', 'snapshot': 'v1',
                     'base_url': 'https://example.github.io/data/snapshots/v1/',
                     'manifest': {'path': 'data/manifest.json'}}
        self.save(scene, manifest, reference)
        ids = sorted(p.parent.name for p in (self.root / 'scenario').glob('*/scenario.json'))
        write(self.root / 'visualizer/site/scenes/index.json', {'default': ids[0], 'scenes': [{'id': n} for n in ids]})
        return scene, manifest, reference

    def save(self, scene, manifest, reference):
        write(scene / 'data/manifest.json', manifest)
        reference['manifest']['sha256'] = hashlib.sha256((scene / 'data/manifest.json').read_bytes()).hexdigest()
        write(scene / 'publication.json', reference)

    def tree(self, manifest):
        return {'truncated': False, 'tree': [
            {'path': 'snapshots/v1/' + f['path'], 'type': 'blob', 'mode': '100644', 'size': f['bytes']}
            for f in manifest['files']]}

    def test_exact_category_limit_passes(self):
        self.scenario()
        result = budgets.check(self.root)
        self.assertTrue(result['passed'])
        self.assertEqual(result['limit_bytes'], 150_000_000)
        self.assertEqual(result['total_limit_bytes'], 200_000_000)

    def test_one_byte_over_each_category_fails(self):
        for category in ('geometry', 'physics_state'):
            with self.subTest(category=category):
                self.scenario(geometry=(75_000_000, 75_000_001) if category == 'geometry' else (),
                              physics=(75_000_000, 75_000_001) if category == 'physics_state' else ())
                result = budgets.check(self.root)
                self.assertFalse(result['passed'])
                self.assertEqual(result['scenarios'][0]['groups'][category]['over_bytes'], 1)

    def test_exact_total_and_one_byte_over_total(self):
        self.scenario(geometry=(50_000_000, 50_000_000), physics=(50_000_000, 50_000_000))
        self.assertTrue(budgets.check(self.root)['passed'])
        self.scenario(geometry=(50_000_000, 50_000_000), physics=(50_000_000, 50_000_001))
        result = budgets.check(self.root)
        self.assertFalse(result['passed'])
        self.assertTrue(all(g['passed'] for g in result['scenarios'][0]['groups'].values()))
        self.assertEqual(result['scenarios'][0]['over_bytes'], 1)

    def test_multiple_scenarios_are_budgeted_separately(self):
        self.scenario('one')
        self.scenario('two')
        result = budgets.check(self.root)
        self.assertTrue(result['passed'])
        self.assertEqual(sum(s['total_bytes'] for s in result['scenarios']), 300_000_000)

    def test_unclassified_and_double_classified_payloads_fail(self):
        scene, manifest, reference = self.scenario()
        manifest['files'][0]['path'] = 'unclassified/blob.gz'
        self.save(scene, manifest, reference)
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            budgets.check(self.root)
        scene, _, _ = self.scenario()
        p = json.loads((scene / 'asset-budget.json').read_bytes())
        p['groups']['physics_state']['prefixes'].append('geometry/')
        write(scene / 'asset-budget.json', p)
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            budgets.check(self.root)

    def test_policy_cannot_exempt_resources_or_override_limit(self):
        scene, _, _ = self.scenario()
        original = json.loads((scene / 'asset-budget.json').read_bytes())
        for extra in ({'limit_bytes': 1_000_000_000}, {'exclude': ['geometry/']}, {'schema_version': '2.0.0'}):
            with self.subTest(extra=extra):
                write(scene / 'asset-budget.json', original | extra)
                with self.assertRaisesRegex(ValueError, 'Invalid asset budget'):
                    budgets.check(self.root)
        write(scene / 'asset-budget.json', original)
        (scene / 'asset-budget.json').unlink()
        with self.assertRaises(FileNotFoundError):
            budgets.check(self.root)

    def test_invalid_prefixes_fail(self):
        scene, _, _ = self.scenario()
        p = json.loads((scene / 'asset-budget.json').read_bytes())
        for name in ('geometry', '../', '/', 'geometry//', 'geometry/%2e%2e/'):
            with self.subTest(name=name):
                p['groups']['geometry']['prefixes'] = [name]
                write(scene / 'asset-budget.json', p)
                with self.assertRaises(ValueError):
                    budgets.check(self.root)

    def test_deleted_manifest_cannot_hide_one_public_scenario(self):
        self.scenario('one')
        scene, _, _ = self.scenario('two')
        (scene / 'data/manifest.json').unlink()
        with self.assertRaisesRegex(ValueError, 'missing its budgeted'):
            budgets.check(self.root)

    def test_locked_hash_duplicates_sizes_and_total_cannot_be_forged(self):
        scene, manifest, reference = self.scenario()
        broken = copy.deepcopy(manifest)
        broken['bytes'] += 1
        write(scene / 'data/manifest.json', broken)
        with self.assertRaisesRegex(ValueError, 'checksum'):
            budgets.check(self.root)
        for mutate in (lambda m: m.update(bytes=m['bytes']+1),
                       lambda m: m['files'].append(m['files'][0]),
                       lambda m: m['files'][0].update(bytes=-1),
                       lambda m: m['files'][0].update(bytes=True)):
            broken = copy.deepcopy(manifest)
            mutate(broken)
            self.save(scene, broken, reference)
            with self.assertRaises(ValueError):
                budgets.check(self.root)

    def test_local_payload_bytes_are_verified_and_private_data_is_excluded(self):
        scene, manifest, _ = self.scenario(geometry=(6,))
        (scene / 'publication.json').unlink()
        payload = scene / 'data/geometry/0.gz'
        payload.parent.mkdir()
        payload.write_bytes(b'public')
        manifest['files'][0]['sha256'] = hashlib.sha256(b'public').hexdigest()
        write(scene / 'data/manifest.json', manifest)
        write(self.root / 'asset/data/private.json', {'private': 'retained'})
        self.assertEqual(budgets.check(self.root)['scenarios'][0]['total_bytes'], 6)
        payload.write_bytes(b'forged')
        with self.assertRaisesRegex(ValueError, 'checksum/size mismatch'):
            budgets.check(self.root)

    def test_remote_tree_sizes_missing_files_and_symlinks_fail(self):
        _, manifest, _ = self.scenario()
        original = self.tree(manifest)
        budgets.verify_tree(manifest, original)
        mutations = [lambda t: t.update(truncated=True),
                     lambda t: t['tree'][0].update(size=1),
                     lambda t: t['tree'][0].update(mode='120000'),
                     lambda t: t['tree'].pop(),
                     lambda t: t['tree'].append(dict(t['tree'][0], path='snapshots/v1/extra.bin'))]
        for mutate in mutations:
            broken = copy.deepcopy(original)
            mutate(broken)
            with self.assertRaises(ValueError):
                budgets.verify_tree(manifest, broken)

    def test_remote_verification_uses_pinned_and_served_manifests(self):
        scene, manifest, _ = self.scenario()
        data = (scene / 'data/manifest.json').read_bytes()
        with patch.object(budgets, 'request_bytes', side_effect=[data, data, json.dumps(self.tree(manifest)).encode()]) as fetch:
            result = budgets.check(self.root, remote=True)
            self.assertTrue(result['passed'])
            self.assertEqual(fetch.call_count, 3)
            self.assertIn('/' + 'a' * 40 + '/', fetch.call_args_list[0].args[0])
            self.assertIn('remote Git blob sizes', result['scenarios'][0]['verification'])
        with patch.object(budgets, 'request_bytes', return_value=b'forged'):
            with self.assertRaisesRegex(ValueError, 'manifests disagree'):
                budgets.check(self.root, remote=True)

    def test_markdown_failure_is_actionable(self):
        self.scenario(geometry=(75_000_000, 75_000_001))
        text = budgets.markdown(budgets.check(self.root))
        self.assertIn('150,000,001', text)
        self.assertIn('FAIL', text)
        self.assertIn('geometry/1.gz', text)

    def test_inventory_redirect_is_rejected_before_forwarding_request(self):
        with self.assertRaisesRegex(ValueError, 'redirected'):
            budgets.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://another.example/')

    def test_publisher_stops_before_building_when_budget_check_fails(self):
        spec = importlib.util.spec_from_file_location('budget_test_publisher',
            Path(__file__).parents[2] / 'visualizer/tools/publish_pages.py')
        publisher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(publisher)
        with patch.object(publisher, 'ROOT', self.root), \
             patch.object(publisher, 'git', side_effect=['main', '', 'a' * 40, 'a' * 40 + '\trefs/heads/main']), \
             patch.object(publisher.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'budget-check')) as run, \
             patch.object(publisher, 'build') as build:
            with self.assertRaises(subprocess.CalledProcessError):
                publisher.publish()
            self.assertIn('--verify-remote', run.call_args.args[0])
            self.assertTrue(run.call_args.kwargs['check'])
            build.assert_not_called()
            self.assertFalse((self.root / 'cache').exists())


if __name__ == '__main__':
    unittest.main()
