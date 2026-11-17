"""OLSJ four-body architectural study. Mapped plans, estimated elevations.
No scene mutation outside owned collection; no IO or downloads.
"""
import math

def build(ctx, feature):
    parts=feature['geometry']; H=float(feature['height_m']); levels=max(1,round(H/3)); cfg=feature.get('detail_parameters',{})
    main='00a6586d' in feature['id']; slope=.018 if feature.get('source_properties',{}).get('roof_shape')=='skillion' else 0
    mats={k:ctx.material('OLSJ study '+k,c,r) for k,c,r in [('brick',(.46,.27,.16),.85),('trim',(.64,.55,.40),.75),('glass',(.07,.17,.20),.2),('metal',(.16,.19,.19),.4),('roof',(.27,.31,.30),.85),('entry',(.65,.34,.13),.65)]}
    meshes={k:ctx.mesh(k) for k in ['mapped_slabs','wall_openings','window_glass','frames_sills','roof_skin','roof_seams','roof_edge_flashings','rainwater_pipes','entrance_canopy','door_leaves']}
    openings=[];entrances=[]; interfaces=[]
    ymin=min(p[1] for part in parts for p in part['outer'])
    def top(x,y):return H+slope*(y-ymin)
    for part in parts:
        ring=[tuple(p) for p in part['outer']]
        if ring[0]==ring[-1]:ring.pop()
        if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]+ring[:1]))<0:ring.reverse()
        tris=part['triangles']
        if tris and isinstance(tris[0][0],int):tris=[[part['vertices_xy'][i] for i in t] for t in tris]
        for tri in tris:
            meshes['mapped_slabs'].face([(*p,0) for p in reversed(tri)],mats['trim'])
            meshes['roof_skin'].face([(*p,top(*p)) for p in tri],mats['roof'])
        # Estimated standing seams clipped to exact concave roof footprint.
        x=min(p[0] for p in ring)+.6
        while x<max(p[0] for p in ring):
            hits=[]
            for a,b in zip(ring,ring[1:]+ring[:1]):
                if min(a[0],b[0])<=x<max(a[0],b[0]):hits.append(a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0]))
            hits.sort()
            for ya,yb in zip(hits[::2],hits[1::2]):
                if yb-ya>.2:meshes['roof_seams'].beam((x,ya+.08,top(x,ya+.08)+.025),(x,yb-.08,top(x,yb-.08)+.025),.022,mats['metal'],6)
            x+=1.2
        for edge,(a,b) in enumerate(zip(ring,ring[1:]+ring[:1])):
            L=math.dist(a,b);tx=(b[0]-a[0])/L;ty=(b[1]-a[1])/L;nx,ny=ty,-tx;ang=math.atan2(ty,tx)
            def p(s,z,d=0):return(a[0]+tx*s-nx*d,a[1]+ty*s-ny*d,z)
            def box(key,s,z,w,h,mat,d=0,depth=.1):meshes[key].box(*p(s,z,d),w,depth,h,mat,ang)
            shared=0
            for interface in cfg.get('shared_edges',[]):
                if min(math.dist(a,interface['a'])+math.dist(b,interface['b']),math.dist(a,interface['b'])+math.dist(b,interface['a']))<.02:shared=interface['height'];interfaces.append(interface)
            rooflo=min(top(*a),top(*b)); holes=[]
            # Mapped entrance is a polygon vertex: use adjacent east-facing edge.
            isdoor=main and math.dist(b,(-44.598824,522.979455))<.02
            for floor in range(levels):
                z0=floor*3
                if z0<shared-.01:continue
                n=int(L/3.0)
                if n<1:continue
                for j in range(n):
                    c=L*(j+.5)/n; door=isdoor and floor==0 and j==n-1
                    w=min(2.2 if door else 1.75,L/n-.75);lo=0 if door else z0+.85;hi=2.45 if door else min(z0+2.55,rooflo-.25)
                    if hi<=lo:continue
                    holes.append((c-w/2,c+w/2,lo,hi,door))
            cuts=sorted({shared,rooflo,*[v for h in holes for v in h[2:4]]})
            for lo,hi in zip(cuts,cuts[1:]):
                if hi<=shared or lo>=rooflo:continue
                cursor=0
                for le,ri in sorted((h[0],h[1]) for h in holes if h[2]<=lo and h[3]>=hi)+[(L,L)]:
                    if le>cursor:meshes['wall_openings'].face([p(cursor,lo),p(le,lo),p(le,hi),p(cursor,hi)],mats['brick'])
                    cursor=ri
            if abs(top(*a)-top(*b))>1e-7:
                coords=[p(0,rooflo),p(L,rooflo),p(L,top(*b)),p(0,top(*a))];coords=[q for i,q in enumerate(coords) if q!=coords[i-1]]
                if len(coords)>=3:meshes['wall_openings'].face(coords,mats['brick'])
            for le,ri,lo,hi,door in holes:
                dep=.38 if door else .24;c=(le+ri)/2;w=ri-le
                for q,r in [((le,lo),(ri,lo)),((ri,lo),(ri,hi)),((ri,hi),(le,hi)),((le,hi),(le,lo))]:meshes['wall_openings'].face([p(*q),p(*r),p(*r,dep),p(*q,dep)],mats['trim'])
                box('door_leaves' if door else 'window_glass',c,(lo+hi)/2,w-.08,hi-lo-.08,mats['glass'],dep,.03)
                for s in [le+.04,c,ri-.04]:box('frames_sills',s,(lo+hi)/2,.07,hi-lo,mats['metal'],dep-.03,.07)
                for z in [lo+.04,hi-.04]:box('frames_sills',c,z,w,.07,mats['metal'],dep-.03,.07)
                if not door:
                    box('frames_sills',c,lo-.05,w+.14,.10,mats['trim'],-.045,.34)
                    box('frames_sills',c,hi-.45,w,.05,mats['metal'],dep-.03,.07)
                else:
                    box('entrance_canopy',c,hi+.30,w+.8,.14,mats['entry'],-.52,1.5)
                    for s in [c-.14,c+.14]:meshes['door_leaves'].beam(p(s,.95,dep-.09),p(s,1.40,dep-.09),.018,mats['metal'],8)
                    entrances.append({'threshold_xyz':list(p(c,0)),'outward_normal':[nx,ny,0],'clear_width_m':w-.14,'leaf_depth_m':dep,'certainty':'mapped_entrance_vertex_on_adjacent_edge_estimated_opening_dimensions'})
                openings.append({'edge':edge,'centre':list(p(c,(lo+hi)/2)),'door':door,'width':w,'bottom':lo,'top':hi,'normal':[nx,ny,0],'recess':dep})
            if shared<rooflo:
                meshes['roof_edge_flashings'].beam((*a,top(*a)+.07),(*b,top(*b)+.07),.075,mats['metal'],8)
                if L>5:
                    s=.22;meshes['rainwater_pipes'].beam(p(s,.1,-.10),p(s,rooflo-.05,-.10),.055,mats['metal'],8)
    objects=[]
    for key,m in meshes.items():
        o=m.done()
        if o:
            o['building_id']=feature['id'];o['semantic_component']=key;o['semantic_id']=feature['id']+'::'+key;o['certainty']='mapped_plan_estimated_elevations';o['evidence_status']='source_poor_detailed_study_not_verified_reconstruction';objects.append(o.name)
    return {'created':objects,'openings':openings,'interfaces':{'entrances':entrances,'shared_edges':interfaces},'parameters':{'baseline_height_m':H,'assumed_floor_spacing_m':3,'roof_slope':slope,'roof_slope_certainty':'estimated; source roof_shape only'},'uncertainty':['No facade or roof photographs used. Openings, frames, materials, rainwater pipes and canopy are artistic estimates.','Full mapped polygons and baseline heights retained. Two ancillary heights are unverified9m defaults.','Radial LiDAR roof replacement remains on hold and is not incorporated.','Shared party walls omitted only below neighbor height; no interior fitout.']}
