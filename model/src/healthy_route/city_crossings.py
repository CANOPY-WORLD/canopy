"""Health-only crossing gates from pinned walking tags and current SUMO samples.

No new road connections are made. Pedestrian phases are assumptions, distinct
from the recorded vehicle signals. The short traffic clip is explicitly replayed.
"""
import copy
import hashlib
import math
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import shapely
from shapely.geometry import LineString, Point

from canopy._io import read, digest
from .source_walking_network import project
from .walk_signal_schedule import WalkProgram, WalkGate
from .traffic_gaps import ClearWindows, TrafficGapGate, intervals, mark_sweeps

TRAFFIC = 'scenes/imperial_corridor_8km/context/traffic-native.json'
SOURCE = 'transportation-source/connectivity-segments-2026-10-21.0.parquet'


def annotate_crossings(network, sources, origin):
    """Split existing edges at tagged boundaries; preserve the original topology."""
    out=copy.deepcopy(network);out['edges']=[];crossings={};splits=0
    for edge_index,edge in enumerate(network['edges']):
        source=sources.get(edge.get('source_segment'))
        if not source or edge.get('level',[0,False])[0]!=0 or edge.get('level',[0,False])[1]:
            out['edges'].append(copy.deepcopy(edge));continue
        rules=source.get('subclass_rules') or [{'value':source.get('subclass'),'between':None}]
        rules=[r for r in rules if r.get('value')=='crosswalk']
        if not rules:
            out['edges'].append(copy.deepcopy(edge));continue
        raw=project(list(shapely.from_wkb(source['geometry']).coords),origin)
        line=LineString(raw);xyz=np.asarray(edge['points']);path=LineString(xyz[:,:2]);length=path.length
        if line.length<=0 or length<=0:raise ValueError('Invalid crossing source geometry')
        ds=np.r_[0,np.cumsum(np.linalg.norm(np.diff(xyz[:,:2],axis=0),axis=1))]
        cuts={0.,length};ranges=[]
        for index,rule in enumerate(rules):
            a,b=rule.get('between') or [0.,1.]
            if not 0<=a<b<=1:raise ValueError('Invalid crosswalk source range')
            key='crosswalk:'+source['id']+':'+str(index)
            ranges.append((a*line.length,b*line.length,key))
            for fraction in [a,b]:
                point=line.interpolate(fraction,normalized=True)
                d=path.project(point)
                if point.distance(path)<.1 and 1e-6<d<length-1e-6:cuts.add(d)
        cuts=sorted(cuts);node_ids=[edge['u']]
        for cut_index,d in enumerate(cuts[1:-1]):
            node='crossing-cut:'+str(edge_index)+':'+str(cut_index)
            out['nodes'][node]=[float(np.interp(d,ds,xyz[:,k])) for k in range(3)]+[0.]
            node_ids.append(node);splits+=1
        node_ids.append(edge['v'])
        for i,(a,b) in enumerate(zip(cuts,cuts[1:])):
            middle=path.interpolate((a+b)/2);source_d=line.project(middle)
            if middle.distance(line)>.1:raise ValueError('Crosswalk no longer aligns with pinned source')
            key=next((key for lo,hi,key in ranges if lo-1e-7<=source_d<=hi+1e-7),None)
            positions=[a]+[float(d) for d in ds if a<d<b]+[b]
            points=[[float(np.interp(d,ds,xyz[:,k])) for k in range(3)] for d in positions]
            item=copy.deepcopy(edge);item.update(u=node_ids[i],v=node_ids[i+1],points=points,
                distance=[d-a for d in positions],crossing_id=key)
            out['edges'].append(item)
            if key:
                entry=crossings.setdefault(key,dict(id=key,source_segment=source['id'],
                    source_records=source.get('sources') or [],segments=[],length_m=0.))
                entry['segments'].append(points);entry['length_m']+=b-a
    out['crossings']=list(crossings.values())
    out['crossing_mapping']=dict(source='Pinned Overture crosswalk subclass/ranges',
        crossings=len(crossings),split_nodes=splits,new_connections=0,
        limits='Crosswalk tags do not establish that physical pedestrian lights exist. Ground-level source-mapped paths only; untagged crossings are not invented.')
    return out


