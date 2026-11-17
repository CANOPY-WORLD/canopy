"""Exercise the domain layout through storage, imported data and public HTTP routes."""
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from common.layout import source_path
from common.storage import Storage
from canopy.assets.store import import_run
from canopy.scenario.store import create
from canopy.visualization.profile import select
from canopy.visualization.server import Handler

ROOT = Path(__file__).resolve().parents[2]


class DomainLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'checkout'
        self.root.mkdir()
        (self.root / 'AGENTS.md').write_text('Test checkout')
        shutil.copytree(ROOT / 'asset/schemas', self.root / 'asset/schemas')
        self.storage = Storage.load(self.root)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_metadata_and_payloads_are_separate_by_default(self):
        self.assertEqual(self.storage.metadata('core008'), self.root / 'scenario/south_ken')
        self.assertEqual(self.storage.assets('south_ken', 'assets'),
                         self.root / 'asset/data/project/south_ken/assets')
        self.assertEqual(self.storage.cache_root, self.root / 'cache')
        self.assertFalse((self.root / 'project').exists())

    def test_external_data_root_keeps_metadata_in_scenario(self):
        external = Path(self.temp.name) / 'retained'
        self.write('storage.local.json', json.dumps({'data_root': str(external)}))
        storage = Storage.load(self.root)
        self.assertEqual(storage.metadata('white_city'), self.root / 'scenario/white_city')
        self.assertEqual(storage.assets('white_city', 'assets'), external / 'project/white_city/assets')

    def test_cache_cannot_overlap_metadata_or_retained_data(self):
        for relative in ('scenario/south_ken/cache', 'asset/data', 'asset/data/project/south_ken/cache'):
            with self.subTest(relative=relative):
                self.write('storage.local.json', json.dumps({'cache_root': str(self.root / relative)}))
                with self.assertRaises(ValueError):
                    Storage.load(self.root)

    def test_imported_script_paths_resolve_both_source_roots(self):
        self.assertEqual(source_path('urban_flow/physics', self.root), self.root / 'model/src/urban_flow/physics')
        self.assertEqual(source_path('visualization/adapters', self.root),
                         self.root / 'visualizer/src/visualization/adapters')

    def test_wheel_schema_copies_match_public_contracts(self):
        for schema in (ROOT / 'asset/schemas').glob('*.json'):
            with self.subTest(schema=schema.name):
                self.assertEqual(schema.read_bytes(), (ROOT / 'model/src/canopy/schemas' / schema.name).read_bytes())

    def test_public_routes_read_new_layout_without_exposing_source(self):
        fixture = ROOT / 'model/tests/fixtures/contract-v1'
        manifest = json.loads((fixture / 'manifest.json').read_text())
        scenario = manifest['scene_id']
        create(self.storage, scenario, 'Recorded fixture', manifest['spatial'])
        refs = import_run(self.storage, scenario, fixture)
        select(self.storage, scenario, refs, 'engineering')
        self.write('visualizer/src/visualization/catalog/index.html', 'catalog page')
        self.write('visualizer/site/index.html', 'detailed website')
        self.write('visualizer/guide/index.html', 'architecture guide')
        self.write('visualizer/guide/inventory.json', '{"review": true}')
        self.write('visualizer/site/vendor/data.bin', '0123456789')
        self.write('model/tests/fixtures/example.json', '{"example": true}')
        self.write('model/src/private.py', 'private source')
        private = self.write('storage.local.json', '{"private": true}')
        (self.root / 'visualizer/site/vendor/escape').symlink_to(private)
        (self.root / 'visualizer/guide/escape').symlink_to(private)

        class QuietHandler(Handler):
            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, storage=self.storage))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'

            def get(path, headers=None):
                return urlopen(Request(base + path, headers=headers or {}), timeout=5)

            with get('/') as response:
                self.assertEqual(response.read(), b'catalog page')
            with get('/index.html') as response:
                self.assertEqual(response.read(), b'detailed website')
            with get('/guide/') as response:
                self.assertEqual(response.read(), b'architecture guide')
            with get('/guide/inventory.json') as response:
                self.assertTrue(json.load(response)['review'])
            with get('/api/canopy/scenarios') as response:
                catalog = json.load(response)
                self.assertEqual([entry['scenario_id'] for entry in catalog], [scenario])
                self.assertTrue(catalog[0]['available'])
            with get(f'/api/canopy/scenarios/{scenario}/visualization') as response:
                self.assertTrue(json.load(response)['layers'])
            with get(f'/project/{scenario}/scenario.json') as response:
                self.assertEqual(json.load(response)['scenario_id'], scenario)
            with get('/examples/example.json') as response:
                self.assertTrue(json.load(response)['example'])
            with get('/schemas/scenario-v2.schema.json') as response:
                self.assertEqual(json.load(response)['properties']['schema_version']['const'], '2.0.0')
            with get('/vendor/data.bin', {'Range': 'bytes=2-5'}) as response:
                self.assertEqual(response.status, 206)
                self.assertEqual(response.read(), b'2345')
            asset = json.loads((self.storage.metadata(scenario) / 'scenario.json').read_text())['assets'][refs[0]]
            with get(f'/project/{scenario}/{asset}') as response:
                self.assertEqual(json.load(response)['scenario_id'], scenario)
            for path in ('/model/src/private.py', '/storage.local.json', '/asset/data/', '/vendor/escape', '/guide/escape'):
                with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                    get(path)
                self.assertIn(error.exception.code, (400, 404))
            self.assertFalse(self.storage.cache_root.exists(), 'Reading a view must not create a run')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
