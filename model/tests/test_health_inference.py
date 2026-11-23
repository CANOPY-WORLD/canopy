import hashlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from healthy_route.inference import predict,load_model,ASSETS
from canopy.models.registry import describe,implementation
from common.contract import validate

class PublicInferenceTests(unittest.TestCase):
    def test_runtime_snapshot_retains_inference_assets(self):
        import tarfile
        from canopy.running.provenance import snapshot_runtime
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'source.tar.gz';snapshot_runtime(target)
            with tarfile.open(target) as archive:
                inventory=json.load(archive.extractfile('runtime-source.json'))['files']
                for name in ('state_cvae.pt','scaler.json','manifest.json'):
                    path='src/healthy_route/assets/'+name
                    data=archive.extractfile(path).read()
                    self.assertEqual(data,(ASSETS/name).read_bytes())
                    self.assertEqual(hashlib.sha256(data).hexdigest(),inventory[path])
    def test_packaged_json_uses_checksum_stable_lf_bytes(self):
        manifest=json.loads((ASSETS/'manifest.json').read_bytes())
        for name in ('manifest.json','scaler.json'):
            self.assertNotIn(b'\r', (ASSETS/name).read_bytes(), name)
        for name,expected in manifest['files'].items():
            self.assertEqual(hashlib.sha256((ASSETS/name).read_bytes()).hexdigest(),expected,name)
    def test_assets_contain_only_model_parameters(self):
        import torch
        self.assertEqual({p.name for p in ASSETS.iterdir()},{'state_cvae.pt','scaler.json','manifest.json'})
        weights=torch.load(ASSETS/'state_cvae.pt',weights_only=True)
        self.assertEqual(set(weights),{'state_dict'})
        self.assertTrue(all(isinstance(v,torch.Tensor) for v in weights['state_dict'].values()))
        self.assertEqual(set(json.loads((ASSETS/'scaler.json').read_text())),{'columns','mean','scale'})
    def test_inference_reproducible_without_private_files(self):
        x=[[10,22,50,.03,0,1,0,1]]*3
        a,sd,_=predict(x,16,16,42);b,_,_=predict(x,16,16,42)
        np.testing.assert_array_equal(a,b);self.assertEqual(len(a),4);self.assertEqual(a[0],16)
        self.assertTrue(np.isfinite(a).all());self.assertGreater(sd[-1],0)
        y=[row.copy() for row in x];y[0][1]=30
        c,_,_=predict(y,16,16,42);self.assertFalse(np.array_equal(a,c))
    def test_cancellation(self):
        def cancel():raise InterruptedError('cancelled')
        with self.assertRaises(InterruptedError):predict([[10,22,50,.03,0,1,0,1]],16,2,42,cancel)
    def test_bad_checksum_rejected(self):
        import shutil
        for name in ('state_cvae.pt','scaler.json'):
            with self.subTest(asset=name),tempfile.TemporaryDirectory() as d:
                copy=Path(d)/'assets';shutil.copytree(ASSETS,copy)
                target=copy/name
                target.write_bytes(target.read_bytes().replace(b'\n',b'\r\n') if name.endswith('.json') else target.read_bytes()+b'x')
                with patch('healthy_route.inference.ASSETS',copy):
                    with self.assertRaisesRegex(ValueError,'checksum'):load_model()
    def test_export_all_layers_and_solar_does_not_change_breathing(self):
        root=Path(__file__).resolve().parents[2]
        request=json.loads((root/'model/tests/fixtures/canopy/health_inference.json').read_text())
        method=implementation(describe('healthy_route','breathing_cvae'))
        spatial={'frame':'ENU','units':'m','georeferenced':False,'origin':{'longitude':0,'latitude':0,'height_m':0,'vertical_datum':'synthetic'},'bounds_m':{'min':[-10,-10,-10],'max':[200,10,10]}}
        with tempfile.TemporaryDirectory() as d:
            c=SimpleNamespace(workspace=Path(d),scenario={'scenario_id':'health_example','spatial':spatial},request=request,run_id='test_inference',created_at='2026-11-22T00:00:00Z',provenance={'code_revision':'test','dirty':False,'parameters':{},'inputs':[]},checkpoint=lambda:None,emit=lambda *a,**k:None)
            method.validate(request,c);a=method.execute(method.prepare(request,c),c)
            p=dict(request['parameters'],irradiance_w_m2=[0]*13);b=method.execute(p,c)
            np.testing.assert_array_equal(a['fields']['breathing'][0],b['fields']['breathing'][0])
            self.assertTrue(np.all(a['fields']['thermal_proxy'][0]>b['fields']['thermal_proxy'][0]))
            out=method.export(a,c);validate(out/'manifest.json')
            m=json.loads((out/'manifest.json').read_text());self.assertEqual(len(m['layers']),8)
            self.assertEqual(m['time']['samples'][-1],3600)
            request['parameters']['positions_m']=[[999,0,0]]*13
            with self.assertRaisesRegex(ValueError,'bounds'):method.validate(request,c)
