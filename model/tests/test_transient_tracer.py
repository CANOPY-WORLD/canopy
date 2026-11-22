import unittest
import numpy as np
from urban_flow.physics.transient_tracer import TransientTracer

class TransientTests(unittest.TestCase):
    def test_mass_and_solid_wall(self):
        fluid=np.ones((3,7,9),bool);fluid[:,:,4]=False
        u=np.zeros((3,*fluid.shape),np.float32);u[0]=1
        s=TransientTracer(u,fluid,2,.1)
        index=np.ravel_multi_index((1,3,2),fluid.shape)
        for _ in range(20):s.step(min(.1,s.max_dt),[index],[10.])
        d=s.diagnostics();self.assertLess(d['relative_mass_error'],2e-6)
        self.assertEqual(float(s.c[:,:,5:].sum()),0)
        self.assertGreater(d['stored_ug'],0)
    def test_projection_and_zero_source(self):
        rng=np.random.default_rng(12);fluid=np.ones((4,8,8),bool);fluid[:,3:5,3:5]=False
        s=TransientTracer(rng.normal(size=(3,*fluid.shape)),fluid,2,.1)
        d=s.project();self.assertLess(d['relative_residual'],5e-4)
        s.step(min(.1,s.max_dt));self.assertEqual(s.diagnostics()['stored_ug'],0)
    def test_unstable_rejected(self):
        s=TransientTracer(np.ones((3,3,4,5)),np.ones((3,4,5),bool),1,1)
        with self.assertRaises(ValueError):s.step(s.max_dt*2)
    def test_source_rejected(self):
        fluid=np.ones((3,4,5),bool);fluid[1,1,1]=False
        s=TransientTracer(np.zeros((3,3,4,5)),fluid,1,0)
        with self.assertRaises(ValueError):s.step(.1,[26],[1])
    def test_advective_centroid(self):
        shape=(5,5,60);u=np.zeros((3,*shape));u[0]=2
        s=TransientTracer(u,np.ones(shape,bool),1,0)
        s.c[2,2,10]=1;s.emitted_ug=1
        for _ in range(20):s.step(.1)
        weights=s.c.cpu().numpy().sum(axis=(0,1))
        self.assertAlmostEqual(float(weights@np.arange(60)/weights.sum()),14,places=4)
        self.assertLess(s.diagnostics()['relative_mass_error'],1e-5)
    def test_diffusion_symmetry(self):
        shape=(21,21,21);s=TransientTracer(np.zeros((3,*shape)),np.ones(shape,bool),1,.2)
        s.c[10,10,10]=1;s.emitted_ug=1
        for _ in range(10):s.step(.1)
        a=s.c.cpu().numpy();np.testing.assert_allclose(a,a[:,:,::-1],atol=1e-7)
        self.assertLess(s.diagnostics()['relative_mass_error'],1e-5)
    def test_invalid_source_does_not_advance(self):
        s=TransientTracer(np.ones((3,3,4,5)),np.ones((3,4,5),bool),1,0)
        before=s.c.clone()
        with self.assertRaises(ValueError):s.step(.01,[999],[1])
        self.assertTrue(bool((s.c==before).all()))

class AdapterTests(unittest.TestCase):
    def test_export_and_input_contract(self):
        import tempfile,json
        from pathlib import Path
        from types import SimpleNamespace
        from canopy.models.transient_pollution import TransientPollution
        from canopy.models.registry import describe
        from canopy._io import write,digest
        from common.contract import validate
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wind=root/'wind';em=root/'emissions';work=root/'work'
            for p in (wind,em,work):p.mkdir()
            shape=[3,6,8];grid={'schema_version':'1.0.0','shape_zyx':shape,'origin_m':[0.,0.,0.],'spacing_m':2.,'coordinate_frame':'ENU','unit':'m/s','mode':'frozen_cell_center_reconstruct_project','arrays':{'velocity':'velocity.npy','fluid':'fluid.npy'}}
            np.save(wind/'velocity.npy',np.zeros((3,*shape),dtype='<f4'));np.save(wind/'fluid.npy',np.ones(shape,dtype='u1'));write(wind/'grid.json',grid)
            wm={'artifacts':[{'id':key,'asset':name} for key,name in [('transport_grid_json','grid.json'),('v','velocity.npy'),('f','fluid.npy')]]};write(wind/'manifest.json',wm)
            e={**grid,'arrays':{n:n+'.npy' for n in ['times','offsets','indices','mass_ug']},'wind_manifest_sha256':digest(wind/'manifest.json'),'unit':'ug','pollutant':'SUMO_PMx_exhaust','time_alignment':'explicit_relative_scenario'}
            for n,a in [('times',np.array([0.,1.,2.])),('offsets',np.array([0,1,2],dtype='<i8')),('indices',np.array([70,71],dtype='<i8')),('mass_ug',np.array([10.,20.],dtype='<f4'))]:np.save(em/(n+'.npy'),a)
            write(em/'emissions.json',e);emeta={'artifacts':[{'id':'emissions_json','asset':'emissions.json'},*[{'id':n,'asset':n+'.npy'} for n in e['arrays']]]};write(em/'manifest.json',emeta)
            spatial={'frame':'ENU','unit':'m','origin':{'longitude':0.,'latitude':0.,'altitude_m':0.,'vertical_datum':'synthetic'},'bounds_m':{'min':[0.,0.,0.],'max':[16.,12.,6.]},'georeferenced':False}
            # Use the normative fixture's spatial keys.
            fixture=Path(__file__).parent/'fixtures/contract-v1/manifest.json'
            spatial=json.loads(fixture.read_text())['spatial'];spatial['bounds_m']={'min':[0.,0.,0.],'max':[16.,12.,6.]}
            ctx=SimpleNamespace(inputs={'wind':({},wm,wind/'manifest.json'),'emissions':({},emeta,em/'manifest.json')},scenario={'scenario_id':'demo','spatial':spatial},workspace=work,run_id='transient_test',created_at='2026-11-22T00:00:00Z',provenance={'code_revision':'synthetic-test','dirty':False,'parameters':{},'inputs':[]},checkpoint=lambda:None,emit=lambda *a,**kw:None)
            method=TransientPollution(describe('pollution','traffic_transient'))
            req={'model_id':'pollution','parameters':{'duration_s':2.,'frames':3,'slice_index':1,'diffusivity_m2_s':.1,'dt_max_s':.1},'execution':{'device':'cpu'}};ctx.request=req
            method.validate(req,ctx);result=method.execute(method.prepare(req,ctx),ctx);path=method.export(result,ctx)
            validate(path/'manifest.json');self.assertEqual(len(result['frames']),3)
            self.assertAlmostEqual(result['diagnostics']['frames'][-1]['emitted_ug'],30.,places=4)
            e['wind_manifest_sha256']='0'*64;write(em/'emissions.json',e)
            with self.assertRaises(ValueError):method.validate(req,ctx)
