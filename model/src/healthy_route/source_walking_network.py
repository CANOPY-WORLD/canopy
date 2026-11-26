"""Prepare a conservative walking graph from pinned Overture junction evidence.

This is an offline input adapter, not a solver or a Viewer-side repair. Display
lines alone cannot establish access or connectivity. Unresolved paths stay out.
"""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from shapely import from_wkb
from shapely.geometry import LineString, Point, box
from shapely.ops import substring
from shapely.strtree import STRtree

from .build_network import visible_parts
from .city_alignment import Terrain

WALKING = {'footway', 'path', 'pedestrian', 'steps', 'living_street'}
EXPLICIT_FOOT = {'cycleway', 'bridleway', 'track'}
ROUNDING_M = .081  # 0.1 m presentation rounding, including clipped endpoints.
RELEASE = '2026-10-21.0'


def access_reason(row):
    """Accept only unconditionally usable, bidirectional research walking paths.

    Conditional/directional rules are excluded, not evaluated against an invented
    observation date or permission. Conservative whole-segment exclusion also
    applies to scoped restrictions; no partial permission is silently expanded.
    """
    cls = row['class']
    if cls not in WALKING | EXPLICIT_FOOT:
        return 'unsupported_road_class'
    allowed = False
    for rule in row.get('access_restrictions') or []:
        when = rule.get('when') or {}
        modes = when.get('mode')
        if modes and 'foot' not in modes:
            continue
        if rule.get('access_type') not in {'allowed', 'designated'}:
            return 'pedestrian_denial_or_unknown_access'
        if any(when.get(k) for k in ('during', 'heading', 'using', 'recognized', 'vehicle')):
            return 'conditional_pedestrian_access'
        if rule.get('between') not in (None, [0, 1], [0., 1.]):
            return 'partial_pedestrian_access'
        if modes and 'foot' in modes:
            allowed = True
    if cls in EXPLICIT_FOOT and not allowed:
        return 'no_explicit_pedestrian_permission'
    for rule in row.get('prohibited_transitions') or []:
        modes = (rule.get('when') or {}).get('mode')
        if not modes or 'foot' in modes:
            return 'unresolved_pedestrian_turn_restriction'
    flags = {flag for rule in row.get('road_flags') or [] for flag in rule.get('values', [])}
    if flags & {'is_tunnel', 'is_indoor', 'is_under_construction', 'is_disused'}:
        return 'unsupported_indoor_tunnel_or_inactive_path'
    levels = {rule['value'] for rule in row.get('level_rules') or []}
    if len(levels) > 1 or any(rule.get('between') for rule in row.get('level_rules') or []):
        return 'unresolved_varying_level'
    if levels and min(levels) < 0:
        return 'unresolved_underground_height'
    return None


def project(points, origin):
    xy = np.asarray(points, dtype=float)[:, :2] - [origin['longitude'], origin['latitude']]
    scale = math.pi / 180 * 6378137
    return xy * [scale * math.cos(math.radians(origin['latitude'])), scale]


def components_for(edges):
    adj = defaultdict(set)
    for e in edges:
        adj[e['u']].add(e['v']); adj[e['v']].add(e['u'])
    remaining, groups = set(adj), []
    while remaining:
        stack = [min(remaining)]; remaining.remove(stack[0]); group = []
        while stack:
            u = stack.pop(); group.append(u)
            for v in adj[u]:
                if v in remaining:
                    remaining.remove(v); stack.append(v)
        groups.append(sorted(group))
    return sorted(groups, key=lambda g: (-len(g), g[0]))


