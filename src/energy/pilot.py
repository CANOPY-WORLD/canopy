"""Acquire public context and replay a bounded, lossless electricity/heat test.

No inferred real feeder topology, real demand, pipe hydraulics or extra weather
frames. Source GIS geometries are clipped only after the scene's AEQD transform.
Run with the optional requirements in energy/requirements.txt.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import re
from pathlib import Path
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import requests
from pyproj import CRS, Transformer
from shapely import contains_xy
from shapely.geometry import Point, Polygon, LineString, box, shape, mapping
from shapely.ops import transform, unary_union
import trimesh

from common.contract import validate
from common.export import digest, write
from common.storage import Storage

ARCGIS = 'https://services.arcgis.com/drifeOPKLpgnJ8Qa/arcgis/rest/services/'
LAYERS = {
    'existing_heat_lines': ('1e7b01a2f9f6417da6239165d753baa7', 'Existing_Heat_Networks_Lines/FeatureServer/6'),
    'existing_heat_centres': ('99e133d3ff25437a87f9f7b7125cded5', 'Existing_Energy_Centre_Points/FeatureServer/5'),
    'proposed_heat_lines': ('cdc737c0c98c44b8ac40ac262b5b75d1', 'proposed_hn_lines/FeatureServer/0'),
    'proposed_heat_centres': ('af995003239a4c068e9ae5f8d814b4c9', 'proposed_energy_centre_points/FeatureServer/3'),
    'heat_planning_sites': ('833159a24d3b40938fa399ae56f96639', 'lhm_communal_campus_networks_Q4_2025/FeatureServer/9'),
}


def projection(spatial):
    o = spatial['origin']
    crs = CRS.from_proj4(f"+proj=aeqd +lat_0={o['latitude']} +lon_0={o['longitude']} +datum=WGS84 +units=m")
    return Transformer.from_crs(4326, crs, always_xy=True), Transformer.from_crs(crs, 4326, always_xy=True)


def get_json(url, params=None):
    response = requests.get(url, params=params, timeout=90)
    response.raise_for_status()
    data = response.json()
    if 'error' in data:
        raise ValueError(f'{response.url}: {data["error"]}')
    return data, response.url


def acquire(storage, config, spatial, destination):
    """Keep raw queries, metadata, dates and hashes; never overwrite a snapshot."""
    destination.mkdir(parents=True, exist_ok=False)
    _, inverse = projection(spatial)
    lo, hi = spatial['bounds_m']['min'], spatial['bounds_m']['max']
    corners = [inverse.transform(x, y) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])]
    bounds = [min(p[0] for p in corners), min(p[1] for p in corners), max(p[0] for p in corners), max(p[1] for p in corners)]
    sources = []
    for name, (item, service) in LAYERS.items():
        metadata, meta_url = get_json(f'https://www.arcgis.com/sharing/rest/content/items/{item}', {'f': 'json'})
        write(destination / f'{name}_metadata.json', metadata)
        layer_metadata, _ = get_json(ARCGIS + service, {'f': 'json'})
        write(destination / f'{name}_layer.json', layer_metadata)
        params = dict(f='geojson', where='1=1', geometry=','.join(map(str, bounds)), geometryType='esriGeometryEnvelope', inSR=4326, outSR=4326, spatialRel='esriSpatialRelIntersects', outFields='*', orderByFields=layer_metadata['objectIdField'], resultRecordCount=1000, resultOffset=0)
        features, urls = [], []
        while True:
            data, url = get_json(ARCGIS + service + '/query', params)
            if data.get('type') != 'FeatureCollection':
                raise ValueError('Expected geographic FeatureCollection')
            write(destination / f'{name}_page{params["resultOffset"]}.geojson', data)
            features.extend(data['features']); urls.append(url)
            if not data.get('properties', {}).get('exceededTransferLimit') and not data.get('exceededTransferLimit') and len(data['features']) < 1000:
                break
            if not data['features']:
                raise ValueError('Pagination did not advance')
            params['resultOffset'] += len(data['features'])
        write(destination / f'{name}.geojson', dict(type='FeatureCollection', features=features))
        sources.append(dict(id=name, urls=urls, metadata_url=meta_url, retrieved_at=datetime.now(timezone.utc).isoformat(), license=metadata.get('licenseInfo'), attribution=metadata.get('accessInformation'), modified=metadata.get('modified'), count=len(features)))
    # Record the official alternative and access limitation without bypassing login.
    ukpn, ukpn_url = get_json('https://ukpowernetworks.opendatasoft.com/api/explore/v2.1/catalog/datasets/ukpn-secondary-sites')
    write(destination / 'ukpn_catalog_metadata.json', ukpn)
    sources.append(dict(id='ukpn_secondary_sites_metadata_only', url=ukpn_url, data_visible=ukpn.get('data_visible'), limitation='Catalogue says register and login to view records; no authenticated records acquired.', license=ukpn['metas']['default'].get('license')))
    osm_path = storage.assets(config['scene_id'], 'input') / config['osm_input']
    osm = extract_osm(osm_path, spatial)
    write(destination / 'osm_energy.geojson', osm)
    sources.append(dict(id='osm_energy', source_file=str(osm_path), source_sha256=digest(osm_path), url='https://www.openstreetmap.org/copyright', license='ODbL-1.0', attribution='© OpenStreetMap contributors', limitation='Existing local 2026-10-07 snapshot; tags are mapped observations, not verified current availability, capacity or connectivity.'))
    sources.append(dict(id='scope', geographic_bounds_wgs84=bounds, limitation='Scene rectangle crosses borough boundaries. Absence of a mapped asset is not evidence of absence. GLA lines are indicative, not engineering survey.'))
    write(destination / 'sources.json', sources)
    write(destination / 'checksums.json', {p.name: digest(p) for p in sorted(destination.iterdir()) if p.is_file()})
    return destination


def extract_osm(path, spatial):
    """Reuse node/way geometry; don't invent incomplete ways or relation topology."""
    project, _ = projection(spatial)
    lo, hi = spatial['bounds_m']['min'], spatial['bounds_m']['max']
    domain = box(lo[0], lo[1], hi[0], hi[1])
    nodes, features = {}, []
    for _, e in ET.iterparse(path, events=('end',)):
        if e.tag not in ('node', 'way', 'relation'):
            continue
        tags = {t.attrib['k']: t.attrib['v'] for t in e.findall('tag')}
        if e.tag == 'node':
            nodes[e.attrib['id']] = (float(e.attrib['lon']), float(e.attrib['lat']))
        category = 'charging_station' if tags.get('amenity') == 'charging_station' else tags.get('power')
        if category in ('substation', 'transformer', 'generator', 'plant', 'cable', 'line', 'charging_station'):
            geometry = None
            if e.tag == 'node':
                geometry = Point(nodes[e.attrib['id']])
            elif e.tag == 'way':
                refs = [n.attrib['ref'] for n in e.findall('nd')]
                if len(refs) >= 2 and all(n in nodes for n in refs):
                    coords = [nodes[n] for n in refs]
                    geometry = Polygon(coords) if len(coords) >= 4 and refs[0] == refs[-1] else LineString(coords)
            if geometry is not None and transform(project.transform, geometry).intersects(domain):
                features.append(dict(type='Feature', id=f'{e.tag}/{e.attrib["id"]}', geometry=mapping(geometry), properties={**tags, 'category': category, 'osm_version': e.attrib.get('version'), 'osm_timestamp': e.attrib.get('timestamp')}))
        e.clear()
    return dict(type='FeatureCollection', features=features)


