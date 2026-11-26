"""Local city service boundaries; all fixtures are fictional."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

spec = importlib.util.spec_from_file_location('city_health_service', Path(__file__).parents[1] / 'tools/serve_city_health.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class CityHealthServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.site = root / 'site'; self.site.mkdir()
        (self.site / 'index.html').write_text('City preview', encoding='utf-8')
        self.private = root / 'participant.json'
        self.private.write_text('{"private":true}', encoding='utf-8')
        field = root / 'field.gz'; field.write_bytes(b'declared field')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), service.Handler)
        self.server.site = self.site
        self.server.fields = {'/health-inputs/physics/chunks/temp/0000.gz': field}
        self.server.metadata = {'example': ['fictional_a', 'fictional_b']}
        self.server.last_result = None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.temp.cleanup()

    def request(self, path, method='GET', headers=None, body=None):
        client = HTTPConnection('127.0.0.1', self.server.server_port)
        client.request(method, path, body=body, headers=headers or {})
        response = client.getresponse()
        status, data = response.status, response.read()
        client.close()
        return status, data

    def test_declared_fields_and_metadata_without_execution(self):
        self.assertEqual(self.request('/')[0], 200)
        self.assertEqual(json.loads(self.request('/api/health/status')[1])['last_result'], None)
        self.assertEqual(self.request('/health-inputs/physics/chunks/temp/0000.gz'), (200, b'declared field'))
        self.assertEqual(self.request('/health-inputs/physics/chunks/temp/0000.gz', 'HEAD'), (200, b''))

    def test_private_files_and_encoded_traversal_are_not_served(self):
        for path in ['/participant.json', '/pedestrian/private/participant.json', '/%2e%2e/participant.json', '/health-inputs/physics/../../participant.json']:
            for method in ['GET', 'HEAD']:
                self.assertEqual(self.request(path, method)[0], 404)

    def test_reject_foreign_origin_and_non_json_before_computation(self):
        self.assertEqual(self.request('/api/pedestrian/plan', 'POST', {'Origin':'https://example.com', 'Content-Type':'application/json'}, '{}')[0], 403)
        self.assertEqual(self.request('/api/pedestrian/plan', 'POST', {'Content-Type':'text/plain'}, '{}')[0], 415)

    def test_recorded_mode_never_runs_a_planner(self):
        self.server.mode='current-city-recording'
        self.server.recording={'samples':[], 'health_score':None}
        self.assertEqual(self.request('/api/pedestrian/plan','POST',{'Content-Type':'application/json'},'{}')[0],405)
        self.assertIsNone(json.loads(self.request('/api/health/recording')[1])['health_score'])

    def test_selection_only_changes_two_endpoints(self):
        template={'method_id':'city_walk','inputs':{'physiology':'fixed@1'},'parameters':{'origin':'a','goal':'b','speed_m_s':1.3}}
        result=service.endpoint_request(template,{'origin':'c','goal':'d'})
        self.assertEqual(result['parameters'],{'origin':'c','goal':'d','speed_m_s':1.3})
        self.assertEqual(result['inputs'],template['inputs']);self.assertEqual(template['parameters']['origin'],'a')
        for bad in [{'origin':'c','goal':'d','physiology':'other@1'},{'origin':'c'},{'origin':[], 'goal':'d'},{'origin':'c','goal':'d','speed_m_s':5}]:
            with self.assertRaises(ValueError):service.endpoint_request(template,bad)

    def test_selection_retains_same_origin_and_route_boundaries(self):
        self.server.mode='current-city-recording';self.server.select_routes=True
        self.assertTrue(json.loads(self.request('/api/health/status')[1])['select_routes'])
        self.assertEqual(self.request('/api/health/walk','POST',{'Content-Type':'application/json','Origin':'https://example.com'},'{}')[0],403)
        self.assertEqual(self.request('/api/pedestrian/plan','POST',{'Content-Type':'application/json'},'{}')[0],404)

    def test_selected_departure_preserves_fixed_model_and_rejects_invalid_clock(self):
        template={'method_id':'city_walk','inputs':{'physiology':'fixed@1'},'parameters':{'origin':'a','goal':'b','departure_s':0,'speed_m_s':1.3}}
        result=service.endpoint_request(template,{'origin':'c','goal':'d','departure_s':600})
        self.assertEqual(result['parameters']['departure_s'],600)
        self.assertEqual(template['parameters']['departure_s'],0)
        self.assertEqual(result['inputs'],template['inputs'])
        for time in [-1,True,'600',None,float('inf'),float('nan')]:
            with self.subTest(time=time),self.assertRaises(ValueError):
                service.endpoint_request(template,{'origin':'c','goal':'d','departure_s':time})
