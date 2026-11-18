"""Adapters around Physics4D kernels. No renderer imports or global scene state."""
import math
from pathlib import Path
import struct
import json
import numpy as np
from canopy._io import write, read, relative
from .interface import Method


def geometry_grid(context):
    asset,manifest,path=context.inputs['geometry']
    entry=next((x for x in manifest.get('artifacts',[]) if x['id']=='heightfield'),None)
    if entry is None: raise ValueError('Geometry requires heightfield artifact; a visual GLB alone is insufficient')
    grid=read(relative(path.parent,entry['asset']))
    declared={a['asset'] for a in manifest.get('artifacts',[])}
    if not {grid['height'],grid['solid']}<=declared:raise ValueError('Heightfield arrays must be declared artifacts')
    height=np.load(relative(path.parent,grid['height']),allow_pickle=False)
    solid=np.load(relative(path.parent,grid['solid']),allow_pickle=False)
    if height.ndim!=2 or min(height.shape)<3 or solid.shape!=height.shape or not np.isfinite(height).all():
        raise ValueError('Invalid heightfield dimensions/values')
    if height.dtype.str != '<f4' or solid.dtype != np.uint8 or not np.isin(solid,[0,1]).all():
        raise ValueError('Heightfield requires float32 height and uint8 binary solid mask')
    if not math.isfinite(grid['spacing_m']) or grid['spacing_m']<=0: raise ValueError('Invalid grid spacing')
    if len(grid['origin_m'])!=3 or not np.isfinite(grid['origin_m']).all(): raise ValueError('Invalid grid origin')
    if grid.get('shape_yx') != list(height.shape) or grid.get('coordinate_frame')!='ENU' or grid.get('sample_location')!='cell_center':
        raise ValueError('Heightfield shape, frame or sampling convention mismatch')
    lo=np.asarray(context.scenario['spatial']['bounds_m']['min']);hi=np.asarray(context.scenario['spatial']['bounds_m']['max'])
    origin=np.asarray(grid['origin_m']);upper=origin+np.array([height.shape[1]*grid['spacing_m'],height.shape[0]*grid['spacing_m'],float(height.max())])
    if (height<0).any() or (origin<lo).any() or (upper>hi).any():raise ValueError('Heightfield lies outside scenario bounds')
    return grid,height,solid


def base(context, times):
    return {'schema_version':'1.1.0','scene_id':context.scenario['scenario_id'],'simulation':context.request['model_id'],
            'run_id':context.run_id,'status':'complete','created_at':context.created_at,
            'spatial':context.scenario['spatial'],'time':{'unit':'s','samples':times},'layers':[],
            'provenance':context.provenance,'artifacts':[]}


def save_glb(path, height, dx, origin):
    # Explicit ENU -> glTF Y-up: (east, north, up) -> (east, up, -north).
    ny,nx=height.shape
    ys,xs=np.mgrid[0:ny,0:nx]
    positions=np.column_stack(((xs.ravel()+.5)*dx+origin[0],height.ravel()+origin[2],-((ys.ravel()+.5)*dx+origin[1]))).astype('<f4')
    triangles=[]
    for y in range(ny-1):
        for x in range(nx-1):
            a=y*nx+x;triangles.extend([a,a+1,a+nx,a+1,a+nx+1,a+nx])
    indices=np.asarray(triangles,dtype='<u4');binary=positions.tobytes()+indices.tobytes()
    doc={'asset':{'version':'2.0','generator':'Canopy heightfield'},'scene':0,'scenes':[{'nodes':[0]}],
         'nodes':[{'mesh':0,'extras':{'entity_id':'terrain'}}],
         'meshes':[{'primitives':[{'attributes':{'POSITION':0},'indices':1,'material':0}]}],
         'materials':[{'doubleSided':True,'pbrMetallicRoughness':{'baseColorFactor':[.42,.55,.44,1],'metallicFactor':0,'roughnessFactor':1}}],
         'buffers':[{'byteLength':len(binary)}],
         'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':positions.nbytes,'target':34962},{'buffer':0,'byteOffset':positions.nbytes,'byteLength':indices.nbytes,'target':34963}],
         'accessors':[{'bufferView':0,'componentType':5126,'count':len(positions),'type':'VEC3','min':positions.min(0).tolist(),'max':positions.max(0).tolist()},
                      {'bufferView':1,'componentType':5125,'count':len(indices),'type':'SCALAR'}]}
    encoded=json.dumps(doc,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%4)
    path.write_bytes(struct.pack('<III',0x46546c67,2,12+8+len(encoded)+8+len(binary))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary)