def current_traffic_windows(traffic, crossings, checkpoint=lambda:None):
    """Use front-bumper references, sparse identities and nonuniform timestamps."""
    frames=traffic['frames'];times=np.array([f['time'] for f in frames],float)
    start,stop=traffic['signals']['recorded_interval'];period=stop-start
    if len(times)<2 or not np.isfinite(times).all() or np.any(np.diff(times)<=0) or times[0]!=start or times[-1]>=stop:
        raise ValueError('Invalid declared current traffic clock')
    if traffic['position_reference']!='front_bumper' or traffic['coordinate_frame']!='ENU':
        raise ValueError('Unsupported current traffic reference')
    geometries=[shapely.union_all([LineString(np.array(p)[:,:2]) for p in c['segments']]) for c in crossings]
    tree=shapely.STRtree(geometries)
    lane_geometries=[LineString([p[:2] for p in l['shape']]) for l in traffic['lanes'] if max(abs(p[2]) if len(p)>2 else 0 for p in l['shape'])<2]
    lane_tree=shapely.STRtree(lane_geometries)
    # Being near the clip centre alone does not establish sampled road coverage.
    coverage=[]
    for c,geometry in zip(crossings,geometries):
        hits=lane_tree.query(geometry,predicate='intersects')
        coverage.append(bool(len(hits)) and all(math.dist(p[:2],traffic['center'])<traffic['radius']-10 for segment in c['segments'] for p in segment))
    mask=np.zeros((len(crossings),len(frames)),dtype=bool)
    def bodies(frame):
        result={}
        for row in frame['vehicles']:
            identity,kind,x,y,z,heading,_,_=row
            dims=traffic['vehicle_types'][kind];length,width=dims['length'],dims['width']
            if not np.isfinite([x,y,z,heading,length,width]).all():raise ValueError('Missing vehicle pose/dimensions')
            # Explicit assumed ground band, not a validated traffic datum transform.
            if abs(z)>2:continue
            result[identity]=(np.array([x-length/2*math.cos(heading),y-length/2*math.sin(heading)]),math.hypot(length/2,width/2)+1.4)
        return result
    if crossings:
        current=bodies(frames[0])
        for k,frame in enumerate(frames):
            checkpoint();following=bodies(frames[k+1]) if k+1<len(frames) else current
            # Never sweep a missing vehicle identity or the last-to-first seam.
            ids=list(current);a=np.array([current[i][0] for i in ids]);b=np.array([following.get(i,current[i])[0] for i in ids]);r=np.array([current[i][1] for i in ids])
            if ids:mask[mark_sweeps(tree,a,b,r),k]=True
            born=[i for i in following if i not in current]
            if born:
                p=np.array([following[i][0] for i in born]);mask[mark_sweeps(tree,p,p,np.array([following[i][1] for i in born])),k]=True
            current=following
    ends=np.r_[times[1:],stop];windows={}
    for c,covered,occupied in zip(crossings,coverage,mask):
        if not covered:continue
        # One-second temporal padding, including across the explicit replay seam.
        spans=[]
        for a,b in zip(times[occupied]-start,ends[occupied]-start):
            for cycle in [-1,0,1]:
                lo=max(0.,a-1+cycle*period);hi=min(period,b+1+cycle*period)
                if lo<hi:spans.append((lo,hi))
        merged=[]
        for lo,hi in sorted(spans):
            if merged and lo<=merged[-1][1]+1e-8:merged[-1][1]=max(merged[-1][1],hi)
            else:merged.append([lo,hi])
        windows[c['id']]=ClearWindows(merged,period)
    return windows,dict(source_interval_s=[start,stop],period_s=period,
        mapping=f'source time = {start:g} + (Health seconds modulo {period:g}); repeated short simulation clip, not a common observation clock',
        covered_crossings=len(windows),spatial_margin_m=1.4,temporal_buffer_s=1,
        limits='Retained simulated vehicles only; XY bounding-disc estimate. Native |Z|<2 m is an assumed ground band, not validated vertical registration. No sweep through absent IDs or replay seam. Unknown outside lane/clip coverage; no real-world clearance guarantee.')