class SceneHeights:
    def __init__(self, terrain, native):
        self.terrain = Terrain(terrain)
        self.decks = []
        for lane in native['lanes']:
            if lane['edge'] is None:
                continue
            edge = native['edges'][lane['edge']]
            if 'bridge' not in edge.get('structure', []):
                continue
            xyz = np.asarray(lane['shape']); line = LineString(xyz[:, :2])
            if line.length:
                ds = np.r_[0, np.cumsum(np.linalg.norm(np.diff(xyz[:, :2], axis=0), axis=1))]
                self.decks.append((line, xyz, ds, edge.get('level', 1)))
        self.index = STRtree([d[0] for d in self.decks])

    def sample(self, xy, row):
        elevated = row.get('bridge') or row.get('level', 0) > 0
        if not elevated:
            return np.array([self.terrain.sample(*p) for p in xy])
        values = []
        for p in xy:
            point = Point(p); choices = []
            for j in self.index.query(point.buffer(12)):
                line, xyz, ds, level = self.decks[j]
                distance = line.distance(point)
                if level == (row.get('level') or 1) and distance <= 12:
                    choices.append((distance, int(j)))
            if not choices:
                return None
            _, j = min(choices); line, xyz, ds, _ = self.decks[j]
            values.append(float(np.interp(line.project(point), ds, xyz[:, 2])))
        return np.asarray(values)