class Heightfield(Method):
    def validate(self,request,context):
        p=request['parameters'];lo=context.scenario['spatial']['bounds_m']['min'];hi=context.scenario['spatial']['bounds_m']['max']
        if p['nx']*p['cell_m']>hi[0]-lo[0] or p['ny']*p['cell_m']>hi[1]-lo[1] or p['obstacle_height_m']>hi[2]-lo[2]:
            raise ValueError('Generated geometry must fit scenario bounds')
    def prepare(self,request,context): return request['parameters']
    def execute(self,p,context):
        height=np.zeros((p['ny'],p['nx']),dtype='<f4');solid=np.zeros_like(height,dtype=np.uint8)
        if p['obstacle_height_m']>0:
            y,x=p['ny']//2,p['nx']//2;height[y:y+2,x:x+2]=p['obstacle_height_m'];solid[y:y+2,x:x+2]=1
        context.checkpoint()
        return {'height':height,'solid':solid,'spacing_m':p['cell_m'],'origin_m':context.scenario['spatial']['bounds_m']['min'],'diagnostics':{'quality':'synthetic_geometry','note':'heightfield surface, not a watertight volume mesh'}}
    def export(self,result,context):
        folder=context.workspace/'payload';folder.mkdir();height=result['height']
        np.save(folder/'height.npy',height);np.save(folder/'solid.npy',result['solid'])
        grid={'height':'height.npy','solid':'solid.npy','shape_yx':list(height.shape),'spacing_m':result['spacing_m'],'origin_m':result['origin_m'],'sample_location':'cell_center','coordinate_frame':'ENU'}
        write(folder/'heightfield.json',grid)
        save_glb(folder/'visual.glb',height,result['spacing_m'],result['origin_m'])
        write(folder/'entities.json',{'terrain':{'category':'terrain','glb_node':0}})
        m=base(context,[]);m['layers']=[{'id':'geometry','kind':'mesh','format':'glb','asset':'visual.glb','sampling':'static','encoding':{'coordinate_frame':'glTF-y-up'},'display':{'widget':'mesh','capabilities':['pick','opacity']}}]
        for name in ['height.npy','solid.npy','heightfield.json','entities.json']:
            from canopy._io import digest
            m['artifacts'].append({'id':'heightfield' if name=='heightfield.json' else name.replace('.','_'),'asset':name,'sha256':digest(folder/name),'media_type':'application/octet-stream'})
        write(folder/'manifest.json',m);return folder


