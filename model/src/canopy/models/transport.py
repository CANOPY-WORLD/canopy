"""Coupled models consume versioned wind/geometry assets, never private solver state."""
from types import SimpleNamespace
import numpy as np
from canopy._io import read,write,relative,digest
from .methods import Fields,geometry_grid


def artifact(context,port,id):
    asset,manifest,path=context.inputs[port]
    item=next((a for a in manifest.get('artifacts',[]) if a['id']==id),None)
    if item is None:raise ValueError(f'{port} requires artifact {id}; run a method declaring that representation')
    return relative(path.parent,item['asset'])


def wind_volume(context):
    geometry_ref=context.request['inputs']['geometry'] if hasattr(context,'request') else context.input_references['geometry']
    asset,manifest,path=context.inputs['wind']
    if geometry_ref not in asset['derived_from']:raise ValueError('Wind must explicitly derive from the selected geometry version')
    meta=read(artifact(context,'wind','volume_json'));grid,height,_=geometry_grid(context)
    if meta.get('axes')!='TCZYX' or meta.get('coordinate_frame')!='ENU' or meta.get('unit')!='m/s' or meta.get('components')!=['east','north','up']:
        raise ValueError('Wind volume must declare TCZYX, ENU and m/s')
    if meta['origin_m']!=grid['origin_m'] or meta['spacing_m']!=[grid['spacing_m']]*3 or meta.get('sample_location')!='cell_center':
        raise ValueError('Wind/geometry grid mismatch; explicit resampling is required')
    if meta['file'] not in {a['asset'] for a in manifest.get('artifacts',[])}:raise ValueError('Wind volume must be a declared artifact')
    volume=np.load(relative(path.parent,meta['file']),mmap_mode='r',allow_pickle=False)
    times=np.asarray(meta['time_s'],dtype=float)
    if volume.dtype.str!='<f4' or list(volume.shape)!=meta['shape'] or volume.ndim!=5 or volume.shape[1]!=3 or volume.shape[-2:]!=height.shape or len(times)!=len(volume):raise ValueError('Invalid wind volume shape/dtype')
    if list(times)!=manifest['time']['samples'] or not np.isfinite(volume).all():raise ValueError('Wind time/value mismatch')
    if len(times)>1 and (np.diff(times)<=0).any():raise ValueError('Wind times must increase')
    return grid,height,volume,times,manifest


def mac_state(context):
    meta=read(artifact(context,'wind','mac_state_json'));base=artifact(context,'wind','mac_state_json').parent
    grid,height,volume,times,_=wind_volume(context)
    if meta.get('schema_version')!='1.0.0' or meta.get('axes')!='CZYX' or meta.get('face_convention')!='positive_face_of_cell' or meta.get('components')!=['east','north','up']:
        raise ValueError('Unsupported MAC face representation')
    if meta['spacing_m']!=grid['spacing_m'] or meta['origin_m']!=grid['origin_m'] or meta['time_s']!=times[-1]:raise ValueError('MAC state and volume grid/time mismatch')
    declared={a['asset'] for a in context.inputs['wind'][1].get('artifacts',[])}
    if not {meta['faces'],meta['fluid'],meta['inlet']}<=declared:raise ValueError('MAC arrays must be declared artifacts')
    if type(meta.get('open_top')) is not bool:raise ValueError('MAC open_top must be boolean')
    faces=np.load(relative(base,meta['faces']),allow_pickle=False)
    fluid=np.load(relative(base,meta['fluid']),allow_pickle=False)
    inlet=np.load(relative(base,meta['inlet']),allow_pickle=False)
    if faces.shape!=volume.shape[1:] or fluid.shape!=volume.shape[2:] or inlet.shape!=fluid.shape[:2] or fluid.dtype!=np.uint8 or not np.isin(fluid,[0,1]).all():raise ValueError('Invalid MAC state dimensions or mask')
    if faces.dtype.str!='<f4' or inlet.dtype.str!='<f4':raise ValueError('MAC face/inlet velocities require float32')
    if not np.isfinite(faces).all() or not np.isfinite(inlet).all():raise ValueError('Invalid MAC velocities')
    expected=(np.arange(fluid.shape[0])[:,None,None]+.5)*grid['spacing_m']>height[None]
    if not np.array_equal(fluid,expected):raise ValueError('MAC fluid mask disagrees with geometry')
    return meta,faces,fluid.astype(bool),inlet


