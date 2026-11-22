"""Read native signal states and mapped crossing markings for offline review."""
import math
import xml.etree.ElementTree as ET


def signal_facilities(network, signals_file, begin, end, nearby):
    lanes={l.get('id'):l for e in network.findall('edge') for l in e.findall('lane')}
    heads=[];seen=set()
    for c in network.findall('connection'):
        if c.get('tl') is None:continue
        lane_id=c.get('from')+'_'+c.get('fromLane');lane=lanes[lane_id]
        points=[list(map(float,p.split(','))) for p in lane.get('shape').split()]
        if len(points)<2 or not nearby(*points[-1][:2]):continue
        key=(c.get('tl'),lane_id,int(c.get('linkIndex')))
        if key in seen:continue
        seen.add(key);a,b=points[-2:]
        heads.append({'tls':key[0],'lane':lane_id,'link_index':key[2],
            'position':b[:2]+[b[2] if len(b)>2 else 0],
            'heading':math.atan2(b[1]-a[1],b[0]-a[0]),
            'lane_width':float(lane.get('width','3.2')),'direction':c.get('dir')})
    ids={h['tls'] for h in heads};timeline={i:[] for i in ids};previous={}
    if not signals_file.exists():return {'heads':heads,'timeline':{},'recorded_interval':None}
    for _,s in ET.iterparse(signals_file,events=['end']):
        if s.tag!='tlsState':continue
        identity=s.get('id');time=float(s.get('time'))
        if identity in ids and time<end:
            event={'time':time,'state':s.get('state'),'phase':int(s.get('phase')),'program':s.get('programID')}
            if time<=begin:previous[identity]=event
            else:timeline[identity].append(event)
        s.clear()
    for identity in ids:
        if identity not in previous:raise ValueError(f'Missing initial recorded TLS state: {identity}')
        timeline[identity].insert(0,previous[identity])
        times=[v['time'] for v in timeline[identity]]
        if times!=sorted(times) or len(times)!=len(set(times)):raise ValueError('Non-monotone signal recording')
    for h in heads:
        if h['link_index']<0 or any(h['link_index']>=len(v['state']) for v in timeline[h['tls']]):raise ValueError('Signal link index outside recorded state')
    return {'heads':heads,'timeline':timeline,'recorded_interval':[begin,end]}


def crossing_facilities(osm_file, network, lanes, junctions, nearby):
    """Use explicit OSM crossing-way markings; clip paint to the native road surface.

    Stripe/dot sizes and height matching are presentation assumptions, not survey.
    Unknown/unmarked crossings deliberately receive no invented zebra pattern.
    """
    import pyproj
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union
    projection=pyproj.Proj(network.find('location').get('projParameter'))
    ox,oy=map(float,network.find('location').get('netOffset','0,0').split(','))
    osm=ET.parse(osm_file).getroot();nodes={n.get('id'):n for n in osm.findall('node')}
    lines=[];surfaces=[]
    for l in lanes:
        if len(l['shape'])<2:continue
        line=LineString([p[:2] for p in l['shape']]);lines.append((line,l['shape']))
        if not l['internal']:surfaces.append(line.buffer(l['width']/2,cap_style=2))
    for j in junctions:
        if len(j['shape'])>=3:
            poly=Polygon([p[:2] for p in j['shape']])
            if poly.is_valid:surfaces.append(poly)
    if not surfaces or not lines:return []
    road=unary_union(surfaces)
    def height(x,y):
        from shapely.geometry import Point
        point=Point(x,y);line,points=min(lines,key=lambda pair:pair[0].distance(point))
        distance=line.project(point);travel=0
        for a,b in zip(points,points[1:]):
            length=math.dist(a[:2],b[:2])
            if length and travel+length>=distance-1e-8:
                u=max(0,min(1,(distance-travel)/length));return (a[2] if len(a)>2 else 0)*(1-u)+(b[2] if len(b)>2 else 0)*u
            travel+=length
        return points[-1][2] if len(points[-1])>2 else 0
    features=[]
    for way in osm.findall('way'):
        tags={t.get('k'):t.get('v') for t in way.findall('tag')}
        if tags.get('footway')!='crossing':continue
        marking=tags.get('crossing:markings','')
        kind='zebra' if 'zebra' in marking else 'dots' if 'dots' in marking else 'lines' if marking=='lines' else None
        if kind is None:continue
        points=[]
        for ref in way.findall('nd'):
            n=nodes.get(ref.get('ref'))
            if n is None:points=[];break
            x,y=projection(float(n.get('lon')),float(n.get('lat')));points.append([x+ox,y+oy])
        if len(points)<2 or not any(nearby(*p) for p in points):continue
        clipped=LineString(points).intersection(road)
        parts=[clipped] if clipped.geom_type=='LineString' else list(getattr(clipped,'geoms',[]))
        for part in parts:
            if part.geom_type!='LineString' or part.length<.5:continue
            features.append({'osm_way_id':way.get('id'),'kind':kind,'source_marking':marking,
                'line':[[x,y,height(x,y)] for x,y in part.coords]})
    return features
