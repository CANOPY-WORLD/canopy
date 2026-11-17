"""Blender generator for a configured concept office floor, in scene ENU metres.
Run: blender -b --python this_file -- CONFIG OUTPUT_DIRECTORY
Layout and source evidence live in the scene configuration, not this module.
"""
import bpy, json, sys, math
from pathlib import Path
from mathutils import Vector
cfg_path, out_path = sys.argv[sys.argv.index('--')+1:]
cfg=json.loads(Path(cfg_path).read_text()); out=Path(out_path);out.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
z=cfg['floor_z_m']; H=cfg['wall_height_m']
def mat(name,color):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);return m
floor=mat('Warm stone',(0.72,.71,.66));white=mat('Partition ivory',(.86,.87,.83));red=mat('Terracotta facade',(.49,.19,.105));wood=mat('Oak',(.55,.36,.19));dark=mat('Graphite',(.07,.11,.14));blue=mat('Office carpet',(.16,.32,.36));green=mat('Lounge sage',(.32,.46,.36));glass=mat('Pale blue glazing',(.51,.72,.77));ink=mat('Signage',(.06,.13,.17))
def box(name,x,y,w,d,h,bottom,material):
 bpy.ops.mesh.primitive_cube_add(size=1,location=(x,y,bottom+h/2));o=bpy.context.object;o.name=name;o.dimensions=(w,d,h);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(material);o['design_status']='hypothetical concept';return o
edges=set()
def edge(name,a,b,h=H,material=white,bottom=z):
 key=(tuple(sorted((tuple(a),tuple(b)))),h,bottom)
 if key in edges:return
 edges.add(key)
 dx,dy=b[0]-a[0],b[1]-a[1];o=box(name,(a[0]+b[0])/2,(a[1]+b[1])/2,math.hypot(dx,dy),.16,h,bottom,material);o.rotation_euler.z=math.atan2(dy,dx);return o
def label(text,x,y,size=.65):
 bpy.ops.object.text_add(location=(x,y,z+.045));o=bpy.context.object;o.name=text;o.data.body=text;o.data.size=size;o.data.materials.append(ink)
def chair(x,y):
 box('Chair seat',x,y,.55,.55,.12,z+.43,blue);box('Chair back',x,y+.25,.55,.1,.55,z+.45,blue);box('Chair base',x,y,.1,.1,.43,z,dark)
def desk(x,y):
 box('Desk',x,y,1.6,.8,.08,z+.73,wood)
 for dx in [-.65,.65]:box('Desk leg',x+dx,y,.06,.65,.73,z,dark)
 box('Monitor',x,y+.18,.55,.08,.35,z+.86,dark);chair(x,y-.85)
p=cfg['footprint_enu_xy'];N=len(p);verts=[(x,y,z-.25) for x,y in p]+[(x,y,z) for x,y in p];faces=[tuple(range(N-1,-1,-1)),tuple(range(N,2*N))]+[(i,(i+1)%N,(i+1)%N+N,i+N) for i in range(N)]
mesh=bpy.data.meshes.new('Model-derived perimeter');mesh.from_pydata(verts,[],faces);mesh.update();o=bpy.data.objects.new('Floor slab / east volume',mesh);bpy.context.collection.objects.link(o);o.data.materials.append(floor)
for a,b in zip(p,p[1:]+p[:1]):
 edge('Terracotta sill',a,b,.65,red)
 # open-topped facade with slender frame posts; full-height glass omitted for clarity
 length=math.dist(a,b)
 for i in range(int(length/2.4)+1):
  t=i/max(1,int(length/2.4));x=a[0]+(b[0]-a[0])*t;y=a[1]+(b[1]-a[1])*t
  box('Facade mullion',x,y,.09,.09,H,z,dark)
for r in cfg['rooms']:
 x0,y0,x1,y1=r['rect'];typ=r['type'];cx=(x0+x1)/2;cy=(y0+y1)/2
 box(r['name']+' floor',cx,cy,x1-x0-.2,y1-y0-.2,.02,z,green if typ=='lounge' else blue if typ in ('office','meeting') else floor)
 # East-facing opening 1.2 m wide; all rooms reach surrounding circulation.
 if typ!='lounge':
  for a,b in [((x0,y0),(x1,y0)),((x0,y1),(x1,y1)),((x0,y0),(x0,y1)),((x1,y0),(x1,cy-.6)),((x1,cy+.6),(x1,y1))]:edge(r['name']+' partition',a,b)
  edge('Door lintel',(x1,cy-.6),(x1,cy+.6),.35,white,z+H-.35)
 label(r['name'],x0+.5,y0+.5,.52)
 if typ=='office':desk(cx,cy)
 if typ=='meeting':
  box('Meeting table',cx,cy,4,1.4,.1,z+.72,wood)
  for dx in [-1.4,0,1.4]:chair(cx+dx,cy-1.3);chair(cx+dx,cy+1.3)
 if typ=='lounge':
  box('Tea counter',cx,y1-.7,8,.65,.9,z,wood)
  for dx in [-3,1.5]:
   box('Lounge table',cx+dx,cy,1.4,1.4,.1,z+.7,wood);chair(cx+dx,cy-1.1);chair(cx+dx,cy+1.1)
 if typ=='core':
  # Indicative stair/service reservation only, not a detailed circulation design.
  for i in range(10):box('Indicative stair',x0+1.6,y0+.6+i*.22,2,.22,.15*(i+1),z,white)
  box('Service reservation',x0+4,cy,1.5,1.8,2.4,z,glass)
for x,y in cfg['desk_centres']:
 for dx in [-.85,.85]:desk(x+dx,y)
label('OPEN WORKSPACE / 28 DESKS',35,98,.7)
label('CONCEPT / NOT AS BUILT',34,79,.55)
# Native file and GLB contain only architectural geometry, with no roof.
bpy.ops.wm.save_as_mainfile(filepath=str(out/'office.blend'))
bpy.ops.export_scene.gltf(filepath=str(out/'office.glb'),export_format='GLB',export_yup=True)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24
scene.world.color=(.65,.65,.65)
bpy.ops.object.light_add(type='AREA',location=(40,85,70));bpy.context.object.data.energy=18000;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=55
bpy.ops.object.light_add(type='SUN',location=(0,0,60));bpy.context.object.data.energy=2;bpy.context.object.rotation_euler=(.4,-.3,-.3)
def render(name,location,target,scale):
 bpy.ops.object.camera_add(location=location);cam=bpy.context.object;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=scale;scene.camera=cam;scene.render.resolution_x=1600;scene.render.resolution_y=1400;scene.render.resolution_percentage=100;scene.render.filepath=str(out/name);bpy.ops.render.render(write_still=True)
render('axonometric.png',(100,15,91),(42,91,z),78)
render('floor_plan.png',(43,92,100),(43,92,z),65)
print('OFFICE_CONCEPT_COMPLETE',out)