class SteadyPollution(Fields):
    def validate(self,request,context):
        context.input_references=request['inputs'];grid,height,volume,times,_=wind_volume(context)
        meta,faces,fluid,inlet=mac_state(context);p=request['parameters']
        if p['slice_index']>=fluid.shape[0]:raise ValueError('Slice outside wind volume')
        for source in p['sources']:
            z,y,x=source['cell_zyx']
            if any(i>=n for i,n in zip((z,y,x),fluid.shape)) or not fluid[z,y,x]:raise ValueError('Emission source must be inside a fluid cell')
        if request['execution'].get('device','cpu')!='cpu':raise ValueError('Sparse steady tracer currently supports CPU only')
    def prepare(self,request,context):return wind_volume(context),mac_state(context),request['parameters']
    def execute(self,prepared,context):
        from urban_flow.physics.conservative_tracer import SteadyTracer
        (grid,height,volume,times,_),(meta,faces,fluid,inlet),p=prepared
        source=np.zeros(fluid.shape)
        for row in p['sources']:source[tuple(row['cell_zyx'])]+=row['mass_g_s']
        context.checkpoint();solver=SteadyTracer(fluid,faces,inlet,grid['spacing_m'],p['diffusivity_m2_s'],meta['open_top'])
        field,diagnostics=solver.solve(source);context.checkpoint()
        k=p['slice_index'];sampling=dict(grid,origin_m=[*grid['origin_m'][:2],grid['origin_m'][2]+(k+.5)*grid['spacing_m']])
        diagnostics.update(quality='conservative_steady_solve_passed',source_mass_unit='g/s',wind_time_s=float(times[-1]),assumptions='steady passive scalar; open boundary zero background; no chemistry')
        return {'grid':sampling,'height':np.zeros_like(height),'times':[float(times[-1])],'invalid':(~fluid[k]).astype('u1'),'fields':{'concentration':([field[k]],'g/m3',False)},'full_field':field,'full_grid':grid,'diagnostics':diagnostics}
    def export(self,result,context):
        folder=super().export(result,context);m=read(folder/'manifest.json');m['time']={'unit':'s','samples':[]}
        # A steady solution is static, with its driving snapshot recorded in provenance.
        layer=m['layers'][0];layer['sampling']='static';data=np.load(folder/'concentration.npy',allow_pickle=False)[0];np.save(folder/'concentration.npy',data)
        layer['encoding'].update(shape=list(data.shape),axes='YX')
        np.save(folder/'concentration_zyx.npy',np.asarray(result['full_field'],dtype='<f4'))
        write(folder/'scalar_volume.json',{'file':'concentration_zyx.npy','axes':'ZYX','shape':list(result['full_field'].shape),'dtype':'<f4','unit':'g/m3','origin_m':result['full_grid']['origin_m'],'spacing_m':[result['full_grid']['spacing_m']]*3,'coordinate_frame':'ENU','sample_location':'cell_center'})
        for name in ['concentration_zyx.npy','scalar_volume.json']:
            m['artifacts'].append({'id':name.replace('.','_'),'asset':name,'sha256':digest(folder/name),'media_type':'application/octet-stream'})
        write(folder/'manifest.json',m);return folder