def build_graph(scene, segments, connectors, height_at):
    """Inputs use scene XY metres; each segment has a source LineString.

    Physical joins require the same connector ID, <=8.1 cm presentation residual
    and <=10 cm height agreement. Interior cuts are namespaced by source row/run:
    coincident roads without a shared connector can never acquire a shared node.
    """
    source_lines = [r['line'] for r in segments]
    tree = STRtree(source_lines); bounds = box(-scene['half_m'], -scene['half_m'], scene['half_m'], scene['half_m'])
    nodes, edges, audit, connector_nodes = {}, [], [], defaultdict(list)
    counts = Counter(); matching_residuals = []; connector_residuals = []
    for row_id, display in enumerate(scene['roads']):
        if display['cls'] not in WALKING | EXPLICIT_FOOT or len(display['line']) < 2:
            continue
        line = LineString(display['line']); choices = []
        for j in tree.query(line.buffer(ROUNDING_M)):
            raw = segments[j]
            if raw['class'] != display['cls']:
                continue
            distance = line.hausdorff_distance(source_lines[j].intersection(bounds))
            if distance <= ROUNDING_M:
                choices.append((distance, int(j)))
        record = {'scene_row': row_id, 'class': display['cls'], 'name': display.get('name', '')}
        if len(choices) != 1:
            reason = 'ambiguous_source_match' if choices else 'unmatched_source_geometry'
            counts[reason] += 1; audit.append(dict(record, status=reason)); continue
        residual, j = choices[0]; raw = segments[j]
        record.update(segment_id=raw['id'], version=raw['version'], source_match_residual_m=residual)
        reason = access_reason(raw)
        if reason:
            counts[reason] += 1; audit.append(dict(record, status=reason)); continue
        raw_flags = {f for r in raw.get('road_flags') or [] for f in r.get('values', [])}
        source_level = next(iter(raw.get('level_rules') or []), {}).get('value', 0)
        if source_level != display.get('level', 0) or ('is_bridge' in raw_flags) != bool(display.get('bridge')):
            counts['source_display_grade_mismatch'] += 1
            audit.append(dict(record, status='source_display_grade_mismatch')); continue
        refs = []
        for ref in raw['connectors']:
            cid = ref['connector_id']; xy = connectors.get(cid)
            if xy is None:
                continue  # Out-of-bbox endpoints cannot establish a city join.
            if raw['line'].distance(Point(xy)) > 1e-5:
                raise ValueError('Connector is not on its declared source segment: ' + cid)
            canonical = np.round(xy, 1).tolist()
            display_vertices = np.asarray(display['line'])
            errors = np.linalg.norm(display_vertices-canonical, axis=1)
            nearest = int(np.argmin(errors))
            if errors[nearest] <= ROUNDING_M:
                refs.append((cid, canonical, tuple(display_vertices[nearest])))
        before = len(edges)
        for run_id, part in enumerate(visible_parts(display)):
            if part.length < 1e-8:
                continue
            # Regular cuts make long roads selectable without inventing junctions.
            cuts = {0.: None, part.length: None}
            for k in range(1, math.ceil(part.length / 30)):
                cuts[k * part.length / math.ceil(part.length / 30)] = None
            ambiguous = False
            visible_vertices = set(part.coords)
            for cid, xy, mapped_vertex in refs:
                if mapped_vertex not in visible_vertices:
                    continue  # A nearby connector on a hidden segment is absent.
                distance = part.distance(Point(xy))
                if distance > ROUNDING_M:
                    continue
                q = part.project(Point(xy))
                # Avoid duplicate cuts at a rounded endpoint.
                if q < 1e-7: q = 0.
                if part.length-q < 1e-7: q = part.length
                if cuts.get(q) and cuts[q][0] != cid:
                    ambiguous = True
                    break
                cuts[q] = (cid, xy); connector_residuals.append(distance)
            if ambiguous:
                counts['unresolved_rounded_connector_collisions'] += 1
                continue
            ordered = sorted(cuts)
            for section, (a, b) in enumerate(zip(ordered, ordered[1:])):
                if b-a < 1e-8:
                    continue
                pts = np.array(substring(part, a, b).coords)
                for index, q in [(0, a), (-1, b)]:
                    if cuts[q]: pts[index] = cuts[q][1]
                if np.linalg.norm(np.diff(pts, axis=0), axis=1).sum() <= 1e-8:
                    continue
                heights = height_at(pts, display)
                if heights is None:
                    counts['unresolved_elevated_sections'] += 1; continue
                xyz = np.c_[pts, heights].tolist(); ends = []
                for index, q in [(0, a), (-1, b)]:
                    ref = cuts[q]
                    if ref:
                        cid = ref[0]; compatible = [n for n in connector_nodes[cid] if abs(nodes[n][2]-xyz[index][2]) <= .1]
                        if compatible:
                            nid = compatible[0]; xyz[index] = nodes[nid][:3]
                        else:
                            nid = f'junction:{cid}:{len(connector_nodes[cid])}'
                            connector_nodes[cid].append(nid)
                            nodes[nid] = xyz[index] + [0.]
                    else:
                        nid = f'path:{row_id}:{run_id}:{q:.9f}'
                        nodes[nid] = xyz[index] + [0.]
                    ends.append(nid)
                distance = np.r_[0, np.cumsum(np.linalg.norm(np.diff(np.array(xyz)[:, :2], axis=0), axis=1))].tolist()
                # Subdivision also prevents loss of a closed loop or parallel route
                # when the downstream alignment reader keys edges by endpoints.
                via = f'via:{row_id}:{run_id}:{section}'
                middle = distance[-1]/2
                mid = [float(np.interp(middle, distance, np.array(xyz)[:, k])) for k in range(3)]
                cut = int(np.searchsorted(distance, middle, side='right'))
                nodes[via] = mid + [0.]
                for u, v, points in [(ends[0], via, xyz[:cut]+[mid]), (via, ends[1], [mid]+xyz[cut:])]:
                    ds = np.r_[0, np.cumsum(np.linalg.norm(np.diff(np.array(points)[:, :2], axis=0), axis=1))].tolist()
                    edges.append(dict(u=u, v=v, points=points, distance=ds, crossing_id=None,
                        level=[display.get('level', 0), bool(display.get('bridge')), False],
                        name=display.get('name') or 'Source-mapped walking path', source_segment=raw['id'],
                        source_class=raw['class'], source_row=row_id, source='Pinned Overture shared-connector topology'))
        if len(edges) > before:
            counts['accepted_'+raw['class']] += 1; matching_residuals.append(residual)
            audit.append(dict(record, status='retained', edges=len(edges)-before))
        else:
            counts['no_visible_supported_section'] += 1
            audit.append(dict(record, status='no_visible_supported_section'))
    components = components_for(edges); used = {n for e in edges for n in (e['u'], e['v'])}
    nodes = {n: p for n, p in nodes.items() if n in used}
    counts.update(nodes=len(nodes), undirected_links=len(edges), components=len(components),
                  largest_component_nodes=len(components[0]) if components else 0,
                  vertically_separated_connectors=sum(len(v)>1 for v in connector_nodes.values()), environmental_exclusions=0)
    report = dict(summary=dict(counts), rows=audit, max_source_match_residual_m=max(matching_residuals, default=0),
                  max_connector_reconciliation_m=max(connector_residuals, default=0))
    network = dict(nodes=nodes, edges=edges, crossings=[], components=components, summary=dict(counts),
        provenance=dict(topology='Only shared pinned Overture connector IDs join paths; geometric intersections and near endpoints alone never join. Hidden display segments remain absent. Private, conditional, indoor, underground and unresolved access/height paths are excluded.',
                        signals='No synthetic pedestrian program, vehicle-signal state or clearance is used.',
                        coordinate_conversion='Local equirectangular XY: R=6378137 m, cos(origin latitude) longitude scale; source connectors rounded to presentation 0.1 m, reconciled within 0.081 m; terrain/deck height policy retained.',
                        access='Pedestrian classes and living_street have an explicit research class-default assumption; cycleway/bridleway/track require unconditional foot permission. Not surveyed access or navigation advice.'))
    return network, report


