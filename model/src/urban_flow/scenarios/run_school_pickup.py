"""Retain local controlled school-source comparisons on the shared ENU scene."""
import argparse,json,shutil,time
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from common.storage import Storage
from common.export import digest,write
from common.provenance import snapshot_sources
from common.contract import validate
from common.runs import promote
from urban_flow.scenarios.school_pickup import scenario_sources,simulate,receptor_series,CASES

def raster_roads(roads,ids,origin,shape,dx):
 w=np.zeros(shape,float);used=[]
 for r in roads:
  if str(r['osm_way_id']) not in set(map(str,ids)):continue
  points=np.asarray(r.get('enu_xy',r.get('coordinates_enu_m')));used.append(str(r['osm_way_id']))
  for a,b in zip(points,points[1:]):
   q=a+np.linspace(0,1,max(2,int(np.linalg.norm(b-a)/(dx/2))+1))[:,None]*(b-a);ij=np.floor((q-origin)/dx).astype(int);ok=(ij[:,0]>=0)&(ij[:,0]<shape[1])&(ij[:,1]>=0)&(ij[:,1]<shape[0]);w[ij[ok,1],ij[ok,0]]=1
 if set(map(str,ids))-set(used):raise ValueError('Selected mapped road missing')
 return w

def idle_support(roads,point,origin,dx,invalid,radius=20):
 yy,xx=np.indices(roads.shape);distance=np.hypot(origin[0]+(xx+.5)*dx-point[0],origin[1]+(yy+.5)*dx-point[1]);valid=(roads>0)&~invalid
 if not valid.any():raise ValueError('No valid road cells')
 nearest=float(distance[valid].min())
 if nearest>40:raise ValueError('Idling candidate farther than40m from selected road')
 support=valid&(distance<=max(radius,nearest+dx));return support.astype(float),nearest

def route_proxy(outputs,route,origin,dx,invalid):
 if not route:return {'available':False,'reason':'No supported pedestrian network route supplied'}
 p=np.asarray(route['enu_xy']);samples=[];weights=[]
 for a,b in zip(p,p[1:]):
  length=float(np.linalg.norm(b-a));n=max(1,int(np.ceil(length/2)));samples.extend(a+(np.arange(n)+.5)[:,None]/n*(b-a));weights.extend([length/n/1.4]*n)
 q=np.asarray(samples);ij=np.floor((q-origin)/dx).astype(int);ok=(ij[:,0]>=0)&(ij[:,0]<invalid.shape[1])&(ij[:,1]>=0)&(ij[:,1]<invalid.shape[0]);valid=ok.copy();valid[ok]&=~invalid[ij[ok,1],ij[ok,0]];w=np.asarray(weights)
 return {'available':True,'semantics':'Frozen600s concentration sampled along mappedcandidate path at assumed1.4m/s; arbitrary concentration-seconds proxy, not inhaled dose or safety certification. Invalid route portions are omitted and disclosed.','route':route,'walk_seconds':float(w.sum()),'valid_duration_fraction':float(w[valid].sum()/w.sum()),'case_proxy_au_s':{case:float(np.dot(a[-1,ij[valid,1],ij[valid,0]],w[valid]))for case,a in outputs.items()}}