class Fields(Method):
    def validate(self,request,context): geometry_grid(context)
    def prepare(self,request,context):
        grid,height,solid=geometry_grid(context)
        return grid,height,solid,request['parameters'],request['execution'].get('device','cpu')
    def export(self,result,context):
        folder=context.workspace/'payload';folder.mkdir();m=base(context,result['times']);grid=result['grid']
        np.save(folder/'height.npy',result['height'].astype('<f4'))
        for name,(array,unit,vector) in result['fields'].items():
            array=np.asarray(array,dtype='<f4');np.save(folder/f'{name}.npy',array)
            kind='vector_field' if vector else 'scalar_field'
            encoding={'coordinate_frame':'ENU','dtype':'<f4','shape':list(array.shape),'axes':'TCYX' if vector else 'TYX','origin_m':grid['origin_m'],'spacing_m':[grid['spacing_m']]*2,'sample_location':'cell_center','byte_order':'little','compression':'none','height_asset':'height.npy','height_dtype':'<f4'}
            if 'invalid' in result:
                np.save(folder/'invalid.npy',np.asarray(result['invalid'],dtype=np.uint8))
                encoding.update(mask_asset='invalid.npy',mask_dtype='|u1',mask_semantics='invalid_nonzero')
            m['layers'].append({'id':name,'kind':kind,'format':'npy','asset':f'{name}.npy','sampling':'linear','encoding':encoding,'field':{'name':name,'unit':unit},'display':{'widget':kind,'capabilities':['pick','legend','opacity']}})
        if 'epoch' in result:m['time']['epoch']=result['epoch']
        write(folder/'manifest.json',m);return folder


class Solar(Fields):
    def execute(self,prepared,context):
        import torch
        from urban_flow.physics.solar.model import ShadowNet, HorizonNet, ground_irradiance
        grid,height,solid,p,device=prepared
        shadow=ShadowNet(height,grid['spacing_m'],device)
        svf,_=HorizonNet(shadow,n_azimuth=p['horizon_directions'])()
        fields=[];masks=[]
        for i,alt in enumerate(p['altitudes_deg']):
            context.checkpoint();mask=shadow(alt,p['azimuth_deg'])
            ghi,_,_=ground_irradiance(mask,svf,alt,p['month'],albedo=p['albedo'])
            fields.append(ghi.cpu().numpy());masks.append(mask.float().cpu().numpy());context.emit('progress',completed=i+1,total=len(p['altitudes_deg']))
        return {'grid':grid,'height':height,'times':p['times_s'],'fields':{'irradiance':(fields,'W/m2',False),'shadow':(masks,'1',False)},'diagnostics':{'quality':'finite_values_checked','assumptions':'prescribed sun directions, ASHRAE clear sky; not measured weather'}}
    def validate(self,request,context):
        super().validate(request,context);p=request['parameters']
        if len(p['times_s'])!=len(p['altitudes_deg']) or any(b<=a for a,b in zip(p['times_s'],p['times_s'][1:])):
            raise ValueError('Solar samples require one altitude per strictly increasing time')


