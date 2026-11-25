import json
import threading
import unittest
from functools import partial
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from canopy.running.local_health import Handler


class LocalHealthServiceTests(unittest.TestCase):
    def setUp(self):
        self.server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,storage=None))
        self.calls=[]
        self.server.session=SimpleNamespace(token='test-token',job={'status':'idle'},allowed_files=set(),calculate=self.calls.append)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def request(self,method,path,headers=None,body=None):
        connection=HTTPConnection('127.0.0.1',self.server.server_port)
        connection.request(method,path,body,headers or {})
        response=connection.getresponse();status=response.status;data=response.read();connection.close()
        return status,data

    def test_get_does_not_run_and_input_bytes_are_blocked(self):
        self.assertEqual(self.request('GET','/api/health/job')[0],200)
        for path in ['/project/imperial_corridor_8km/assets/bundles/input_bundle/manifest.json','/project/imperial_corridor_8km/assets/bundles/older_input/observations.csv','/project/imperial_corridor_8km/assets/bundles/result/provenance/request.json','/project/imperial_corridor_8km/runs/cache/file.json']:
            self.assertEqual(self.request('GET',path)[0],403)
        self.assertEqual(self.calls,[])

    def test_explicit_same_origin_token_required(self):
        self.assertEqual(self.request('POST','/api/health/plan',body='{}')[0],403)
        headers={'Origin':f'http://127.0.0.1:{self.server.server_port}','X-Planning-Token':'test-token','Content-Type':'application/json'}
        self.assertEqual(self.request('POST','/api/health/plan',headers,'{}')[0],200)
        self.assertEqual(self.calls,[{}])
        headers['Origin']='https://example.invalid'
        self.assertEqual(self.request('POST','/api/health/plan',headers,'{}')[0],403)
        self.assertEqual(len(self.calls),1)

    def test_rejects_other_host(self):
        self.assertEqual(self.request('GET','/api/health/job',{'Host':'example.invalid'})[0],403)
