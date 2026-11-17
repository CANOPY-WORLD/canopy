"""Public infrastructure inventory: retain raw sources, no inferred connections."""
import csv,json,shutil,subprocess,zipfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import requests,numpy as np,trimesh
from shapely.geometry import shape,mapping,box
from shapely.ops import transform
from common.storage import Storage
from common.export import write,digest
from common.contract import validate
from common.runs import promote,refresh_catalog
from energy.pilot import acquire,projection,extract_osm,ribbons,line_parts

def main():
 s=Storage.load();scene='tower_hamlets';config=json.loads((s.metadata(scene)/'configs/energy_pilot.json').read_text());spatial=json.loads((s.metadata(scene)/'project.json').read_text())['spatial']
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');rid='energy_inventory_'+stamp
 source=s.assets(scene,'input')/rid;acquire(s,config,spatial,source)
 project,inverse=projection(spatial);lo,hi=spatial['bounds_m']['min'],spatial['bounds_m']['max'];domain=box(*lo[:2],*hi[:2]);a,b=inverse.transform(*lo[:2]),inverse.transform(*hi[:2]);notes=[]
 # Query only public endpoints; retain failures and never substitute empty success.
 query=f'[out:xml][timeout:40];(nwr["amenity"="charging_station"]({a[1]},{a[0]},{b[1]},{b[0]});nwr["power"~"^(substation|transformer|line|minor_line|cable)$"]({a[1]},{a[0]},{b[1]},{b[0]}););(._;>;);out meta;'
 write(source/'overpass_query.json',dict(query=query))
 osm=json.loads((source/'osm_energy.geojson').read_text())
 try:
  url='https://overpass-api.de/api/interpreter';r=requests.post(url,data={'data':query},timeout=65);r.raise_for_status();(source/'overpass.xml').write_bytes(r.content)
  if b'<remark>' in r.content:raise ValueError('Overpass returned incomplete query')
  fresh=extract_osm(source/'overpass.xml',spatial);write(source/'osm_refreshed.geojson',fresh);osm=fresh
  notes.append(dict(source='OSM',url=url,status='refreshed',retrieved_at=datetime.now(timezone.utc).isoformat(),license='ODbL-1.0',attribution='© OpenStreetMap contributors'))
 except Exception as e:notes.append(dict(source='OSM',status='retained_snapshot_fallback',error=str(e),snapshot='2026-10-07'))
 for ds in ['grid-and-primary-sites','ukpn-secondary-sites']:
  url=f'https://ukpowernetworks.opendatasoft.com/api/explore/v2.1/catalog/datasets/{ds}/records'
  try:
   r=requests.get(url,params={'limit':1},timeout=25);write(source/(ds+'_access.json'),dict(status=r.status_code,response=r.json(),url=r.url));notes.append(dict(source=ds,status=r.status_code,url=r.url,limitation='No authenticated account used; metadata is not a network asset inventory.'))
  except Exception as e:notes.append(dict(source=ds,error=str(e)))
 write(source/'operator_charging_evidence.json',dict(retrieved_at=datetime.now(timezone.utc).isoformat(),records=[dict(site='Canada Square Car Park',operator='Tesla',address='Montgomery Street, London E14 5EW',reported_chargers=12,reported_max_power_kw=250,access_hours='24/7',source_url='https://www.tesla.com/en_au/findus/location/supercharger/canarywharfsupercharger',source_type='operator webpage',geometry=None,building_id=None,limitation='Operator listing; not live availability. No verified coordinate/building match; not added as extra mapped station.')]))
 write(source/'checksums.json',{str(p.relative_to(source)):digest(p)for p in sorted(source.rglob('*'))if p.is_file()and p.name!='checksums.json'})
 out=s.scratch(scene,'energy',rid);out.mkdir(parents=True);shutil.copytree(source,out/'sources');features=[]
 for name in ['existing_heat_lines','proposed_heat_lines','existing_heat_centres','proposed_heat_centres','heat_planning_sites']:
  for f in json.loads((source/(name+'.geojson')).read_text())['features']:
   if not f.get('geometry'):continue
   g=transform(project.transform,shape(f['geometry']))
   if not g.intersects(domain):continue
   props=dict(category=name,source='GLA London Heat Map',status='proposed'if name.startswith('proposed')else 'planning_record'if name=='heat_planning_sites'else 'mapped_existing',source_properties=f['properties'],connectivity='unknown',live_status='unknown')
   features.append(dict(type='Feature',id=name+':'+str(len(features)),geometry=mapping(g.intersection(domain)),properties=props))
 for f in osm['features']:
  p=f['properties'];cat=p['category']
  if cat not in ['substation','transformer','line','minor_line','cable','charging_station']:continue
  g=transform(project.transform,shape(f['geometry']));p=dict(p,category='osm_'+cat,source='OpenStreetMap',status='mapped_observation',connectivity='unknown',live_status='unknown',source_url='https://www.openstreetmap.org/'+f['id'])
  features.append(dict(type='Feature',id=f['id'],geometry=mapping(g.intersection(domain)),properties=p))
 write(out/'infrastructure_enu.geojson',dict(type='FeatureCollection',coordinate_reference=spatial,features=features))
 # Preserve mapped buildings, with no proximity-based assignment to chargers/networks.
 buildings=json.loads((s.run(scene,config['geometry_run']).parent/config['energy_context_run']/'buildings.json').read_text()) if 'energy_context_run'in config else json.loads((s.assets(scene,'input')/config['building_input']).read_text())
 write(out/'buildings.json',buildings)
 with (out/'buildings.csv').open('w')as f:
  w=csv.writer(f);w.writerow(['building_id','name','charger_connection','electric_connection','heat_connection'])
  for b in buildings['buildings']:w.writerow([b['id'],b.get('name',''),'unknown','unknown','unknown'])
 geographic=[{**f,'geometry':mapping(transform(inverse.transform,shape(f['geometry'])))}for f in features]
 write(out/'infrastructure_wgs84.geojson',dict(type='FeatureCollection',features=geographic))
 with (out/'assets.csv').open('w')as f:
  fields=['id','category','name','operator','voltage','capacity','socket:type2','socket:type2:output','socket:type2_combo','socket:type2_combo:output','access','opening_hours','source','source_url','status','connectivity','live_status'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for x in features:w.writerow({k:x['id']if k=='id'else x['properties'].get(k,'')for k in fields})
 layers=[];colors={'existing_heat_lines':[245,92,148,255],'proposed_heat_lines':[255,169,67,255],'osm_line':[85,193,255,255],'osm_cable':[85,193,255,255],'osm_substation':[70,175,245,255],'osm_charging_station':[76,221,152,255]}
 for cat in sorted(set(f['properties']['category']for f in features)):
  fs=[f for f in features if f['properties']['category']==cat];meshes=[];color=colors.get(cat,[196,159,240,255])
  for f in fs:
   g=shape(f['geometry']);lines=list(line_parts(g))
   if lines:meshes.append(ribbons(lines,color,z=5,width=3,dashed=cat.startswith('proposed')))
   else:
    p=g.representative_point();m=trimesh.creation.box(extents=[8,12,8]);m.apply_translation([p.x,6,-p.y]);m.visual.vertex_colors=color;meshes.append(m)
  if not meshes:continue
  asset=cat+'.glb';trimesh.util.concatenate(meshes).export(out/asset);layers.append(dict(id=cat,kind='mesh',format='glb',asset=asset,sampling='static',encoding=dict(coordinate_frame='glTF-y-up'),display=dict(widget='mesh',capabilities=['opacity','pick'])))
 coverage={key:sum(bool(f['properties'].get(key)) for f in features if f['properties']['category']=='osm_charging_station')for key in ['operator','capacity','socket:type2','socket:type2:output','socket:type2_combo:output','access','opening_hours']}
 report=dict(charger_field_coverage=coverage,counts=dict(Counter(f['properties']['category']for f in features)),building_count=len(buildings['buildings']),acquisition=notes,limits=['Point glyphs are illustrative, not equipment dimensions.','No inferred cables, building/charger assignments, demand, operational status or hydraulic parameters.','GeoJSON coordinates are local ENU metres, not RFC7946 longitude/latitude.','OSM and GLA observations are not independently field verified; cross-source deduplication not asserted.'])
 write(out/'report.json',report)
 with zipfile.ZipFile(out/'source_snapshot.zip','w',zipfile.ZIP_DEFLATED)as z:
  for p in (s.root/'src/energy').glob('*.py'):z.write(p,str(p.relative_to(s.root)))
 artifacts=[dict(id='source_snapshot'if p.name=='source_snapshot.zip'else 'source_'+str(i),asset=str(p.relative_to(out)),sha256=digest(p),media_type='application/octet-stream')for i,p in enumerate(sorted(out.rglob('*')))if p.is_file()and p.suffix!='.glb']
 disclaimer='公开设施清单：粉色为已记录热网，橙色虚线为规划热网，蓝色为已映射电力设施，绿色为充电站。设备符号非实际尺寸；未推断地下电缆、建筑连接或实时运行状态。'
 m=dict(schema_version='1.1.0',scene_id=scene,simulation='energy_inventory',run_id=rid,status='complete',created_at=datetime.now(timezone.utc).isoformat(),provenance=dict(code_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,parameters=dict(disclaimer=disclaimer),inputs=[dict(id='source_checksums',sha256=digest(source/'checksums.json'))]),spatial=spatial,time=dict(unit='s',samples=[]),layers=layers,artifacts=artifacts)
 write(out/'manifest.json',m);validate(out/'manifest.json');dest=promote(s,out);vid=rid.lower();base=config['geometry_run']
 write(s.metadata(scene)/'views'/f'{vid}.json',dict(schema_version='1.1.0',scene_id=scene,title='公开电网、热网和充电设施',time_alignment='relative',runs=[rid,base],layers=[dict(run_id=rid,layer_id=l['id'],visible=True)for l in layers]+[dict(run_id=base,layer_id='geometry',visible=True)],camera=dict(position=[3000,-3800,3800],target=[0,0,0])))
 refresh_catalog(s);print('VIEW',vid,flush=True);print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