class Wind(Fields):
    def validate(self,request,context):
        super().validate(request,context);grid,height,_=geometry_grid(context);p=request['parameters']
        dimensions=[p['nz'],*height.shape]
        while min(dimensions)>4:
            if any(x%2 for x in dimensions):raise ValueError('MAC multigrid dimensions must be even before coarsest level')
            dimensions=[x//2 for x in dimensions]
        if p['slice_index']>=p['nz']:raise ValueError('slice_index outside vertical grid')
        if p['nz']*grid['spacing_m'] > context.scenario['spatial']['bounds_m']['max'][2]-grid['origin_m'][2]:raise ValueError('Wind domain exceeds scenario height')
        if height.max() >= p['nz']*grid['spacing_m']:raise ValueError('Wind requires fluid above the highest obstacle')
    def execute(self,prepared,context):
        import torch
        import torch.nn.functional as F
        from urban_flow.solvers.mac_torch import MAC
        grid,height,solid,p,device=prepared;dx=grid['spacing_m']
        z=(np.arange(p['nz'])+.5)*dx
        fluid=torch.as_tensor(z[:,None,None]>height[None],device=device)
        inlet=torch.full((p['nz'],height.shape[0]),float(p['inlet_m_s']),device=device,dtype=torch.float32)*fluid[:,:,0]
        solver=MAC(fluid,dx,inlet,open_top=p['open_top'])
        solver.vel[0].copy_(p['inlet_m_s']*solver.opened(0))
        volumes=[];times=[];diagnostics=[]
        def record(t):
            u,v,w=solver.vel
            west=F.pad(u[:,:,:-1],(1,0));west[:,:,0]=inlet
            south=F.pad(v[:,:-1,:],(0,0,1,0));bottom=F.pad(w[:-1],(0,0,0,0,1,0))
            volumes.append(torch.stack([.5*(u+west),.5*(v+south),.5*(w+bottom)]).cpu().numpy().copy());times.append(t)
        diagnostics.append(solver.project(rtol=p['pressure_rtol'],maxiter=p['pressure_iterations']));record(0.)
        time=0.
        for frame in range(1,p['frames']+1):
            target=frame*p['frame_seconds']
            while time<target-1e-10:
                context.checkpoint();speed=max(p['inlet_m_s'],sum(float(v.abs().max()) for v in solver.vel),1e-6)
                dt=min(p['dt_max_s'],.4*dx/speed,target-time)
                solver.advect(dt);diagnostics.append(solver.project(rtol=p['pressure_rtol'],maxiter=p['pressure_iterations']));time+=dt
            record(target);context.emit('progress',completed=frame,total=p['frames'])
        full=np.asarray(volumes,dtype='<f4');k=p['slice_index'];sampling_grid=dict(grid,origin_m=[*grid['origin_m'][:2],grid['origin_m'][2]+float(z[k])])
        return {'grid':sampling_grid,'height':np.zeros_like(height),'times':times,'fields':{'velocity':(full[:,:,k],'m/s',True)},'volume':full,'faces':torch.stack(solver.vel).cpu().numpy(),'fluid':fluid.cpu().numpy().astype('u1'),'inlet':inlet.cpu().numpy(),'invalid':(~fluid[k]).cpu().numpy().astype(np.uint8),'diagnostics':{'quality':'pressure_projection_passed','max_divergence_rms':max(x['divergence_rms'] for x in diagnostics),'assumptions':'incompressible inviscid staggered MAC; west inlet/east pressure outlet; no turbulence closure','slice_index':k}}
    def export(self,result,context):
        from canopy._io import digest
        folder=super().export(result,context);m=read(folder/'manifest.json')
        np.save(folder/'velocity_tczyx.npy',result['volume']);np.save(folder/'invalid.npy',result['invalid'])
        write(folder/'volume.json',{'file':'velocity_tczyx.npy','dtype':'<f4','axes':'TCZYX','shape':list(result['volume'].shape),'coordinate_frame':'ENU','components':['east','north','up'],'unit':'m/s','spacing_m':[result['grid']['spacing_m']]*3,'origin_m':geometry_grid(context)[0]['origin_m'],'sample_location':'cell_center','time_s':result['times']})
        np.save(folder/'faces_czyx.npy',result['faces'].astype('<f4'))
        np.save(folder/'fluid_zyx.npy',result['fluid'])
        np.save(folder/'inlet_zy.npy',result['inlet'].astype('<f4'))
        write(folder/'mac_state.json',{'schema_version':'1.0.0','faces':'faces_czyx.npy','fluid':'fluid_zyx.npy','inlet':'inlet_zy.npy','axes':'CZYX','face_convention':'positive_face_of_cell','components':['east','north','up'],'spacing_m':result['grid']['spacing_m'],'origin_m':geometry_grid(context)[0]['origin_m'],'time_s':result['times'][-1],'open_top':context.request['parameters']['open_top']})
        for name in ['velocity_tczyx.npy','volume.json','faces_czyx.npy','fluid_zyx.npy','inlet_zy.npy','mac_state.json']:
            m['artifacts'].append({'id':name.replace('.','_'),'asset':name,'sha256':digest(folder/name),'media_type':'application/octet-stream'})
        m['layers'][0]['encoding'].update(mask_asset='invalid.npy',mask_dtype='|u1',mask_semantics='invalid_nonzero')
        write(folder/'manifest.json',m);return folder