def energy_balance(irradiance, area, config):
    """kW electric and kW thermal are distinct; negative net import means export."""
    irradiance, area = np.asarray(irradiance, float), np.asarray(area, float)
    if irradiance.ndim != 2 or area.shape != (irradiance.shape[1],) or not np.isfinite(irradiance).all() or not np.isfinite(area).all() or (irradiance < 0).any() or (area <= 0).any():
        raise ValueError('Invalid solar samples or areas')
    for key in ('pv_coverage_fraction', 'pv_efficiency', 'pv_performance_ratio'):
        if not 0 < config[key] <= 1:
            raise ValueError(f'Invalid {key}')
    if not np.isfinite(config['heat_pump_cop']) or config['heat_pump_cop'] < 1:
        raise ValueError('Invalid COP')
    for key in ('building_electric_kw_each', 'building_heat_kw_each', 'charging_kw_start', 'charging_kw_end'):
        if not np.isfinite(config[key]) or config[key] < 0:
            raise ValueError(f'Invalid {key}')
    pv = irradiance * area[None, :] * config['pv_coverage_fraction'] * config['pv_efficiency'] * config['pv_performance_ratio'] / 1000
    heat = np.full_like(pv, config['building_heat_kw_each'])
    hp = heat / config['heat_pump_cop']
    base = np.full_like(pv, config['building_electric_kw_each'])
    ev = np.linspace(config['charging_kw_start'], config['charging_kw_end'], len(pv))
    demand = (base + hp).sum(axis=1) + ev
    grid = demand - pv.sum(axis=1)
    return dict(pv=pv, heat=heat, hp=hp, base=base, ev=ev, demand=demand, grid=grid, ambient_heat=heat-hp)