def prepare_crossings(city,network,checkpoint=lambda:None):
    city=Path(city);source_path=city/SOURCE
    rows=pq.read_table(source_path,columns=['id','subclass','subclass_rules','sources','geometry']).to_pylist()
    origin=read(city/'scenes/imperial_corridor_8km/context/vector_landscape/source/scene-meta.json')['origin']
    annotated=annotate_crossings(network,{r['id']:r for r in rows},origin)
    traffic=read(city/TRAFFIC)
    return annotated,traffic,dict(source_sha256=digest(source_path),traffic_sha256=digest(city/TRAFFIC),
        native_provenance=traffic['provenance'],mapping=annotated['crossing_mapping'])


def apply_crossing_waits(route,network,traffic,departure,deadline,policy,checkpoint=lambda:None):
    by_id={c['id']:c for c in network['crossings']}
    chosen=[by_id[c] for c in dict.fromkeys(route['crossing_ids'])]
    windows,clock=current_traffic_windows(traffic,chosen,checkpoint)
    programs={};gates={}
    for c in chosen:
        # Full source crossing, not a subdivision, sets an adequate assumed phase.
        clearance=policy['crossing_clearance_s'];green=max(policy['crossing_green_s'],c['length_m']/policy['speed_m_s']+2-clearance)
        red=policy['crossing_red_s'];period=red+green+clearance
        offset=int(hashlib.sha256(c['id'].encode()).hexdigest()[:8],16)%int(math.ceil(period))
        p=WalkProgram(red,green,clearance,float(offset));signal=WalkGate(c['id'],p,2.)
        programs[c['id']]=dict(red_s=red,green_s=green,clearance_s=clearance,origin_s=float(offset))
        gates[c['id']]=TrafficGapGate(signal,windows[c['id']]) if c['id'] in windows else signal
    edges={tuple((e['u'],e['v'])):e for e in network['edges']}
    timeline=[];elapsed=0.;waits=[];displays={};i=0
    original=route['timeline'];keys=route['edge_keys']
    while i<len(original):
        checkpoint();key=tuple(keys[i]);edge=edges.get(key) or edges[tuple(reversed(key))];crossing=edge.get('crossing_id');j=i+1
        if crossing:
            while j<len(original):
                key2=tuple(keys[j]);e2=edges.get(key2) or edges[tuple(reversed(key2))]
                if e2.get('crossing_id')!=crossing:break
                j+=1
            duration=sum(e['end']-e['start'] for e in original[i:j]);gate=gates[crossing]
            entry=gate.next_entry(departure+elapsed,duration,deadline)
            if entry is None:raise ValueError('No crossing release within Health coverage for '+crossing+'; current traffic clip may not contain a sufficient gap')
            extra=entry-departure-elapsed
            details=gate.wait_details(departure+elapsed,duration,deadline,entry) if isinstance(gate,TrafficGapGate) else dict(wait_reason='modelled_pedestrian_light',signal_only_wait_s=extra,traffic_extra_wait_s=0.)
            if extra>1e-7:
                event=dict(kind='Waiting',start=elapsed,end=elapsed+extra,points=[original[i]['points'][0]],crossing_id=crossing,**details)
                timeline.append(event);waits.append(event);elapsed+=extra
            displays[crossing]=dict(id=crossing,program=programs[crossing],
                heads=[original[i]['points'][0],original[j-1]['points'][-1]],crossing_s=duration,
                traffic_covered=crossing in windows,
                traffic_gap=dict(period_s=windows[crossing].period,blocked_intervals_s=windows[crossing].blocked,crossing_s=duration,clearance_s=2.) if crossing in windows else None)
        for e in original[i:j]:
            duration=e['end']-e['start'];timeline.append(dict(e,start=elapsed,end=elapsed+duration,
                kind='Crossing' if crossing else 'Walking',crossing_id=crossing));elapsed+=duration
        i=j
    if departure+elapsed>deadline+1e-7:raise ValueError('Crossing waits exceed available Health coverage')
    result=copy.deepcopy(route);result.update(timeline=timeline,duration_s=elapsed,
        walking_duration_s=route['duration_s'],wait_s=sum(w['end']-w['start'] for w in waits),waits=waits,
        crossing_signals=list(displays.values()),traffic_clock=clock)
    return result