def build_pinned(root, segments_path, connectors_path):
    """Read-only pinned-source preparation; pyarrow is only needed at this stage."""
    import gzip
    import pyarrow.parquet as pq
    root = Path(root); context = root/'scenes/imperial_corridor_8km/context'
    scene = json.loads((context/'vector_landscape/source/scene-meta.json').read_bytes())
    if scene['source']['overture_release'] != RELEASE:
        raise ValueError('Review source adapter for the changed city Overture release')
    downloads = {}
    for path, kind in [(Path(segments_path), 'segment'), (Path(connectors_path), 'connector')]:
        state = json.loads(path.with_suffix(path.suffix+'.state').read_bytes())
        if state['last_release'] != RELEASE or state['theme'] != 'transportation' or state['type'] != kind:
            raise ValueError('Wrong pinned transportation download: '+kind)
        downloads[kind] = {k:state[k] for k in ['last_release','last_run','theme','type','bbox','backend']}
    if downloads['segment']['bbox'] != downloads['connector']['bbox']:
        raise ValueError('Segment and connector download coverage differs')
    raw = pq.read_table(segments_path).to_pylist(); segments = []
    for row in raw:
        if row['subtype'] != 'road' or row['class'] not in WALKING | EXPLICIT_FOOT:
            continue
        row['line'] = LineString(project(from_wkb(row.pop('geometry')).coords, scene['origin']))
        segments.append(row)
    connectors = {r['id']: project(from_wkb(r['geometry']).coords, scene['origin'])[0].tolist()
                  for r in pq.read_table(connectors_path).to_pylist()}
    terrain = json.loads((context/'terrain/terrain.json').read_bytes())['terrain']
    native = json.loads(gzip.decompress((context/'terrain/road-network.json.gz').read_bytes()))
    network, audit = build_graph(scene, segments, connectors, SceneHeights(terrain, native).sample)
    inputs = dict(release=RELEASE, origin=scene['origin'], downloads=downloads,
                  source_url=f's3://overturemaps-us-west-2/release/{RELEASE}/theme=transportation/',
                  license='Overture ODbL-1.0 for OSM-derived records; individual sources retained in GeoParquet',
                  files={Path(p).name: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in [segments_path, connectors_path]})
    network['provenance']['source_inputs'] = inputs; audit['source_inputs'] = inputs
    return network, audit
