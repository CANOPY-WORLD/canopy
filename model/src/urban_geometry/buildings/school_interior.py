"""Conceptual ground-floor teaching pods inside a mapped footprint.

No claim of surveyed rooms, entrances, occupancy, code compliance or HVAC.
Geometry is an intentionally open 1.1 m cutaway, not a sealed CFD domain.
"""
import math

def inside(p, ring):
    x,y=p; result=False
    for a,b in zip(ring,ring[1:]+ring[:1]):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:result=not result
    return result

def concept_rectangle(ring):
    """Find a conservative axis-aligned rectangle using dense edge samples."""
    xmin=min(x for x,y in ring);xmax=max(x for x,y in ring);ymin=min(y for x,y in ring);ymax=max(y for x,y in ring)
    best=None
    for w in range(12,int(xmax-xmin)-1,2):
      for h in range(16,int(ymax-ymin)-1,2):
       for ix in range(1,8):
        for iy in range(1,8):
         x=xmin+(xmax-xmin-w)*ix/8;y=ymin+(ymax-ymin-h)*iy/8
         pts=[(x+w*t/20,y+dy) for t in range(21) for dy in [0,h]]+[(x+dx,y+h*t/20) for t in range(21) for dx in [0,w]]
         if (best is None or w*h>best[0]) and all(inside(p,ring) for p in pts):best=(w*h,x,y,w,h)
    if best is None:raise ValueError('No suitable conceptual teaching pod area')
    return best[1:]

def build(ctx, feature):
    ring=[tuple(p) for p in feature['geometry'][0]['outer']];school=feature['school_id']
    mats={k:ctx.material('Interior concept '+k,c,.8) for k,c in [('floor',(.79,.79,.73)),('wall',(.86,.84,.77)),('classroom',(.57,.72,.62)),('quiet',(.83,.69,.49)),('corridor',(.35,.57,.66)),('desk',(.65,.42,.22)),('chair',(.12,.34,.42)),('door',(.71,.31,.12))]}
    mesh={k:ctx.mesh('concept_'+k) for k in ['footprint_floor','room_floors','cutaway_partitions','open_door_leaves','desks','chairs','shelves']}
    for part in feature['geometry']:
      for tri in part['triangles']:
       coords=[part['vertices_xy'][i] for i in tri] if isinstance(tri[0],int) else tri
       mesh['footprint_floor'].face([(*p,.04) for p in coords],mats['floor'])
    x,y,w,h=concept_rectangle(ring);corr=2.4; wing=(w-corr)/2;count=3 if h<34 else 4;rh=h/count;rooms=[];doors=[]
    def box(key,cx,cy,z,ww,dd,hh,mat):mesh[key].box(cx,cy,z,ww,dd,hh,mats[mat])
    box('room_floors',x+w/2,y+h/2,.065,corr,h,.04,'corridor')
    def wall(cx,cy,ww,dd):box('cutaway_partitions',cx,cy,.62,ww,dd,1.1,'wall')
    for side in [0,1]:
      xx=x if side==0 else x+wing+corr
      corridor_edge=x+wing if side==0 else xx
      for i in range(count):
       yy=y+i*rh; label=('Reading and quiet room' if i==0 and side==1 else 'Staff / reception concept' if i==0 and side==0 else f'Classroom {side*count+i}')
       typ='quiet' if i==0 else 'classroom';cx=xx+wing/2;cy=yy+rh/2
       box('room_floors',cx,cy,.09,wing-.15,rh-.15,.04,typ)
       wall(xx if side==0 else xx+wing,cy,.15,rh)
       if i==0:wall(cx,yy,wing,.15)
       wall(cx,yy+rh,wing,.15)
       # A 1.3 m clear opening onto corridor; open leaf points into room.
       gap=1.3;dy=yy+rh*.38
       wall(corridor_edge,(yy+dy-gap/2)/2,.15,dy-gap/2-yy)
       wall(corridor_edge,(dy+gap/2+yy+rh)/2,.15,yy+rh-dy-gap/2)
       sign=-1 if side==0 else 1
       box('open_door_leaves',corridor_edge+sign*.58,dy-gap/2,.55,1.12,.06,1.,'door')
       doors.append({'room_id':f'{school}_room_{side}_{i}','center_enu_m':[corridor_edge,dy,.1],'clear_width_m':gap,'assumed':True})
       # Furniture kept away from corridor-side door zone.
       for a in [-1,1]:
        for b in [-1,1]:
         dx=cx+a*min(1.7,wing*.22);dy2=cy+b*min(1.7,rh*.23)
         box('desks',dx,dy2,.75,1.3,.75,.1,'desk')
         for lx in [-.5,.5]:
          for ly in [-.23,.23]:box('desks',dx+lx,dy2+ly,.4,.06,.06,.65,'chair')
         box('chairs',dx,dy2-.65,.44,.48,.46,.09,'chair');box('chairs',dx,dy2-.84,.70,.48,.06,.53,'chair')
       box('shelves',cx,yy+rh-.4,.6,min(2.4,wing*.5),.42,1.0,'desk')
       rooms.append({'id':f'{school}_room_{side}_{i}','label':label,'assumed_use':True,'center_enu_m':[cx,cy,.12],'polygon_enu_m':[[xx,yy],[xx+wing,yy],[xx+wing,yy+rh],[xx,yy+rh]]})
    rooms.append({'id':school+'_corridor','label':'Concept corridor (2.4 m)','assumed_use':True,'center_enu_m':[x+w/2,y+h/2,.12],'polygon_enu_m':[[x+wing,y],[x+wing+corr,y],[x+wing+corr,y+h],[x+wing,y+h]]})
    made=[]
    for key,m in mesh.items():
      obj=m.done()
      if obj:
       obj['building_id']=feature['id'];obj['school_id']=school;obj['semantic_component']='concept_interior_'+key;obj['semantic_id']=feature['id']+'::concept_interior_'+key;obj['certainty']='hypothetical_user_authorized';made.append(obj.name)
    return {'school_id':school,'building_ids':[feature['id']],'asset':f'{school}/{school}_interior.glb','center_enu_m':[x+w/2,y+h/2],'camera_offset':[35,45,45],'rooms':rooms,'doors':doors,'created':made,'cutaway_wall_height_m':1.1,'assumed_full_wall_height_m':3.,'unassigned_perimeter':'Footprint remainder is intentionally unassigned; not a room survey','simulation_ready':False}