class Temperature(Fields):
    def validate(self,request,context):
        context.input_references=request['inputs'];grid,height,volume,times,_=wind_volume(context);p=request['parameters']
        if len(times)<2 or not np.allclose(np.diff(times),times[1]-times[0]):raise ValueError('Temperature requires uniformly spaced wind snapshots with at least two samples')
        if min(volume.shape[2:])<3 or p['slice_index']>=volume.shape[2]:raise ValueError('Invalid thermal domain or slice')
        if self.spec['adapter']=='temperature_numpy' and request['execution'].get('device','cpu')!='cpu':raise ValueError('NumPy temperature supports CPU only')
    def prepare(self,request,context):return wind_volume(context),request['parameters'],request['execution'].get('device','cpu')
    def execute(self,prepared,context):
        from urban_flow.solvers.temperature import Temperature3DScenarioConfig,SouthKensingtonConfig,solve_temperature_fields_3d_numpy,solve_temperature_fields_3d_torch
        (grid,height,wind,times,manifest),p,device=prepared
        # Use left-held recorded wind over each interval; no extrapolated time samples.
        solid=(np.arange(wind.shape[2])[:,None,None]+.5)*grid['spacing_m']<=height[None]
        roof=solid.copy();roof[:-1]&=~solid[1:]
        fields={'u':wind[:-1,0],'v':wind[:-1,1],'w':wind[:-1,2],'solid_mask_3d':solid,'roof_mask_3d':roof,'study_area_mask_2d':np.ones(height.shape,bool)}
        boundary={'surface_exchange_coeff_per_s':np.full(height.shape,p['surface_exchange_per_s'],np.float32),'ground_surface_temperature_excess_c':np.full(height.shape,p['surface_excess_c'],np.float32),'roof_surface_temperature_excess_3d':roof.astype(np.float32)*p['surface_excess_c'],'ambient_temp_series_c':np.full(len(times),p['ambient_c'],np.float32),'inflow_temp_series_c':np.full(len(times),p['ambient_c'],np.float32),'surface_forcing_layer_count':np.array([1],np.int32)}
        v=SouthKensingtonConfig(grid['spacing_m'],grid['spacing_m'])
        t=Temperature3DScenarioConfig(frame_duration_s=float(times[1]-times[0]),max_courant=p['max_courant'],diffusion_coeff_m2_s=p['diffusivity_m2_s'],temperature_solver_device=device,on_substep=context.checkpoint)
        solver=solve_temperature_fields_3d_numpy if self.spec['adapter']=='temperature_numpy' else solve_temperature_fields_3d_torch
        solved=solver(fields,boundary,v,t);full=solved['temperature_fields_c'];k=p['slice_index']
        if not np.isfinite(full).all():raise ValueError('Nonfinite temperature result')
        allowed_min=p['ambient_c']+min(0,p['surface_excess_c'])-.11;allowed_max=p['ambient_c']+max(0,p['surface_excess_c'])+.11
        if full.min()<allowed_min or full.max()>allowed_max:raise ValueError('Temperature violates prescribed boundary/source extrema; refine the time/grid configuration')
        sampling=dict(grid,origin_m=[*grid['origin_m'][:2],grid['origin_m'][2]+(k+.5)*grid['spacing_m']])
        result={'grid':sampling,'height':np.zeros_like(height),'times':times.tolist(),'invalid':solid[k].astype('u1'),'fields':{'temperature':(full[:,k],'degC',False)},'full_field':full,'full_grid':grid,'diagnostics':{'quality':'finite_and_boundary_range_passed','dt_seconds':solved['dt_seconds'],'substeps_per_frame':solved['substeps_per_frame'],'backend':solved['solver_backend'],'assumptions':'prescribed ground/roof excess; west inflow +/-0.1 C vertical profile; left-held wind; no weather/solar coupling'}}
        if 'epoch' in manifest['time']:result['epoch']=manifest['time']['epoch']
        return result
    def export(self,result,context):
        folder=super().export(result,context);m=read(folder/'manifest.json')
        np.save(folder/'temperature_tzyx.npy',np.asarray(result['full_field'],dtype='<f4'))
        write(folder/'scalar_volume.json',{'file':'temperature_tzyx.npy','axes':'TZYX','shape':list(result['full_field'].shape),'dtype':'<f4','unit':'degC','origin_m':result['full_grid']['origin_m'],'spacing_m':[result['full_grid']['spacing_m']]*3,'coordinate_frame':'ENU','sample_location':'cell_center','time_s':result['times']})
        for name in ['temperature_tzyx.npy','scalar_volume.json']:
            m['artifacts'].append({'id':name.replace('.','_'),'asset':name,'sha256':digest(folder/name),'media_type':'application/octet-stream'})
        write(folder/'manifest.json',m);return folder