def run(config):
 c=json.loads(Path(config).read_text());sitepath=Path(c['site']);site=json.loads(sitepath.read_text());plan=c['source_plan'];storage=Storage.load();wr=storage.run('tower_hamlets',c['wind_run']);wm=json.loads((wr/'manifest.json').read_text());layer=next(x for x in wm['layers']if x['id']==c['wind_layer']);enc=layer['encoding'];dx=4.;bounds=site['bounds_enu_m'];origin=np.array(bounds[:2],float);ix,iy=((origin-np.array(enc['origin_m'][:2]))/dx).astype(int);nx=int((bounds[2]-bounds[0])/dx);ny=int((bounds[3]-bounds[1])/dx)
 if (nx,ny)!=(200,200)or not np.allclose((origin-np.array(enc['origin_m'][:2]))/dx,[ix,iy]):raise ValueError('Expected aligned800m ROI')
 whole=np.load(wr/layer['asset'],mmap_mode='r');mask=np.load(wr/enc['mask_asset']).astype(bool)
 if ix<0 or iy<0 or ix+nx>mask.shape[1]or iy+ny>mask.shape[0]:raise ValueError('ROI exceeds actual wind coverage')
 uv=whole[-1,:2,iy:iy+ny,ix:ix+nx].copy();invalid=mask[iy:iy+ny,ix:ix+nx].copy();roads=site.get('mapped_roads') or json.loads((sitepath.parent/'mapped_roads.json').read_text())['roads'];w=raster_roads(roads,plan['rolling_road_ids'],origin,(ny,nx),dx)
 idle_roads=raster_roads(roads,plan.get('idling_road_ids',plan['rolling_road_ids']),origin,(ny,nx),dx)
 gate,gn=idle_support(idle_roads,plan['gate_idling_point_enu_m'],origin,dx,invalid);peripheral,pn=idle_support(idle_roads,plan['peripheral_idling_point_enu_m'],origin,dx,invalid)
 sources=scenario_sources(w,gate,peripheral,invalid,c);start=time.time();times,outputs,diag=simulate(uv,invalid,sources,c)
 out=storage.scratch('tower_hamlets','school_pickup',c['run_id']);out.mkdir(parents=True,exist_ok=False);(out/'data').mkdir();(out/'provenance').mkdir();np.save(out/'data/invalid.npy',invalid.astype('u1'));np.save(out/'provenance/frozen_wind_enu.npy',uv)
 layers=[];maxvalue=max(float(a.max())for a in outputs.values());differences={n:a-outputs['baseline']for n,a in outputs.items()if n!='baseline'};diffmax=max(float(np.abs(a).max())for a in differences.values())
 for name,a in {**outputs,**{n+'_minus_baseline':d for n,d in differences.items()}}.items():
  np.save(out/f'data/{name}.npy',a.astype('<f4'));diff=name.endswith('_minus_baseline');layers.append({'id':name,'kind':'scalar_field','format':'npy','asset':f'data/{name}.npy','sampling':'step','field':{'name':name.replace('_',' '),'unit':'a.u.'},'encoding':{'coordinate_frame':'ENU','dtype':'<f4','shape':list(a.shape),'axes':'TYX','origin_m':[*origin,2.0],'spacing_m':[dx,dx],'sample_location':'cell_center','byte_order':'little','compression':'none','mask_asset':'data/invalid.npy','mask_dtype':'|u1','mask_semantics':'invalid_nonzero'},'display':{'widget':'scalar_field','capabilities':['pick','legend','opacity'],'range':[-diffmax,diffmax]if diff else[0,maxvalue]}})
 for case,parts in sources.items():
  for component in ['rolling','idling']:np.save(out/f'provenance/source_{case}_{component}.npy',parts[component].astype('<f4'))
 receptors={r['id']:{'definition':r,'cases':{case:receptor_series(a,r['enu_m'],origin,dx,invalid)for case,a in outputs.items()}}for r in plan['receptors']}
 limits=['Controlled local800m planar tracer with zero external inflow concentration; excludes regionalbackground and importedpollution.','Wind frozen at029modelstep100; surrogate10000s interpretation is not calibrated physicaltime. Tracer600s clock is independent.','Assumed trip/dwell/emission parameters are illustrative, not measuredschooltraffic. Rolling source is not a complete nonexhaust emissions model.','Peripheral scenario relocates idling only; rolling approach sources unchanged. No legalparking/access/safewalking guarantee.','Mapped campus/gate candidates may be unverified; receptors inside coarse solids remain invalid, never snapped throughwalls.','Arbitraryunits, no chemistry/deposition/verticalexchange; not healthrisk or dose.']
 summary={'school_id':site['school_id'],'name':site['name'],'run_id':c['run_id'],'times_s':times.tolist(),'bounds_enu_m':bounds,'shape':[len(times),ny,nx],'cell_m':dx,'height_m':2.,'cases':list(CASES),'shared_range':[0,maxvalue],'difference_range':[-diffmax,diffmax],'assumptions':c,'source_mapping':{'plan':plan,'gate_nearest_road_cell_m':gn,'peripheral_nearest_road_cell_m':pn},'case_metrics':{n:{'final_mean_valid_au':float(a[-1,~invalid].mean()),'final_max_au':float(a[-1].max()),'final_mass_au':diag[n][-1]['mass_au'],'emitted_au':diag[n][-1]['emitted_au'],'max_mass_balance_error_au':max(abs(r['balance_error_au'])for r in diag[n])}for n,a in outputs.items()},'receptors':receptors,'route_proxy':route_proxy(outputs,plan.get('pedestrian_route'),origin,dx,invalid),'limitations':limits,'runtime_s':time.time()-start}
 write(out/'provenance/selected_mapped_roads.json',[r for r in roads if str(r['osm_way_id']) in set(map(str,plan['rolling_road_ids']+plan.get('idling_road_ids',[])))]);write(out/'summary.json',summary);write(out/'provenance/mass_balance.json',diag);shutil.copy2(sitepath,out/'provenance/site.json');shutil.copy2(config,out/'provenance/config.json');revision=snapshot_sources(storage.root,out/'source_snapshot.tar.gz')
 artifacts=[{'id':'source_snapshot'if p.name=='source_snapshot.tar.gz'else p.relative_to(out).as_posix(),'asset':p.relative_to(out).as_posix(),'sha256':digest(p),'media_type':'application/octet-stream'}for p in sorted(out.rglob('*'))if p.is_file()and not p.is_relative_to(out/'data')]
 spatial=dict(wm['spatial']);spatial['bounds_m']={'min':[bounds[0],bounds[1],0],'max':[bounds[2],bounds[3],4]};manifest={'schema_version':'1.1.0','scene_id':'tower_hamlets','simulation':'pollution','run_id':c['run_id'],'status':'complete','created_at':datetime.now(timezone.utc).isoformat(),'spatial':spatial,'time':{'unit':'s','samples':times.tolist()},'provenance':{'code_revision':revision,'dirty':True,'parameters':{'config':c,'limitations':limits},'inputs':[{'id':'wind_manifest','sha256':digest(wr/'manifest.json')},{'id':'site','sha256':digest(sitepath)}]},'layers':layers,'artifacts':artifacts};write(out/'manifest.json',manifest);validate(out/'manifest.json');return promote(storage,out)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);args=ap.parse_args();print(run(args.config))
