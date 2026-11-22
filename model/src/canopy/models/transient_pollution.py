"""Transient traffic tracer, explicit frozen reconstructed-wind input contract."""
import numpy as np
from canopy._io import read, write, relative, digest
from .interface import Method
from .methods import base
from .transport import artifact


def arrays(context, port, artifact_id):
    path=artifact(context,port,artifact_id);meta=read(path)
    declared={x['asset'] for x in context.inputs[port][1].get('artifacts',[])}
    result={}
    for key,name in meta['arrays'].items():
        if name not in declared:raise ValueError('Undeclared computational array')
        result[key]=np.load(relative(path.parent,name),mmap_mode='r',allow_pickle=False)
    return meta,result


class TransientPollution(Method):
    def validate(self,request,context):
        w,a=arrays(context,'wind','transport_grid_json');e,b=arrays(context,'emissions','emissions_json')
        if w['schema_version']!='1.0.0' or e['schema_version']!='1.0.0':raise ValueError('Unsupported computational contract')
        for key in ('origin_m','spacing_m','shape_zyx'):
            if w[key]!=e[key]:raise ValueError('Wind/emissions grid mismatch')
        if e['wind_manifest_sha256']!=digest(context.inputs['wind'][2]):raise ValueError('Emissions mapped against a different wind grid')
        if w['coordinate_frame']!='ENU' or w['unit']!='m/s' or w['mode']!='frozen_cell_center_reconstruct_project':raise ValueError('Unsupported wind semantics')
        shape=tuple(w['shape_zyx']);fluid=a['fluid'];vel=a['velocity']
        if fluid.shape!=shape or vel.shape!=(3,*shape) or not np.isin(fluid,[0,1]).all() or not np.isfinite(vel).all():raise ValueError('Invalid wind arrays')
        if vel.dtype.str!='<f4' or fluid.dtype!=np.uint8:raise ValueError('Invalid computational dtype')
        lo=np.asarray(context.scenario['spatial']['bounds_m']['min']);hi=np.asarray(context.scenario['spatial']['bounds_m']['max'])
        origin=np.asarray(w['origin_m']);spacing=w['spacing_m']
        if not np.isfinite(origin).all() or not np.isfinite(spacing) or spacing<=0 or (origin<lo).any() or (origin+np.asarray(shape[::-1])*spacing>hi).any():raise ValueError('Invalid computational bounds')
        times=b['times'];offset=b['offsets'];idx=b['indices'];mass=b['mass_ug']
        if e['unit']!='ug' or e['pollutant']!='SUMO_PMx_exhaust' or e['time_alignment']!='explicit_relative_scenario':raise ValueError('Unsupported emissions semantics')
        if times.ndim!=1 or len(times)<2 or times[0]!=0 or not np.isfinite(times).all() or (np.diff(times)<=0).any():raise ValueError('Invalid emission interval boundaries')
        if offset.dtype.kind not in 'iu' or offset.shape!=times.shape or offset[0]!=0 or offset[-1]!=len(idx) or (np.diff(offset)<0).any() or mass.shape!=idx.shape or idx.dtype.kind not in 'iu':raise ValueError('Invalid sparse offsets')
        if not np.isfinite(mass).all() or (mass<0).any() or (idx<0).any() or (idx>=fluid.size).any() or not fluid.reshape(-1)[idx].all():raise ValueError('Invalid source mass/cells')
        p=request['parameters']
        if p['slice_index']>=shape[0] or p['duration_s']>times[-1]:raise ValueError('Requested slice/time unavailable')

    def prepare(self,request,context):
        return arrays(context,'wind','transport_grid_json'),arrays(context,'emissions','emissions_json'),request['parameters'],request['execution'].get('device','cpu')

    def execute(self,prepared,context):
        from urban_flow.physics.transient_tracer import TransientTracer
        (w,a),(e,b),p,device=prepared
        solver=TransientTracer(np.array(a['velocity']),np.array(a['fluid']),w['spacing_m'],p['diffusivity_m2_s'],device)
        projection=solver.project(checkpoint=context.checkpoint,progress=lambda **kw:context.emit('projection',**kw))
        context.emit('projection_complete',**projection)
        folder=context.workspace/'payload';folder.mkdir()
        sample_times=np.linspace(0,p['duration_s'],p['frames'])
        frames=[];checks=[];t=0.;interval=0;k=p['slice_index']
        for frame,target in enumerate(sample_times):
            while t<target-1e-9:
                context.checkpoint()
                while b['times'][interval+1]<=t+1e-9:interval+=1
                end=float(b['times'][interval+1]);width=end-float(b['times'][interval])
                dt=min(solver.max_dt,p['dt_max_s'],end-t,target-t)
                start,stop=b['offsets'][interval:interval+2]
                solver.step(dt,b['indices'][start:stop],b['mass_ug'][start:stop]*(dt/width));t+=dt
            name=f'concentration_{frame:03d}.npy';np.save(folder/name,solver.c[k:k+1].cpu().numpy());frames.append(name)
            checks.append(dict(time_s=float(target),**solver.diagnostics()))
            context.emit('progress',completed=frame+1,total=len(sample_times))
        np.save(folder/'final_volume.npy',solver.c.cpu().numpy())
        np.save(folder/'invalid.npy',(~solver.fluid[k]).cpu().numpy().astype('u1'))
        # Keep the exact projected face field used, not only the display vectors.
        for axis,f in zip(('z','y','x'),solver.faces):np.save(folder/f'projected_faces_{axis}.npy',f.cpu().numpy())
        return {'folder':folder,'grid':w,'times':sample_times.tolist(),'frames':frames,'slice':k,'diagnostics':{'quality':'partial_source_preview' if e.get('mapping',{}).get('partial_preview') else 'positivity_and_mass_balance_passed','projection':projection,'frames':checks,'emission_mapping':e.get('mapping',{}),'assumptions':['Frozen recorded wind at its declared model time; new conditional traffic scenario, not a simultaneous observation.','SUMO exhaust PMx increment only; zero initial/background increment; not total measured PM2.5.','Constant effective diffusivity; no chemistry, deposition, non-exhaust PM or calibrated turbulence.','8 m voxel mean is not a resolved pedestrian breathing-height concentration.','Excluded source contributions are unavailable, not zero; downwind concentration is incomplete when partial_preview is true.']}}

    def export(self,result,context):
        folder=result['folder'];w=result['grid'];k=result['slice'];n=len(result['times']);ny,nx=w['shape_zyx'][1:]
        origin=[*w['origin_m'][:2],w['origin_m'][2]+(k+.5)*w['spacing_m']]
        write(folder/'frames.json',{'frames':result['frames']})
        m=base(context,result['times']);m['layers']=[{'id':'traffic_pmx_increment','kind':'scalar_field','format':'npy_frames','asset':'frames.json','sampling':'linear','encoding':{'coordinate_frame':'ENU','dtype':'<f4','shape':[n,ny,nx],'axes':'TYX','origin_m':origin,'spacing_m':[w['spacing_m']]*2,'sample_location':'cell_center','byte_order':'little','compression':'none','frame_assets':result['frames'],'mask_asset':'invalid.npy','mask_dtype':'|u1','mask_semantics':'invalid_nonzero'},'field':{'name':'SUMO exhaust PMx concentration increment','unit':'ug/m3'},'display':{'widget':'scalar_field','capabilities':['pick','legend','opacity']}}]
        write(folder/'volume.json',{'axes':'ZYX','shape':w['shape_zyx'],'dtype':'<f4','unit':'ug/m3','origin_m':w['origin_m'],'spacing_m':[w['spacing_m']]*3,'time_s':result['times'][-1],'file':'final_volume.npy','projected_faces':{'axes_order':['z','y','x'],'convention':'all faces including both domain boundaries','files':[f'projected_faces_{a}.npy' for a in 'zyx'],'unit':'m/s'}})
        for name in ['final_volume.npy','volume.json',*[f'projected_faces_{a}.npy' for a in 'zyx']]:
            m['artifacts'].append({'id':name.replace('.','_'),'asset':name,'sha256':digest(folder/name),'media_type':'application/octet-stream'})
        write(folder/'manifest.json',m);return folder