def line_parts(geometry):
    if geometry.geom_type == 'LineString':
        yield geometry
    elif hasattr(geometry, 'geoms'):
        for part in geometry.geoms:
            yield from line_parts(part)


def ribbons(lines, color, z=7, width=4, dashed=False):
    vertices, faces = [], []
    for line in lines:
        if dashed:
            from shapely.ops import substring
            parts = [substring(line, d, min(d+12, line.length)) for d in np.arange(0, line.length, 24)]
        else:
            parts = [line]
        for part in parts:
            if part.geom_type != 'LineString':
                continue
            coords = list(part.coords)
            for a, b in zip(coords, coords[1:]):
                a, b = np.array(a[:2]), np.array(b[:2]); delta = b-a
                length = np.linalg.norm(delta)
                if length < 1e-8:
                    continue
                normal = np.array([-delta[1], delta[0]]) * width / (2*length)
                k = len(vertices)
                vertices.extend([[v[0], z, -v[1]] for v in (a+normal, b+normal, b-normal, a-normal)])
                faces.extend([[k, k+1, k+2], [k, k+2, k+3], [k+2, k+1, k], [k+3, k+2, k]])
    return trimesh.Trimesh(vertices=vertices, faces=faces, vertex_colors=np.tile(color, (len(vertices), 1)), process=False)


