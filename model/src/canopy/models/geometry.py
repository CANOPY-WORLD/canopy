"""Geometry preparation adapters using the transplanted Physics4D GLB reader."""
import math
import shutil
import numpy as np
from canopy._io import read,write,digest,relative
from .methods import Heightfield


def node_transform(node):
    if 'matrix' in node:
        if any(k in node for k in ('rotation','scale','translation')):
            raise ValueError('glTF node cannot combine matrix and TRS')
        matrix=np.asarray(node['matrix'],dtype=float).reshape(4,4,order='F')
    else:
        x,y,z,w=node.get('rotation',[0,0,0,1])
        if not math.isclose(x*x+y*y+z*z+w*w,1,abs_tol=1e-5):raise ValueError('Invalid glTF quaternion')
        matrix=np.eye(4)
        matrix[:3,:3]=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                              [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                              [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]) @ np.diag(node.get('scale',[1,1,1]))
        matrix[:3,3]=node.get('translation',[0,0,0])
    if not np.isfinite(matrix).all() or not np.allclose(matrix[3],[0,0,0,1]):raise ValueError('Invalid glTF affine transform')
    return matrix


def meshes(doc):
    """Yield instances in the selected glTF scene, preserving parent transforms."""
    scene=doc.get('scene',0)
    roots=doc['scenes'][scene]['nodes']
    visited=set()
    def walk(index,parent):
        if index in visited:raise ValueError('glTF node is repeated or cyclic')
        visited.add(index);node=doc['nodes'][index]
        if 'skin' in node or 'weights' in node:raise ValueError('Bake skinned/morph geometry before rasterization')
        world=parent@node_transform(node)
        if 'mesh' in node:yield index,node,doc['meshes'][node['mesh']],world
        for child in node.get('children',[]):yield from walk(child,world)
    for index in roots:yield from walk(index,np.eye(4))


