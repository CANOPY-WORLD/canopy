#!/usr/bin/env python3
"""Explicit London retained-input conversion; never edits canonical Scenario metadata."""
import argparse, gzip, json, shutil, hashlib, math
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
from scipy.ndimage import map_coordinates, distance_transform_edt
from common.storage import Storage
from canopy._io import write, digest
from canopy.scenario.store import create
from canopy.assets.store import import_run


def prepare(args):
    root=Path(__file__).resolve().parents[2]; workspace=Path(args.workspace).resolve()
    workspace.mkdir(parents=True,exist_ok=False)
    (workspace/'AGENTS.md').write_text('Isolated conditional London traffic pollution experiment.\n')
    shutil.copytree(root/'asset/schemas',workspace/'asset/schemas')
    (workspace/'visualizer').mkdir()
    for name in ('src','site','guide'):(workspace/'visualizer'/name).symlink_to(root/'visualizer'/name,target_is_directory=True)
    storage=Storage.load(workspace);sid='imperial_corridor_8km'
    spatial=json.loads((root/'scenario'/sid/'scenario.json').read_text())['spatial']
    spatial['bounds_m']={'min':[-4000.,-4000.,0.],'max':[4000.,4000.,256.]}
    create(storage,sid,'London · conditional traffic exhaust transport',spatial)
    inp=workspace/'cache'/'conversion';inp.mkdir(parents=True)
    wind=Path(args.wind);height=Path(args.height);emissions=Path(args.emissions);network=Path(args.network)
    vmeta=json.loads((wind.parent/'metadata.json').read_text())
    if vmeta['components']!='ENU east, north, up (east = -dataset u)' or vmeta['origin_enu_m']!=[-4098.,-4098.,-2.] or vmeta['cell_m']!=8:raise ValueError('Unexpected wind alignment; explicit new adapter needed')
    hmeta=json.loads((height.parent/'manifest.json').read_text())
    if hmeta['frame']['x0_m']!=-4096 or hmeta['frame']['y0_m']!=-4096 or hmeta['frame']['cell_m']!=4 or hmeta['geometry_sha256']!=vmeta['rollout_manifest']['geometry_sha256']:raise ValueError('Geometry/wind source mismatch')
    loc=ET.parse(network).getroot().find('location')
    if loc.get('netOffset')!='0.000000,0.000000' or '+lat_0=51.506427 +lon_0=-0.200473' not in loc.get('projParameter',''):raise ValueError('SUMO coordinate transform must be explicit')
    raw=np.load(wind,mmap_mode='r');h4=np.load(height,mmap_mode='r')
    if raw.shape!=(3,32,1024,1024) or h4.shape!=(2048,2048):raise ValueError('Unexpected retained arrays')
    # Exact [-4000,4000) crop; 75th-percentile footprint representation retained
    # from source, conservative maximum of the 2x2 horizontal 4m heights.
    h8=h4[24:2024,24:2024].reshape(1000,2,1000,2).max(axis=(1,3))
    fluid=((np.arange(32)[:,None,None]+.5)*8>h8[None]).astype('u1')
    converted=inp/'wind';converted.mkdir()
    out=np.lib.format.open_memmap(converted/'velocity.npy',mode='w+',dtype='<f4',shape=(3,32,1000,1000))
    yy,xx=np.mgrid[0:1000,0:1000];xy=[(yy*8+102)/8,(xx*8+102)/8]
    for c in range(3):
        for z in range(32):
            coords=np.array([np.full_like(yy,z+.25,dtype=float),*xy])
            # Last layer requires the nearest final wind centre (250m -> 252m).
            out[c,z]=map_coordinates(raw[c],coords,order=1,mode='nearest',prefilter=False)
    out.flush();del out
    np.save(converted/'fluid.npy',fluid)
    grid={'schema_version':'1.0.0','arrays':{'velocity':'velocity.npy','fluid':'fluid.npy'},'shape_zyx':[32,1000,1000],'spacing_m':8.,'origin_m':[-4000.,-4000.,0.],'coordinate_frame':'ENU','unit':'m/s','mode':'frozen_cell_center_reconstruct_project','wind_model_time_s':7500.,'conversion':'Trilinear cell-centre interpolation from origin [-4098,-4098,-2], 8m. Top target centre 252m holds final source centre 250m. Fluid uses max of each 2x2 original 4m height block. Faces reconstructed and pressure-projected at execution.'}
    write(converted/'transport-grid.json',grid)
    inputs=[{'id':name,'sha256':digest(path)} for name,path in [('wind_volume',wind),('wind_metadata',wind.parent/'metadata.json'),('height',height),('geometry_metadata',height.parent/'manifest.json'),('network',network),('emissions',emissions)]]
    source=Path(__file__);source_sha=digest(source)
    def manifest(folder,rid,simulation,times,layers):
        shutil.copy2(source,folder/'conversion-source.py')
        m={'schema_version':'1.1.0','scene_id':sid,'simulation':simulation,'run_id':rid,'status':'complete','created_at':datetime.now(timezone.utc).isoformat(),'spatial':spatial,'time':{'unit':'s','samples':times},'layers':layers,'provenance':{'code_revision':source_sha,'dirty':True,'parameters':{'conversion':grid['conversion'],'relative_traffic_start_s':args.start,'original_wind_solver':'geometry-initialised SCALED; no CFD validation','source_geometry_sha256':hmeta['geometry_sha256']},'inputs':inputs},'artifacts':[{'id':'source_snapshot','asset':'conversion-source.py','sha256':source_sha,'media_type':'text/x-python'}]}
        return m
    # Existing vector widget consumes a static horizontal slice; full volume is an artifact.
    vv=np.load(converted/'velocity.npy',mmap_mode='r');np.save(converted/'slice.npy',vv[:,0]);del vv
    np.save(converted/'invalid.npy',1-fluid[0])
    enc={'coordinate_frame':'ENU','dtype':'<f4','shape':[3,1000,1000],'axes':'CYX','origin_m':[-4000.,-4000.,4.],'spacing_m':[8.,8.],'sample_location':'cell_center','byte_order':'little','compression':'none','mask_asset':'invalid.npy','mask_dtype':'|u1','mask_semantics':'invalid_nonzero'}
    m=manifest(converted,'traffic_pollution_wind_8m','wind',[],[{'id':'wind','kind':'vector_field','format':'npy','asset':'slice.npy','sampling':'static','encoding':enc,'field':{'name':'Frozen wind input before projection','unit':'m/s'},'display':{'widget':'vector_field','capabilities':['pick']}}])
    for name in ['velocity.npy','fluid.npy','transport-grid.json']:
        m['artifacts'].append({'id':'transport_grid_json' if name.endswith('.json') else name.replace('.','_'),'asset':name,'sha256':digest(converted/name),'media_type':'application/octet-stream'})
    write(converted/'manifest.json',m)
    wind_ref=import_run(storage,sid,converted)[0]
    print('wind imported',wind_ref,flush=True)
    # Map roads intersecting a coarse building voxel to the nearest ground fluid
    # centre within two cells, accounting for every displaced or excluded mass.
    nearest_by_z={}
    def neighbours(z):
        if z not in nearest_by_z:nearest_by_z[z]=distance_transform_edt(~fluid[z].astype(bool),return_indices=True)
        return nearest_by_z[z]
    bins=[{} for _ in range(args.seconds)];outside=shifted=unmapped=total=0.;records=0;classes=set();seen=[];unresolved={};elevated=0.
    with gzip.open(emissions,'rb') if emissions.suffix=='.gz' else emissions.open('rb') as stream:
        iterator=ET.iterparse(stream,events=['start','end']);_,xmlroot=next(iterator)
        for event,elem in iterator:
            if event!='end' or elem.tag!='timestep':continue
            time=float(elem.get('time'));i=math.floor(time-args.start+1e-6)
            if 0<=i<args.seconds:
                seen.append(time)
                for vehicle in elem:
                    classes.add(vehicle.get('eclass'));mass=float(vehicle.get('PMx'))*1000*args.step
                    if not math.isfinite(mass) or mass<0:raise ValueError('Invalid SUMO mass')
                    total+=mass;records+=1
                    x=math.floor((float(vehicle.get('x'))+4000)/8);y=math.floor((float(vehicle.get('y'))+4000)/8)
                    if not(0<=x<1000 and 0<=y<1000):outside+=mass;continue
                    road_z=float(vehicle.get('z','nan'))
                    if not math.isfinite(road_z):raise ValueError('SUMO emission output must preserve z')
                    z=math.floor((road_z+1.)/8)
                    if not 0<=z<32:
                        unmapped+=mass;key=f'{z},{y},{x}';unresolved[key]=unresolved.get(key,0.)+mass;continue
                    if z>0:elevated+=mass
                    if not fluid[z,y,x]:
                        distance,nearest=neighbours(z)
                        if distance[y,x]>2:
                            unmapped+=mass;key=f'{z},{y},{x}';unresolved[key]=unresolved.get(key,0.)+mass;continue
                        y,x=nearest[:,y,x];shifted+=mass
                    idx=int((z*1000+y)*1000+x);bins[i][idx]=bins[i].get(idx,0.)+mass
            elem.clear();xmlroot.clear()
    expected=np.arange(args.start,args.start+args.seconds,args.step)
    if len(seen)!=len(expected) or not np.allclose(seen,expected,atol=1e-6,rtol=0):raise ValueError('Missing/nonuniform emission timesteps')
    mapping={'total_emitted_ug':total,'outside_domain_ug':outside,'relocated_within_16m_ug':shifted,'elevated_source_ug':elevated,'exhaust_height_above_road_m':1.,'unmapped_inside_ug':unmapped,'records':records,'emission_classes':sorted(classes),'policy':'SUMO road z plus assumed 1m exhaust height; nearest fluid cell at the same vertical layer within 16m. Explicit preview exclusions only.','partial_preview':bool(unmapped),'excluded_cells_zyx_mass_ug':unresolved}
    write(inp/'mapping-audit.json',mapping);print(json.dumps({k:v for k,v in mapping.items() if k!='excluded_cells_zyx_mass_ug'}),flush=True)
    if unmapped>0 and not args.allow_unmapped_preview:raise ValueError('Unmapped in-domain mass: fix geometry or explicitly select --allow-unmapped-preview')
    epath=inp/'emissions';epath.mkdir();offset=[0];indices=[];masses=[];totals=[]
    for row in bins:
        indices.extend(row.keys());masses.extend(row.values());offset.append(len(indices));totals.append(sum(row.values()))
    for name,data in [('times',np.arange(args.seconds+1,dtype='<f8')),('offsets',np.asarray(offset,dtype='<i8')),('indices',np.asarray(indices,dtype='<i8')),('mass_ug',np.asarray(masses,dtype='<f4'))]:np.save(epath/(name+'.npy'),data)
    emeta={'schema_version':'1.0.0','arrays':{n:n+'.npy' for n in ('times','offsets','indices','mass_ug')},'shape_zyx':grid['shape_zyx'],'origin_m':grid['origin_m'],'spacing_m':8.,'unit':'ug','pollutant':'SUMO_PMx_exhaust','time_alignment':'explicit_relative_scenario','sumo_start_s':args.start,'wind_manifest_sha256':digest(converted/'manifest.json'),'mapping':mapping}
    write(epath/'emissions.json',emeta);write(epath/'rates.json',{'labels':['PMx emission'],'values':[[v] for v in totals]})
    m=manifest(epath,'traffic_pollution_emissions_8m','traffic',list(range(args.seconds)),[{'id':'pmx','kind':'time_series','format':'json','asset':'rates.json','sampling':'step','field':{'name':'In-domain SUMO exhaust PMx','unit':'ug/s'},'display':{'widget':'time_series','capabilities':['pick']}}])
    for name in ['emissions.json',*[n+'.npy' for n in ('times','offsets','indices','mass_ug')]]:
        m['artifacts'].append({'id':'emissions_json' if name.endswith('.json') else name.replace('.','_'),'asset':name,'sha256':digest(epath/name),'media_type':'application/octet-stream'})
    write(epath/'manifest.json',m);eref=import_run(storage,sid,epath,derived_from=[wind_ref])[0]
    request=json.loads((root/'model/tests/fixtures/canopy/traffic_pollution.json').read_text());request['inputs']={'wind':wind_ref,'emissions':eref};request['parameters']['duration_s']=args.seconds
    write(workspace/'request.json',request);print(workspace/'request.json',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','wind','height','emissions','network'):p.add_argument('--'+n,required=True)
    p.add_argument('--allow-unmapped-preview',action='store_true',help='Explicit incomplete demo: account for unresolved sources without treating them as zero pollution')
    p.add_argument('--start',type=float,default=600);p.add_argument('--seconds',type=int,default=600);p.add_argument('--step',type=float,default=.1)
    prepare(p.parse_args())