def build(storage, config, source, run_id):
    scene_id = config['scene_id']; meta = json.loads((storage.metadata(scene_id)/'project.json').read_text())
    spatial = meta['spatial']; project, _ = projection(spatial)
    for name, expected in json.loads((source/'checksums.json').read_text()).items():
        if digest(source/name) != expected:
            raise ValueError(f'Source snapshot changed: {name}')
    lo, hi = spatial['bounds_m']['min'], spatial['bounds_m']['max']; domain = box(*lo[:2], *hi[:2])
    trial = storage.scratch(scene_id, 'energy', run_id); trial.mkdir(parents=True, exist_ok=False)
    shutil.copytree(source, trial/'sources')
    write(trial/'config.json', config)
    solar = storage.run(scene_id, config['solar_run'])
    for name in ('values.npy', 'surface_height_m.npy', 'invalid.npy', 'times.json', 'configuration.json'):
        dest = trial/'solar'/name; dest.parent.mkdir(exist_ok=True); shutil.copy2(solar/'raw'/name, dest)
    shutil.copy2(solar/'manifest.json', trial/'solar/source_manifest.json')
    geometry = storage.assets(scene_id, 'input')/config['building_input']
    shutil.copy2(geometry, trial/'buildings.json')
    ghi = np.load(trial/'solar/values.npy', mmap_mode='r'); heights = np.load(trial/'solar/surface_height_m.npy')
    invalid = np.load(trial/'solar/invalid.npy').astype(bool)
    sm = json.loads((trial/'solar/source_manifest.json').read_text()); enc = sm['layers'][0]['encoding']
    times = json.loads((trial/'solar/times.json').read_text())
    if ghi.shape[0] != len(times) or sm['time']['samples'] != times:
        raise ValueError('Solar clock mismatch')
    if enc['axes'] != 'TYX' or enc['coordinate_frame'] != 'ENU' or sm['spatial']['origin'] != spatial['origin']:
        raise ValueError('Solar frame mismatch')
    dx, dy = enc['spacing_m']; ox, oy, _ = enc['origin_m']
    yy, xx = np.meshgrid(oy+(np.arange(heights.shape[0])+.5)*dy, ox+(np.arange(heights.shape[1])+.5)*dx, indexing='ij')
    samples, areas, selected, positions = [], [], [], []
    buildings = json.loads((trial/'buildings.json').read_text())['buildings']
    used = Polygon(); used_names = set()
    candidates = []
    for b in buildings:
        poly = unary_union([Polygon(p['outer'], p['holes']) for p in b['geometry']])
        if b.get('name') and not re.fullmatch(r'[0-9a-f-]{36}', b['name']) and poly.is_valid and 500 < poly.area < 15000 and poly.centroid.distance(Point(0, 0)) < 600:
            candidates.append((poly.centroid.distance(Point(0, 0)), b, poly))
    for _, b, poly in sorted(candidates, key=lambda x: x[0]):
        if b['name'].casefold() in used_names:
            continue
        usable = poly.difference(used)
        mask = contains_xy(usable, xx, yy) & ~invalid & (heights > 5)
        if mask.sum() < 20:
            continue
        used = used.union(poly)
        used_names.add(b['name'].casefold())
        area = float(mask.sum()*dx*dy); point = usable.representative_point()
        samples.append(np.asarray(ghi[:, mask]).mean(axis=1)); areas.append(area)
        positions.append([point.x, point.y, float(heights[mask].max())+8])
        selected.append(dict(id=b['id'], name=b['name'], roof_grid_area_m2=area, panel_area_m2=area*config['pv_coverage_fraction'], raster_cells_yx=np.argwhere(mask).tolist(), limitations='Mapped footprint intersected with elevated top-surface cells; horizontal PV coverage assumed, roof suitability not surveyed.'))
        if len(selected) == config['building_count']:
            break
    if len(selected) != config['building_count']:
        raise ValueError('Not enough distinct roof samples')
    samples = np.stack(samples, axis=1); result = energy_balance(samples, areas, config)
    write(trial/'selected_buildings.json', selected)
    write(trial/'solar_samples.json', dict(times=times, irradiance_w_m2=samples.tolist(), area_m2=areas, positions=positions))
    layers = []
    def json_layer(name, kind, data, field, unit, dynamic=False):
        if 'ids' in data:
            write(trial/f'catalog/{name}.json', dict(ids=data.pop('ids'), positions=data['positions']))
        asset = f'data/{name}.json'; write(trial/asset, data)
        layers.append(dict(id=name, kind=kind, format='json', asset=asset, sampling='linear' if dynamic else 'static', field=dict(name=field, unit=unit), display=dict(widget=kind, capabilities=['pick','legend','opacity'])))
    def mesh_layer(name, mesh):
        if not len(mesh.faces):
            return
        asset = f'data/{name}.glb'; (trial/'data').mkdir(exist_ok=True)
        mesh.export(trial/asset)
        layers.append(dict(id=name, kind='mesh', format='glb', asset=asset, sampling='static', encoding=dict(coordinate_frame='glTF-y-up'), display=dict(widget='mesh', capabilities=['pick','opacity'])))
    inventory, counts = [], {}
    def display_position(point):
        col = int((point.x-ox)//dx); row = int((point.y-oy)//dy)
        roof = float(heights[row, col]) if 0 <= row < heights.shape[0] and 0 <= col < heights.shape[1] else 0
        return [point.x, point.y, roof+12]
    for name in LAYERS:
        features = json.loads((source/f'{name}.geojson').read_text())['features']; lines=[]; points=[]; ids=[]
        for f in features:
            geo = transform(project.transform, shape(f['geometry'])).intersection(domain)
            if geo.is_empty:
                continue
            props = f['properties']; label = props.get('heat_network_name') or props.get('Site_Name') or str(f.get('id'))
            inventory.append(dict(source=name, id=f.get('id'), label=label, properties=props, scene_geometry=mapping(geo)))
            if 'lines' in name:
                lines.extend(line_parts(geo))
            else:
                points.append(display_position(geo.representative_point())); ids.append(f'{name}:{f.get("id")} | {label}')
        counts[name] = sum(x['source'] == name for x in inventory)
        if lines:
            proposed = name.startswith('proposed')
            mesh_layer(name, ribbons(lines, [255,177,67,255] if proposed else [255,80,112,255], dashed=proposed))
        if points:
            json_layer(name, 'scalar_field', dict(positions=points, ids=ids, values=[1]*len(points)), name+' · public mapped locations, marker heights illustrative', '1')
    osm = json.loads((source/'osm_energy.geojson').read_text())['features']
    categories = Counter(f['properties']['category'] for f in osm)
    for category in ('substation', 'charging_station', 'generator', 'plant'):
        points, ids = [], []
        for f in osm:
            if f['properties']['category'] != category:
                continue
            geo = transform(project.transform, shape(f['geometry'])).intersection(domain)
            if geo.is_empty:
                continue
            point = geo.representative_point(); label = f['properties'].get('name') or f['properties'].get('ref') or category
            points.append(display_position(point)); ids.append(f'OSM {f["id"]} | {label}')
            inventory.append(dict(source='osm', id=f['id'], label=label, properties=f['properties'], scene_geometry=mapping(geo)))
        if points:
            json_layer('osm_'+category, 'scalar_field', dict(positions=points, ids=ids, values=[1]*len(points)), category+' · OSM mapped, not verified operational', '1')
    charger = next(f for f in osm if f['id'] == config['charging_site_osm_id'])
    charger_point = transform(project.transform, shape(charger['geometry'])).representative_point()
    # Separate, explicitly hypothetical connection schematic. No real substation assignment.
    hub = config['scenario_hub_enu_m'][:2]
    mesh_layer('assumed_electric_links', ribbons([LineString([hub, p[:2]]) for p in positions]+[LineString([hub, (charger_point.x, charger_point.y)])], [70,200,255,255], z=14, width=3, dashed=True))
    ids = [x['name']+' | hypothetical equipment' for x in selected]
    json_layer('assumed_roof_pv_kw', 'scalar_field', dict(positions=positions, ids=ids, values=result['pv'].tolist()), 'Assumed PV output on recorded clear-sky rooftop field', 'kW', True)
    json_layer('assumed_ev_kw', 'scalar_field', dict(positions=[display_position(charger_point)], ids=['OSM '+charger['id']+' | assumed charging demand'], values=result['ev'][:,None].tolist()), 'Assumed EV demand, not measured charging', 'kW', True)
    json_layer('electric_balance', 'time_series', dict(labels=['Grid net','PV','Demand'], values=np.stack([result['grid'],result['pv'].sum(axis=1),result['demand']],axis=1).tolist()), 'Hypothetical electricity balance', 'kW', True)
    json_layer('heat_balance', 'time_series', dict(labels=['Heat (th)','HP (el)','Ambient (th)'], values=np.stack([result['heat'].sum(axis=1),result['hp'].sum(axis=1),result['ambient_heat'].sum(axis=1)],axis=1).tolist()), 'Assumed heat pumps; not district network supply', 'kW', True)
    electric_residual = result['grid']+result['pv'].sum(axis=1)-result['demand']
    thermal_residual = result['heat']-result['hp']-result['ambient_heat']
    report = dict(public_features=counts, osm_features=dict(categories), buildings=[s['name'] for s in selected], samples=len(times), duration_s=times[-1]-times[0], electric_balance_max_error_kw=float(abs(electric_residual).max()), heat_balance_max_error_kw=float(abs(thermal_residual).max()), pv_kw_range=[float(result['pv'].sum(axis=1).min()),float(result['pv'].sum(axis=1).max())], net_grid_kw_range=[float(result['grid'].min()),float(result['grid'].max())], hypotheses=config, limitations=['Source snapshot mixes acquisition dates; no current operational guarantee.', 'Scene rectangle includes neighbouring boroughs; not a Tower Hamlets administrative inventory.', 'GLA existing and proposed layers remain separate; schematic line width/elevation are not pipe dimensions.', 'No inference that plotted buildings connect to nearby mapped heat or electrical networks.', 'No real feeder topology, measured load, line rating, voltage, losses or thermal hydraulics.', 'Solar time window is the original 11 frames, 12:00–12:10 UTC on 2026-06-21; no daily/annual extrapolation.', 'PV and heat pump equipment, demand and COP are hypothetical; no temperature-dependent PV model.'])
    write(trial/'report.json', report); write(trial/'inventory.json', inventory)
    # Self-contained source and acquisition snapshots, without unrelated local changes.
    with zipfile.ZipFile(trial/'source_snapshot.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for p in sorted((storage.root/'src/energy').glob('*')):
            if p.is_file(): archive.write(p, str(p.relative_to(storage.root)))
        for name in ('src/common/storage.py','src/common/export.py','src/common/contract.py','schemas/run-manifest-v1.schema.json'):
            archive.write(storage.root/name, name)
    artifacts=[]
    layer_assets = {l['asset'] for l in layers}
    for i, p in enumerate(sorted(trial.rglob('*'))):
        if p.is_file() and str(p.relative_to(trial)) not in layer_assets:
            artifacts.append(dict(id='source_snapshot' if p.name=='source_snapshot.zip' else f'artifact_{i}', asset=str(p.relative_to(trial)), sha256=digest(p), media_type='application/octet-stream'))
    epoch = json.loads((trial/'solar/configuration.json').read_text())['epoch_utc']
    manifest = dict(schema_version='1.1.0', scene_id=scene_id, simulation='energy', run_id=run_id, status='complete', created_at=datetime.now(timezone.utc).isoformat(), provenance=dict(code_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=storage.root,text=True).strip(), dirty=True, parameters={**config, 'limitations':report['limitations']}, inputs=[dict(id='public_source_checksums',sha256=digest(source/'checksums.json')),dict(id='source_solar_manifest',sha256=digest(solar/'manifest.json')),dict(id='source_buildings',sha256=digest(geometry))]), spatial=spatial, time=dict(unit='s',samples=times,epoch=epoch), layers=layers, artifacts=artifacts)
    write(trial/'manifest.json', manifest); validate(trial/'manifest.json')
    return trial, report


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--config',type=Path,required=True); parser.add_argument('--source',type=Path); parser.add_argument('--retain',action='store_true'); args=parser.parse_args()
    config=json.loads(args.config.read_text()); storage=Storage.load(); scene=config['scene_id']
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:6]
    source=args.source
    if source is None:
        source=storage.assets(scene,'input')/('energy_open_'+stamp)
        spatial=json.loads((storage.metadata(scene)/'project.json').read_text())['spatial']
        acquire(storage,config,spatial,source)
    run_id='energy_pilot_'+stamp; trial,report=build(storage,config,source,run_id)
    destination=trial
    if args.retain:
        from common.runs import promote
        destination=promote(storage,trial)
        view_id=run_id.lower()
        m=json.loads((trial/'manifest.json').read_text()); base=config['geometry_run']
        view=dict(schema_version='1.1.0',scene_id=scene,title='Canary Wharf · public energy context + hypothetical 10-minute test',time_alignment='absolute',runs=[run_id,base],layers=[dict(run_id=base,layer_id='geometry',visible=True)]+[dict(run_id=run_id,layer_id=l['id'],visible=l['id'] not in ('proposed_heat_lines','proposed_heat_centres','heat_planning_sites','osm_generator','osm_plant','assumed_electric_links')) for l in m['layers']],camera=dict(position=[3700,-4700,4900],target=[0,0,30]))
        write(storage.metadata(scene)/'views'/f'{view_id}.json',view)
        from common.catalog import view as check_view
        from common.runs import refresh_catalog
        check_view(storage,scene,view_id)
        refresh_catalog(storage)
        print('VIEW',view_id)
    print('SOURCE',source);print('RESULT',destination);print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