class RasterizeGLB(Heightfield):
    def validate(self,request,context):
        from urban_geometry.voxelization.glb_plan import read_glb_header
        asset,m,path=context.inputs['geometry'];p=request['parameters']
        layer=next((x for x in m['layers'] if x['id']==p['layer_id'] and x['id'] in asset['payload']['layers']),None)
        if layer is None or layer['kind']!='mesh' or layer.get('format')!='glb':raise ValueError('Select a GLB mesh layer')
        bounds=p['bounds_xy_m'];lo=context.scenario['spatial']['bounds_m']['min'];hi=context.scenario['spatial']['bounds_m']['max']
        if not lo[2]<=p['ground_elevation_m']<=hi[2]:raise ValueError('Ground datum outside scenario bounds')
        if bounds[0]>=bounds[2] or bounds[1]>=bounds[3]:raise ValueError('Invalid horizontal bounds')
        if bounds[0]<lo[0] or bounds[1]<lo[1] or bounds[2]>hi[0] or bounds[3]>hi[1]:raise ValueError('Crop outside scenario bounds')
        shape=np.rint((np.asarray(bounds[2:])-bounds[:2])/p['cell_m']).astype(int)
        if min(shape)<3 or int(np.prod(shape))>p['max_cells']:raise ValueError('Grid is too small or exceeds max_cells')
        if not np.allclose(shape*p['cell_m'],np.asarray(bounds[2:])-bounds[:2]):raise ValueError('Bounds must contain a whole number of cells')
        doc,_=read_glb_header(relative(path.parent,layer['asset']))
        if doc.get('animations'):raise ValueError('Bake animated GLB to a selected static frame first')
        list(meshes(doc))
        for mesh in doc['meshes']:
            for primitive in mesh['primitives']:
                if primitive.get('mode',4)!=4 or primitive.get('targets'):raise ValueError('Rasterizer supports static triangles only')
                if 'KHR_draco_mesh_compression' in primitive.get('extensions',{}):
                    import importlib.util
                    if importlib.util.find_spec('DracoPy') is None:raise ValueError('Draco GLB requires the geometry extra (DracoPy)')
        if any('EXT_meshopt_compression' in b.get('extensions',{}) for b in doc.get('bufferViews',[])):
            raise ValueError('Decode Meshopt GLB before rasterization; browser decoding remains supported')
    def prepare(self,request,context):
        asset,m,path=context.inputs['geometry'];p=request['parameters']
        return relative(path.parent,next(x['asset'] for x in m['layers'] if x['id']==p['layer_id'])),p
    def execute(self,prepared,context):
        from urban_geometry.voxelization.glb_plan import read_glb_header
        from urban_geometry.voxelization.prepare_glb import read_primitive,raster
        path,p=prepared;doc,offset=read_glb_header(path);bounds=p['bounds_xy_m'];dx=p['cell_m']
        nx,ny=np.rint((np.asarray(bounds[2:])-bounds[:2])/dx).astype(int)
        absolute=np.full((ny,nx),-np.inf,dtype='<f4');entities={};primitives=0
        with path.open('rb') as stream:
            for index,node,mesh,world in meshes(doc):
                context.checkpoint()
                for primitive in mesh['primitives']:
                    points,faces=read_primitive(doc,stream,offset,primitive)
                    if not np.isfinite(points).all() or (faces<0).any() or (faces>=len(points)).any():raise ValueError('Invalid mesh primitive')
                    points=points@world[:3,:3].T+world[:3,3]
                    enu=points[:,[0,2,1]];enu[:,1]*=-1
                    # Restrict triangle work to the requested crop without altering surfaces.
                    if not (enu[:,0].max()<bounds[0] or enu[:,0].min()>bounds[2] or enu[:,1].max()<bounds[1] or enu[:,1].min()>bounds[3]):
                        xy=enu[faces,:2]
                        intersects=(xy[:,:,0].max(axis=1)>=bounds[0])&(xy[:,:,0].min(axis=1)<=bounds[2])&(xy[:,:,1].max(axis=1)>=bounds[1])&(xy[:,:,1].min(axis=1)<=bounds[3])
                        raster(enu,faces[intersects],absolute,bounds[0],bounds[1],dx)
                    primitives+=1
                key=node.get('extras',{}).get('entity_id',f'node_{index}')
                if key in entities:raise ValueError('Duplicate stable entity ID')
                entities[key]={'glb_node':index,'name':node.get('name',''),'category':'mesh'}
                context.emit('progress',completed=len(entities),total=len(doc['nodes']))
        missing=~np.isfinite(absolute)
        if missing.any() and p['uncovered_ground_m'] is None:raise ValueError('GLB does not cover every sample; provide explicit uncovered_ground_m assumption or reduce crop')
        if missing.any():absolute[missing]=p['uncovered_ground_m']
        origin=[bounds[0],bounds[1],p['ground_elevation_m']]
        height=absolute-p['ground_elevation_m']
        if (height<0).any():raise ValueError('Surface below specified ground_elevation_m')
        if absolute.max()>context.scenario['spatial']['bounds_m']['max'][2]:raise ValueError('Sampled surface outside scenario vertical bounds')
        return {'height':height.astype('<f4'),'solid':(height>p['obstacle_threshold_m']).astype('u1'),'spacing_m':dx,'origin_m':origin,'visual_source':path,'entities':entities,'coverage':(~missing).astype('u1'),
                'diagnostics':{'quality':'geometry_rasterized','primitives':primitives,'uncovered_cells':int(missing.sum()),'uncovered_ground_m':p['uncovered_ground_m'],'approximation':'maximum sampled surface; columns above explicit flat datum; no watertight-volume claim'}}
    def export(self,result,context):
        folder=super().export(result,context)
        shutil.copy2(result['visual_source'],folder/'visual.glb');write(folder/'entities.json',result['entities'])
        np.save(folder/'coverage.npy',result['coverage'])
        m=read(folder/'manifest.json')
        for artifact in m['artifacts']:
            artifact['sha256']=digest(folder/artifact['asset'])
        m['artifacts'].append({'id':'sample_coverage','asset':'coverage.npy','sha256':digest(folder/'coverage.npy'),'media_type':'application/octet-stream'})
        write(folder/'manifest.json',m);return folder
