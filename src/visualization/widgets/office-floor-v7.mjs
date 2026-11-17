/** Image-guided office presentation adapter. Scene input is local ENU metres.
 * This adapter builds only the proposed interior; it does not infer real cores,
 * services or occupancy from the source facade. The authored envelope is retained.
 */
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { createFurnitureLibrary } from './office-furniture.mjs';

export function createModernOfficeFloor(config, facadeData) {
  const group = new THREE.Group(); group.name = 'White City / image-guided modern office';
  const upper = new THREE.Group(), facade = new THREE.Group(), ceiling = new THREE.Group();
  const furniture = new THREE.Group(), people = new THREE.Group(), route = new THREE.Group();
  const base = new THREE.Group(), lighting = new THREE.Group();
  for (const [name, g] of Object.entries({base, upper, facade, ceiling, furniture, people, route, lighting})) {
    g.name = name; group.add(g);
  }
  const labels = [], picks = [], ownedMaterials = new Set(), ownedTextures = new Set();
  const lib = createFurnitureLibrary({style:'modern'});
  const diagnostics = {layoutVersion:7, sourceFacadeMeshCount:0, roomCount:config.rooms.length,
    partitionCount:0, doorCount:0, slatCount:0, furnitureCount:0, missingFurniture:[],
    commonFurnitureZones:0, commonSeating:0};
  group.userData = diagnostics;
  const unit = new THREE.BoxGeometry(1,1,1);
  const material = (color, roughness=.75, extra={}) => {
    const m = new THREE.MeshStandardMaterial({color,roughness,...extra}); ownedMaterials.add(m); return m;
  };
  const glass = new THREE.MeshPhysicalMaterial({color:'#e2eceb',transparent:true,opacity:.16,
    roughness:.10,metalness:.025,depthWrite:false,side:THREE.DoubleSide}); ownedMaterials.add(glass);
  const mats = {wall:material('#efefec'), slab:material('#c6c7c3'), frame:material('#3f484c',.34,{metalness:.55}),
    oak:lib.materials.oak, trim:material('#838b8b',.45,{metalness:.35}), glass,
    ceiling:material('#fafaf7',.84,{side:THREE.DoubleSide}),
    light:material('#ffffff',.25,{emissive:'#fff8eb',emissiveIntensity:1.3}),
    base:material('#d7d9d6',.94), carpet:material('#b5bdbb',.97), stone:material('#dedfdb',.87)};
  function floorTexture(kind) {
    const canvas=document.createElement('canvas'); canvas.width=canvas.height=512;
    const ctx=canvas.getContext('2d'); let seed=48;
    const rand=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
    ctx.fillStyle=kind==='wood'?'#e5e1d8':kind==='carpet'?'#d4d7d6':'#eceeea';ctx.fillRect(0,0,512,512);
    for(let i=0;i<6000;i++) {
      ctx.fillStyle=`rgba(75,83,80,${rand()*.045})`;
      ctx.fillRect(rand()*512,rand()*512,kind==='wood'?35+rand()*150:1,1);
    }
    if(kind==='wood') {ctx.strokeStyle='rgba(83,89,82,.10)';ctx.lineWidth=.8;
      for(let y=0;y<512;y+=64){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(512,y);ctx.stroke();
        const x=(y/64%2)*256;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x,y+64);ctx.stroke();}}
    const map=new THREE.CanvasTexture(canvas);map.colorSpace=THREE.SRGBColorSpace;
    map.wrapS=map.wrapT=THREE.RepeatWrapping;map.repeat.set(kind==='wood'?.5:.7,kind==='wood'?.5:.7);
    map.anisotropy=8;ownedTextures.add(map);return map;
  }
  mats.base.map=floorTexture('stone');mats.stone.map=mats.base.map;mats.carpet.map=floorTexture('carpet');
  const woodFloor=material('#f0ece4',.76,{map:floorTexture('wood')});
  function shape(points) {const s=new THREE.Shape();points.forEach((p,i)=>i?s.lineTo(p[0],p[1]):s.moveTo(p[0],p[1]));s.closePath();return s;}
  function polygon(parent,name,points,mat,y=.025,depth=0) {
    const geo=depth?new THREE.ExtrudeGeometry(shape(points),{depth,bevelEnabled:false}):new THREE.ShapeGeometry(shape(points));
    const mesh=new THREE.Mesh(geo,mat);mesh.rotation.x=-Math.PI/2;mesh.position.y=y;
    mesh.name=name;mesh.receiveShadow=true;mesh.castShadow=depth>0;parent.add(mesh);return mesh;
  }
  function box(parent,name,x,n,w,d,h,bottom,mat) {
    const o=new THREE.Mesh(unit,mat);o.name=name;o.position.set(x,bottom+h/2,-n);o.scale.set(w,h,d);
    o.castShadow=true;o.receiveShadow=true;parent.add(o);return o;
  }
  function segment(parent,name,a,b,h,bottom,mat,thickness=.12) {
    const len=Math.hypot(b[0]-a[0],b[1]-a[1]);if(len<.001)return null;
    const o=box(parent,name,(a[0]+b[0])/2,(a[1]+b[1])/2,len,thickness,h,bottom,mat);
    o.rotation.y=Math.atan2(b[1]-a[1],b[0]-a[0]);return o;
  }
  polygon(base,'Authored floor plate',config.footprintLocal,mats.slab,-.30,.30);
  polygon(base,'Continuous microcement circulation floor',config.footprintLocal,mats.base,.008);
  polygon(ceiling,'Continuous warm-white ceiling',config.footprintLocal,mats.ceiling,3.77,.10).castShadow=false;

  for(const source of facadeData?.meshes||[]) {
    if(source.classification==='slab')continue;
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(source.positions,3));geo.setIndex(source.triangles);
    const flat=geo.toNonIndexed();geo.dispose();flat.computeVertexNormals();
    const isGlass=source.classification==='glass'||source.surfaceType==='glass';
    const mat=isGlass?glass.clone():material(source.classification==='terracotta'?'#a1513e':'#384246',.52);
    if(isGlass){mat.opacity=.12;ownedMaterials.add(mat);}
    const mesh=new THREE.Mesh(flat,mat);mesh.name=source.sourceNodeName||source.id;
    mesh.userData={sourceNode:source.sourceNode,classification:source.classification};
    mesh.castShadow=!isGlass;mesh.receiveShadow=true;facade.add(mesh);diagnostics.sourceFacadeMeshCount++;
  }

  function wallSpan(a,b,p) {
    const height=p.height||3.15,thickness=p.thickness||.13,type=p.material||'solid';
    const len=Math.hypot(b[0]-a[0],b[1]-a[1]);if(len<.02)return;
    if(type==='glass') {
      segment(base,'Glass partition base channel',a,b,.045,.018,mats.frame,.065);
      segment(upper,'Low iron glass partition',a,b,height-.09,.065,mats.glass,.026);
      segment(upper,'Slim partition head channel',a,b,.045,height+.02,mats.frame,.065);
      const bays=Math.max(1,Math.ceil(len/1.5));
      for(let k=0;k<=bays;k++){const t=k/bays;box(upper,'Slender glazing mullion',a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,.035,.035,height,.02,mats.frame);}
    } else if(type==='slats') {
      const angle=Math.atan2(b[1]-a[1],b[0]-a[0]);
      const spacing=p.slatSpacing||.16,width=p.slatWidth||.03;
      segment(upper,'Oak screen bottom rail',a,b,.03,.03,mats.oak,.07);
      segment(upper,'Oak screen top rail',a,b,.03,height-.03,mats.oak,.07);
      for(let d=width/2;d<len-width/2;d+=spacing){const t=d/len;
        box(upper,'Vertical oak screen blade',a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,width,.065,height,.015,mats.oak).rotation.y=angle;
        diagnostics.slatCount++;
      }
    } else {
      segment(base,'Solid partition plinth',a,b,.16,.02,mats.wall,thickness);
      segment(upper,'Warm-white acoustic wall',a,b,height-.16,.18,mats.wall,thickness);
      segment(base,'Recessed grey skirting',a,b,.055,.025,mats.trim,thickness+.012);
    }
  }
  for(const p of config.partitions||[]) {
    diagnostics.partitionCount++;
    const a=p.a,b=p.b,len=Math.hypot(b[0]-a[0],b[1]-a[1]);
    const point=d=>[a[0]+(b[0]-a[0])*d/len,a[1]+(b[1]-a[1])*d/len];
    const doors=[...(p.doors||[])].sort((a,b)=>a.offset-b.offset);let cursor=0;
    for(const door of doors) {
      const width=door.width||1.1,lo=Math.max(0,door.offset-width/2),hi=Math.min(len,door.offset+width/2);
      if(lo>cursor)wallSpan(point(cursor),point(lo),p);
      const start=point(lo),end=point(hi),height=2.65,wallHeight=p.height||3.15;
      segment(upper,'Door head',start,end,wallHeight-height,height,mats.wall,p.thickness||.13);
      for(const q of[start,end])box(upper,'Door frame',q[0],q[1],.045,.065,height,0,mats.frame);
      const pivot=new THREE.Group();pivot.name='Door / '+p.id;pivot.position.set(start[0],0,-start[1]);
      pivot.rotation.y=Math.atan2(b[1]-a[1],b[0]-a[0])+(door.openAngleDeg??35)*Math.PI/180;
      const doorMat=(door.material||(p.material==='solid'?'solid':'glass'))==='solid'?mats.wall:mats.glass;
      box(pivot,'Door leaf',width/2,0,width-.035,.035,height-.06,.03,doorMat);
      for(const xx of[.025,width-.04])box(pivot,'Door stile',xx,0,.025,.045,height-.06,.03,mats.frame);
      box(pivot,'Door pull',width-.16,-.065,.025,.035,.34,.93,mats.trim);
      upper.add(pivot);diagnostics.doorCount++;cursor=hi;
    }
    if(cursor<len)wallSpan(point(cursor),b,p);
  }

  for(const room of config.rooms) {
    const [x0,y0,x1,y1]=room.rect;
    const points=room.polygonLocal||[[x0,y0],[x1,y0],[x1,y1],[x0,y1]];
    const pt=room.labelPoint||[(x0+x1)/2,(y0+y1)/2];
    const floorMat=['common','pantry','reception','lounge'].includes(room.type)?woodFloor:
      ['office','meeting','phone','open','hotdesk'].includes(room.type)?mats.carpet:mats.stone;
    polygon(base,room.name+' / finish',points,floorMat,.023);
    if(['office','meeting','phone','wc','washroom','storage'].includes(room.type)) {
      polygon(ceiling,room.name+' / acoustic ceiling',points,mats.ceiling,3.19,.06).castShadow=false;
    }
    labels.push({room,position:new THREE.Vector3(pt[0],.12,-pt[1])});
    picks.push({room,polygon:points,box:new THREE.Box3(new THREE.Vector3(x0,0,-y1),new THREE.Vector3(x1,3.2,-y0))});
    for(const spec of room.furnishings||[]) {
      const factory=lib[spec.kind];
      if(typeof factory!=='function'){diagnostics.missingFurniture.push(spec.kind);continue;}
      const o=factory(spec.options||{});o.name=room.id+' / '+spec.kind;
      o.position.set(spec.position[0],spec.height||0,-spec.position[1]);o.rotation.y=(spec.rotationDeg||0)*Math.PI/180;
      if(spec.scale)o.scale.set(...spec.scale);furniture.add(o);diagnostics.furnitureCount++;
      if(room.type==='common'){diagnostics.commonFurnitureZones++;diagnostics.commonSeating+=spec.kind==='sofa'?(spec.options?.seats||3):0;}
    }
    // A slim architectural light is separate from furniture, so ceiling cutaway
    // never removes the desks or changes their source-plan placement.
    if(!['stair','lift','storage','wc'].includes(room.type)) {
      const width=Math.max(.8,Math.min(x1-x0-1.2,room.type==='common'?6:3.6));
      segment(upper,'Linear suspended light body',[pt[0]-width/2,pt[1]],[pt[0]+width/2,pt[1]],.065,3.08,mats.frame,.09);
      segment(upper,'Linear opal diffuser',[pt[0]-width/2+.025,pt[1]],[pt[0]+width/2-.025,pt[1]],.012,3.067,mats.light,.065);
      for(const dx of[-width*.32,width*.32])box(upper,'Fine pendant cable',pt[0]+dx,pt[1],.007,.007,.6,3.145,mats.frame);
    }
  }
  for(const p of config.corridorPlants||[]) {
    const item=lib.plant({height:1.5,potColor:'ceramic'});item.position.set(p[0],0,-p[1]);furniture.add(item);
  }
  for(const p of config.people||[]) {
    const item=lib.human({color:'navy'});item.position.set(p[0],0,-p[1]);people.add(item);
  }
  const branches=(config.circulationRoute?.branches||[]).filter((_,index)=>
    !(config.floorSelection?.formerWestConnectionBranchActive===false&&index===config.floorSelection.formerWestConnectionBranchIndex));
  const paths=config.circulationRoute?[config.circulationRoute.points,...branches]:[];
  const routeMat=new THREE.LineDashedMaterial({color:'#4f7973',dashSize:.28,gapSize:.16,transparent:true,opacity:.8,depthWrite:false});
  ownedMaterials.add(routeMat);
  for(const path of paths) {
    if(!path||path.length<2)continue;
    const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(path.map(p=>new THREE.Vector3(p[0],.065,-p[1]))),routeMat);
    line.computeLineDistances();route.add(line);
  }
  route.visible=false;ceiling.visible=false;

  function batch(parent) {
    parent.updateMatrixWorld(true);const buckets=new Map(),oldGeometries=new Set();
    parent.traverse(o=>{
      if(!o.isMesh||Array.isArray(o.material))return;
      const g=(o.geometry.index?o.geometry.toNonIndexed():o.geometry.clone()).applyMatrix4(o.matrixWorld);
      oldGeometries.add(o.geometry);const key=o.material.uuid;
      if(!buckets.has(key))buckets.set(key,{mat:o.material,geos:[],names:new Set()});
      const bucket=buckets.get(key);bucket.geos.push(g);bucket.names.add(o.name);
    });
    parent.clear();
    for(const {mat,geos,names}of buckets.values()) {
      const geometry=mergeGeometries(geos,false);geos.forEach(g=>g.dispose());
      if(!geometry)throw new Error('Could not batch modern office geometry');
      const mesh=new THREE.Mesh(geometry,mat);mesh.name=parent.name+' / '+[...names].slice(0,3).join(', ');
      mesh.castShadow=mat!==mats.glass;mesh.receiveShadow=true;parent.add(mesh);
    }
    for(const g of oldGeometries)if(g!==unit)g.dispose();
  }
  batch(furniture);batch(people);batch(upper);batch(base);
  // During a building reveal, show only the part of the presentation facade
  // above the source shell's cut. Coincident source/presentation faces would
  // otherwise flicker as the camera approaches the selected level.
  const contextClip=new THREE.Plane(new THREE.Vector3(0,1,0),0);
  let contextClipped=false;
  function setFacadeContextClip(height) {
    const enabled=Number.isFinite(height);
    if(enabled)contextClip.constant=-height-.002;
    if(enabled!==contextClipped) {
      for(const mesh of facade.children) {
        mesh.material.clippingPlanes=enabled?[contextClip]:null;
        mesh.material.clipShadows=enabled;
        mesh.material.needsUpdate=true;
      }
      contextClipped=enabled;
    }
    diagnostics.facadeContextClipHeight=enabled?height:null;
  }
  return {group,route,upper,facade,ceiling,furniture,people,labels,picks,diagnostics,materials:mats,
    setFacadeContextClip,
    setWalls:visible=>{upper.visible=visible;},setFacade:visible=>{facade.visible=visible;},
    setPeople:visible=>{people.visible=visible;},
    dispose(){const geos=new Set(),materials=new Set(ownedMaterials);
      group.traverse(o=>{if(o.geometry)geos.add(o.geometry);if(o.material)for(const m of Array.isArray(o.material)?o.material:[o.material])materials.add(m);});
      geos.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());ownedTextures.forEach(t=>t.dispose());unit.dispose();lib.dispose();
    }};
}
