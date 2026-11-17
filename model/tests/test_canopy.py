"""End-to-end lifecycle, isolation, provenance and numerical regressions."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from jsonschema import ValidationError
from common.storage import Storage
from canopy.cli import synthetic_spatial
from canopy._io import read,write,digest
from canopy.scenario.store import create,load as scenario_load
from canopy.assets.store import load as asset_load,import_run
from canopy.models.registry import describe,catalog
from canopy.models.methods import Heightfield
from canopy.running.runner import run,prepare_request
from canopy.visualization.profile import select,describe as view

ROOT=Path(__file__).resolve().parents[2]

class CanopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);(root/'AGENTS.md').write_text('test workspace')
        shutil.copytree(ROOT / 'asset/schemas',root/'schemas')
        self.storage=Storage(root,root/'data',root/'cache')
        create(self.storage,'alpha','Alpha',synthetic_spatial())
        create(self.storage,'beta','Beta',synthetic_spatial())
    def request(self,model='geometry',method='heightfield',inputs=None,parameters=None):
        return dict(schema_version='2.0.0',scenario_id='alpha',model_id=model,method_id=method,method_version='1.0.0',inputs=inputs or {},parameters=parameters or {},execution={'device':'cpu','threads':1})
    def geometry(self):return run(self.storage,self.request())['assets'][0]
    def test_registry_every_method_has_schema_guide_example(self):
        for spec in catalog():
            self.assertTrue((ROOT/spec['guide']).is_file());self.assertTrue((ROOT/spec['example']).is_file())
    def test_complete_asset_survives_cache_deletion(self):
        ref=self.geometry();shutil.rmtree(self.storage.cache_root)
        asset,manifest,path=asset_load(self.storage,'alpha',ref)
        self.assertEqual(asset['kind'],'geometry');self.assertIn('source_snapshot',[x['id'] for x in manifest['artifacts']]);self.assertTrue(path.is_relative_to(self.storage.data_root))
    def test_scenario_asset_isolation(self):
        ref=self.geometry()
        with self.assertRaises(ValueError):asset_load(self.storage,'beta',ref)
        data=scenario_load(self.storage,'beta');data['assets'][ref]='../alpha/assets/geometry.json';write(self.storage.metadata('beta')/'scenario.json',data)
        with self.assertRaises(ValueError):scenario_load(self.storage,'beta')
    def test_checksum_change_rejected(self):
        ref=self.geometry();a,m,p=asset_load(self.storage,'alpha',ref)
        (p.parent/'height.npy').write_bytes(b'tampered')
        with self.assertRaises(Exception):asset_load(self.storage,'alpha',ref)
    def test_unknown_version_and_parameter(self):
        request=self.request();request['method_version']='2.0.0'
        with self.assertRaises(ValueError):prepare_request(self.storage,request)
        with self.assertRaises(ValidationError):prepare_request(self.storage,self.request(parameters={'typo':1}))
    def test_preflight_does_not_create_run(self):
        prepare_request(self.storage,self.request());self.assertFalse(self.storage.cache_root.exists())
    def test_failed_run_records_failure_and_registers_nothing(self):
        with patch.object(Heightfield,'execute',side_effect=RuntimeError('solver failed')):
            with self.assertRaises(RuntimeError):run(self.storage,self.request())
        states=list(self.storage.cache_root.rglob('run.json'));self.assertEqual(read(states[0])['status'],'failed');self.assertEqual(scenario_load(self.storage,'alpha')['assets'],{})
    def test_cancelled_run_not_promoted(self):
        with patch.object(Heightfield,'execute',side_effect=InterruptedError('cancel')):
            with self.assertRaises(InterruptedError):run(self.storage,self.request())
        self.assertEqual(read(next(self.storage.cache_root.rglob('run.json')))['status'],'cancelled')
        self.assertEqual(scenario_load(self.storage,'alpha')['assets'],{})
    def test_no_retention_until_explicit_import(self):
        result=run(self.storage,self.request(),retain=False);self.assertEqual(result['assets'],[])
        refs=import_run(self.storage,'alpha',result['payload'])
        with self.assertRaises(FileExistsError):import_run(self.storage,'alpha',result['payload'])
        self.assertEqual(len(refs),1)
    def test_view_rejects_cross_scenario_and_keeps_template(self):
        ref=self.geometry();select(self.storage,'alpha',[ref],'city');data=view(self.storage,'alpha')
        self.assertEqual(data['profile']['template'],'standard');self.assertTrue(data['runs'][0]['url'].startswith('/project/alpha/assets/'))
        with self.assertRaises(ValueError):select(self.storage,'beta',[ref])
    def test_portable_scenario_archive_has_no_cache_dependency(self):
        import tarfile
        from canopy.assets.package import pack
        ref=self.geometry();target=Path(self.tmp.name)/'alpha.tar.gz'
        result=pack(self.storage,'alpha',target)
        self.assertGreater(result['files'],4)
        with tarfile.open(target) as archive:
            self.assertTrue(all(m.name.startswith('project/alpha/') and m.isfile() for m in archive.getmembers()))
            self.assertIn('project/alpha/scenario.json',archive.getnames())
        with self.assertRaises(FileExistsError):pack(self.storage,'alpha',target)
    def test_nonfinite_request_rejected(self):
        with self.assertRaises(ValueError):prepare_request(self.storage,self.request(parameters={'cell_m':float('nan')}))
    def test_wrong_input_kind(self):
        with self.assertRaises(ValueError):prepare_request(self.storage,self.request(inputs={'unexpected':'x'}))
    def test_flood_conserves_closed_basin_rain_volume(self):
        ref=run(self.storage,self.request(parameters={'obstacle_height_m':0}))['assets'][0]
        result=run(self.storage,self.request('flood','shallow_water',{'geometry':ref},{'frames':2,'frame_seconds':1}))
        a,m,path=asset_load(self.storage,'alpha',result['assets'][0]);depth=np.load(path.parent/'water_depth.npy')
        np.testing.assert_allclose(depth[-1],20/1000/3600*2,rtol=1e-4,atol=1e-8)
        self.assertEqual(a['derived_from'],[ref]);self.assertLess(abs(result['diagnostics']['mass_error_m3']),1e-5)
    def test_solar_and_wind_standard_outputs(self):
        ref=self.geometry()
        for model,method in [('solar','shadow'),('wind','mac')]:
            result=run(self.storage,self.request(model,method,{'geometry':ref}))
            a,m,path=asset_load(self.storage,'alpha',result['assets'][0]);self.assertEqual(a['kind'],'physics')
            self.assertTrue(all(np.isfinite(np.load(path.parent/layer['asset'])).all() for layer in m['layers']))
            if model=='wind':self.assertTrue((path.parent/'velocity_tczyx.npy').exists())
    def test_snapshot_tracks_runtime_not_metadata_checkout(self):
        import tarfile,hashlib
        result=run(self.storage,self.request());a,m,path=asset_load(self.storage,'alpha',result['assets'][0])
        with tarfile.open(path.parent/'provenance/source_snapshot.tar.gz') as archive:
            content=archive.extractfile('src/canopy/models/methods.py').read()
            self.assertEqual(content,(ROOT / 'model/src/canopy/models/methods.py').read_bytes())
            index=json.load(archive.extractfile('runtime-source.json'))
            self.assertEqual(index['files']['src/canopy/models/methods.py'],hashlib.sha256(content).hexdigest())
            self.assertEqual(index['identity'],m['provenance']['code_revision'])
    def test_glb_parent_transform_and_coverage_are_preserved(self):
        import struct
        ref=run(self.storage,self.request(parameters={'obstacle_height_m':0,'cell_m':2}))['assets'][0]
        a,m,path=asset_load(self.storage,'alpha',ref);stage=Path(self.tmp.name)/'transform';shutil.copytree(path.parent,stage)
        raw=(stage/'visual.glb').read_bytes();length,kind=struct.unpack_from('<II',raw,12);doc=json.loads(raw[20:20+length])
        doc['nodes'].append({'translation':[1,2,-1],'children':[0]});doc['scenes'][0]['nodes']=[1]
        encoded=json.dumps(doc).encode();encoded+=b' '*((-len(encoded))%4);tail=raw[20+length:]
        (stage/'visual.glb').write_bytes(struct.pack('<III',0x46546c67,2,20+len(encoded)+len(tail))+struct.pack('<II',len(encoded),kind)+encoded+tail)
        m['run_id']='transformed_source';write(stage/'manifest.json',m)
        transformed=import_run(self.storage,'alpha',stage)[0]
        request=self.request('geometry','rasterize_glb',{'geometry':transformed},{'bounds_xy_m':[2,2,30,30]})
        result=run(self.storage,request);a,m,path=asset_load(self.storage,'alpha',result['assets'][0])
        np.testing.assert_allclose(np.load(path.parent/'height.npy'),2)
        self.assertTrue(np.load(path.parent/'coverage.npy').all())
        self.assertEqual((path.parent/'visual.glb').read_bytes(),(stage/'visual.glb').read_bytes())
        with self.assertRaisesRegex(ValueError,'cover every sample'):
            run(self.storage,self.request('geometry','rasterize_glb',{'geometry':transformed},{'bounds_xy_m':[0,0,32,32]}))
    def test_coupled_temperature_backends_and_tracer_conservation(self):
        geometry=self.geometry();wind=run(self.storage,self.request('wind','mac',{'geometry':geometry}))['assets'][0]
        inputs={'geometry':geometry,'wind':wind};values=[]
        for backend in ['numpy','torch']:
            result=run(self.storage,self.request('temperature','finite_difference_'+backend,inputs))
            a,m,path=asset_load(self.storage,'alpha',result['assets'][0]);values.append(np.load(path.parent/'temperature_tzyx.npy'))
            self.assertEqual(set(a['derived_from']),set(inputs.values()));self.assertEqual(m['time']['samples'],[0,.2,.4])
        np.testing.assert_allclose(values[0],values[1],rtol=1e-6,atol=1e-5)
        self.assertGreater(values[0][:,0].max(),20)
        result=run(self.storage,self.request('pollution','steady_tracer',inputs))
        a,m,path=asset_load(self.storage,'alpha',result['assets'][0]);self.assertEqual(m['time']['samples'],[])
        self.assertEqual(m['layers'][0]['sampling'],'static');self.assertEqual(m['layers'][0]['encoding']['axes'],'YX')
        self.assertLess(result['diagnostics']['mass_balance_relative_error'],1e-6)
        self.assertLess(result['diagnostics']['linear_relative_residual'],1e-6)
        self.assertGreater(np.load(path.parent/'concentration.npy').max(),0)
        other=self.geometry()
        with self.assertRaisesRegex(ValueError,'selected geometry version'):
            prepare_request(self.storage,self.request('temperature','finite_difference_numpy',{'geometry':other,'wind':wind}))
        with self.assertRaisesRegex(ValueError,'inside a fluid cell'):
            prepare_request(self.storage,self.request('pollution','steady_tracer',inputs,{'sources':[{'cell_zyx':[0,8,8],'mass_g_s':1}]}))
    def test_geometry_nodes_reject_cycles(self):
        from canopy.models.geometry import meshes
        with self.assertRaisesRegex(ValueError,'cyclic'):
            list(meshes({'scenes':[{'nodes':[0]}],'nodes':[{'children':[0]}]}))
    def test_bad_solar_time_axis_rejected(self):
        ref=self.geometry()
        with self.assertRaises(ValueError):prepare_request(self.storage,self.request('solar','shadow',{'geometry':ref},{'times_s':[2,1]}))

if __name__=='__main__':unittest.main()
