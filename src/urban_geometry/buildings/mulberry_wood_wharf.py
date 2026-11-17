"""Editable Mulberry architectural study; footprint mapped, elevations estimated.

Not a surveyed reconstruction. Source-reported three accommodation levels conflicts
with OSM four levels. All facade and terrace parameters are explicit estimates.
No downloads, scene clearing or export side effects.
"""
import math

DEFAULTS = dict(storey_height_m=3.8, accommodation_levels=3, upper_setback_ratio=.86,
               bay_spacing_m=3.8, opening_width_m=2.25, opening_height_m=2.45,
               sill_m=.85, reveal_m=.28, parapet_m=.35, rail_height_m=1.2)


def build(ctx, feature):
    cfg = dict(DEFAULTS, **feature.get('detail_parameters', {}))
    base = feature.get('base_m', 0.)
    original = feature['geometry'][0]['outer']
    ring = [tuple(p) for p in original]
    if ring[0] == ring[-1]: ring = ring[:-1]
    if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]+ring[:1])) < 0: ring.reverse()
    # Remove only collinear vertices from elevation segmentation, never floor ring.
    corners = [p for i,p in enumerate(ring) if abs((p[0]-ring[i-1][0])*(ring[(i+1)%len(ring)][1]-p[1])-(p[1]-ring[i-1][1])*(ring[(i+1)%len(ring)][0]-p[0])) > .1]
    cx = sum(p[0] for p in corners)/len(corners); cy=sum(p[1] for p in corners)/len(corners)
    inset = [(cx+(x-cx)*cfg['upper_setback_ratio'],cy+(y-cy)*cfg['upper_setback_ratio']) for x,y in corners]
    mats = {
        'wall':ctx.material('Mulberry study warm white precast',(.72,.70,.65),.75),
        'trim':ctx.material('Mulberry study white opening reveals',(.83,.82,.76),.62),
        'glass':ctx.material('Mulberry study dark recessed glazing',(.065,.16,.19),.22,.15,.15),
        'metal':ctx.material('Mulberry study bronze metal',(.17,.19,.18),.42,.55),
        'roof':ctx.material('Mulberry study roof terrace surface',(.34,.39,.33),.92),
        'slab':ctx.material('Mulberry study slab edge',(.57,.57,.53),.82),
    }
    meshes={k:ctx.mesh(k) for k in ['mapped_ground_slab','partitioned_walls','recessed_glazing','opening_frames','floor_slabs','terrace_parapets','terrace_railings','entry_leaves','entry_canopy']}
    entrance=[]; openings=[]; H=cfg['storey_height_m']; levels=cfg['accommodation_levels']
    def polygon(m, poly,z,mat,reverse=False):
        # Mapped school ring is convex; preserve collinear mapped vertices.
        for i in range(1,len(poly)-1):
            t=[(*poly[0],base+z),(*poly[i],base+z),(*poly[i+1],base+z)]
            if reverse:t.reverse()
            if abs((t[1][0]-t[0][0])*(t[2][1]-t[0][1])-(t[1][1]-t[0][1])*(t[2][0]-t[0][0]))>1e-8:m.face(t,mat)
    def slab(poly,z,thick,mesh,mat):
        polygon(mesh,poly,z,mat);polygon(mesh,poly,z-thick,mat,True)
        for a,b in zip(poly,poly[1:]+poly[:1]):mesh.face([(*a,base+z-thick),(*b,base+z-thick),(*b,base+z),(*a,base+z)],mat)
    slab(ring,0,.18,meshes['mapped_ground_slab'],mats['slab'])
    for floor in range(levels):
        poly=corners if floor==0 else inset
        z0=floor*H; z1=z0+H
        slab(poly,z1,.22,meshes['floor_slabs'],mats['roof'] if floor==levels-1 or floor==0 else mats['slab'])
        for edge,(a,b) in enumerate(zip(poly,poly[1:]+poly[:1])):
            L=math.dist(a,b); tx=(b[0]-a[0])/L;ty=(b[1]-a[1])/L;nx,ny=ty,-tx;ang=math.atan2(ty,tx)
            def p(s,z,d=0):return(a[0]+tx*s-nx*d,a[1]+ty*s-ny*d,base+z)
            def box(key,s,z,w,h,mat,d=0,depth=.10):meshes[key].box(*p(s,z,d),w,depth,h,mat,ang)
            n=max(1,int(L/cfg['bay_spacing_m'])); holes=[]
            for j in range(n):
                c=L*(j+.5)/n;door=floor==0 and nx<-.8 and j==n//2
                w=2.6 if door else min(cfg['opening_width_m'],L/n-.6)
                lo=z0 if door else z0+cfg['sill_m'];hi=z0+2.9 if door else lo+cfg['opening_height_m']
                holes.append((c-w/2,c+w/2,lo,hi,door))
            cuts=sorted({z0,z1,*[v for h in holes for v in h[2:4]]})
            for lo,hi in zip(cuts,cuts[1:]):
                cursor=0.
                for left,right in sorted((h[0],h[1]) for h in holes if h[2]<=lo and h[3]>=hi)+[(L,L)]:
                    if left>cursor:meshes['partitioned_walls'].face([p(cursor,lo),p(left,lo),p(left,hi),p(cursor,hi)],mats['wall'])
                    cursor=right
            for le,ri,lo,hi,door in holes:
                dep=.42 if door else cfg['reveal_m'];c=(le+ri)/2;w=ri-le
                for q,r in [((le,lo),(ri,lo)),((ri,lo),(ri,hi)),((ri,hi),(le,hi)),((le,hi),(le,lo))]:
                    meshes['partitioned_walls'].face([p(*q),p(*r),p(*r,dep),p(*q,dep)],mats['trim'])
                box('entry_leaves' if door else 'recessed_glazing',c,(lo+hi)/2,w-.06,hi-lo-.06,mats['glass'],dep,.035)
                for s in [le+.045,c,ri-.045]:box('opening_frames',s,(lo+hi)/2,.065,hi-lo,mats['metal'],dep-.045,.09)
                for z in [lo+.04,hi-.04]:box('opening_frames',c,z,w,.07,mats['metal'],dep-.045,.09)
                if not door:box('opening_frames',c,lo+(hi-lo)*.73,w,.055,mats['metal'],dep-.045,.08)
                if door:
                    for s in [c-.16,c+.16]:meshes['entry_leaves'].beam(p(s,lo+.95,dep-.1),p(s,lo+1.5,dep-.1),.018,mats['metal'],10)
                    box('entry_canopy',c,hi+.35,w+1.0,.14,mats['trim'],-.6,1.55)
                    entrance.append(dict(threshold_xyz=list(p(c,0)),outward_normal=[nx,ny,0],clear_width_m=w-.13,door_leaf_xyz=list(p(c,(lo+hi)/2,dep)),door_leaf_depth_m=dep,certainty='artistically_estimated_unverified_location'))
                openings.append(dict(floor=floor,edge=edge,door=door,centre=list(p(c,(lo+hi)/2)),recess_m=dep,certainty='artistically_estimated'))
            # Joint lines are true shallow recess-coloured components, not image textures.
            for j in range(1,n):box('opening_frames',L*j/n,(z0+z1)/2,.018,H-.08,mats['slab'],-.002,.012)
    for poly,z in [(corners,H),(inset,levels*H)]:
        for a,b in zip(poly,poly[1:]+poly[:1]):
            L=math.dist(a,b);ang=math.atan2(b[1]-a[1],b[0]-a[0]);cx1=(a[0]+b[0])/2;cy1=(a[1]+b[1])/2
            meshes['terrace_parapets'].box(cx1,cy1,base+z+.15,L,.18,.3,mats['wall'],ang)
            for railz in [.42,cfg['rail_height_m']]:meshes['terrace_railings'].beam((*a,base+z+railz),(*b,base+z+railz),.023,mats['metal'],8)
            for j in range(math.ceil(L/.14)+1):
                q=j/math.ceil(L/.14);x=a[0]+q*(b[0]-a[0]);y=a[1]+q*(b[1]-a[1])
                meshes['terrace_railings'].beam((x,y,base+z+.3),(x,y,base+z+cfg['rail_height_m']),.012,mats['metal'],6)
    objects=[]
    for key,m in meshes.items():
        obj=m.done()
        if obj:
            obj['building_id']=feature['id'];obj['semantic_component']=key
            obj['certainty']='mapped_plan_estimated_thickness' if key=='mapped_ground_slab' else 'artistically_estimated_geometry'
            obj['evidence_status']='source_poor_detailed_study_not_verified_reconstruction';objects.append(obj.name)
    return dict(created=objects,parameters=cfg,interfaces={'entrances':entrance},openings=openings,evidence_source_ids=['osm-way-1086252782','myshkin-clarke-hall-school-text','patel-taylor-harbord-text'],uncertainty=['Exact OSM footprint retained. Three accommodation levels from architect text conflict with OSM four levels.','All facade bays, setbacks, terrace extents, railing design, door placement and heights are artistic estimates, not observed.','No inspected licensed photographs were available at authoring; no HVAC, interior layout or hidden equipment invented.','Ground datum zero is unsurveyed. Facade study is not solver-ready or a verified school access plan.'])
