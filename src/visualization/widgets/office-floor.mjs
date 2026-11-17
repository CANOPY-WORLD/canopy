/** Presentation adapter for a scene-configured concept office floor. ENU -> Three: (x, z, -y). */
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { createFurnitureLibrary } from './office-furniture.mjs';
import { createModernOfficeFloor } from './office-floor-v7.mjs';
export function createOfficeFloor(config, facadeData=null) {
 if(config.layoutVersion>=7)return createModernOfficeFloor(config,facadeData);
 const root=new THREE.Group(), route=new THREE.Group(), upper=new THREE.Group(), facade=new THREE.Group(), furniture=new THREE.Group(), people=new THREE.Group(), ceiling=new THREE.Group(), labels=[], picks=[];root.name='I-HUB concept office / east volume';root.add(upper,facade,furniture,people,ceiling,route);
 for(const [name,group] of Object.entries({upper,facade,ceiling,furniture,people,route}))group.name=name;
 const isOpenConcept=(config.layoutVersion||0)>=4, hasFacade=Array.isArray(facadeData?.meshes)&&facadeData.meshes.length>0;
 const diagnostics={sourceFacadeMeshCount:0,slatCount:0,commonFurnitureZones:0,commonSeating:0};root.userData=diagnostics;
 const lib=createFurnitureLibrary();
 const standard=(c,rough=.65)=>new THREE.MeshStandardMaterial({color:c,roughness:rough});
 function texture(kind){const c=document.createElement('canvas');c.width=c.height=256;const ctx=c.getContext('2d');ctx.fillStyle=kind==='wood'?'#cab391':'#b4b2a7';ctx.fillRect(0,0,256,256);let seed=71;function rand(){seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;}
 for(let i=0;i<4000;i++){ctx.fillStyle=`rgba(${kind==='wood'?'81,54,25':'35,42,37'},${rand()*.12})`;ctx.fillRect(rand()*256,rand()*256,kind==='wood'?rand()*100:1,1)}if(kind==='wood'){ctx.strokeStyle='#a69274';for(let x=0;x<256;x+=64){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,256);ctx.stroke()}}const t=new THREE.CanvasTexture(c);t.wrapS=t.wrapT=THREE.RepeatWrapping;t.repeat.set(kind==='wood'?3:5,kind==='wood'?3:5);t.colorSpace=THREE.SRGBColorSpace;return t;}
 const mats={wall:standard('#e7e7e1'),trim:standard('#8a7560'),slab:standard('#c1b9ac'),oak:standard('#d1b78f'),carpet:standard('#b5b9b0'),frame:standard('#454c47',.35),terracotta:standard('#a5543e'),glass:new THREE.MeshPhysicalMaterial({color:'#d5e3df',roughness:.14,transparent:true,opacity:.17,depthWrite:false,metalness:.05,side:THREE.DoubleSide}),ceiling:standard('#f4f4ef')};mats.oak.map=texture('wood');mats.carpet.map=texture('carpet');mats.ceiling.side=THREE.DoubleSide;mats.ceiling.emissive.set('#d5d4c9');mats.ceiling.emissiveIntensity=.12;
 const geo=new THREE.BoxGeometry(1,1,1);
 function box(parent,name,x,n,w,d,h,bottom,mat){const o=new THREE.Mesh(geo,mat);o.name=name;o.position.set(x,bottom+h/2,-n);o.scale.set(w,h,d);o.castShadow=true;o.receiveShadow=true;parent.add(o);return o;}
 function segment(parent,a,b,height,bottom,mat,thickness=.13){const length=Math.hypot(b[0]-a[0],b[1]-a[1]);const o=box(parent,'Partition',(a[0]+b[0])/2,(a[1]+b[1])/2,length,thickness,height,bottom,mat);o.rotation.y=Math.atan2(b[1]-a[1],b[0]-a[0]);return o;}
 const footprint=config.footprintLocal;const shape=new THREE.Shape();footprint.forEach((p,i)=>i?shape.lineTo(...p):shape.moveTo(...p));shape.closePath();const slab=new THREE.Mesh(new THREE.ExtrudeGeometry(shape,{depth:.32,bevelEnabled:false}),mats.slab);slab.rotation.x=-Math.PI/2;slab.position.y=-.32;slab.receiveShadow=true;root.add(slab);
 const top=new THREE.Mesh(new THREE.ShapeGeometry(shape),standard(isOpenConcept?'#e2e4dd':'#bebeb5',.88));top.rotation.x=-Math.PI/2;top.position.y=.008;top.receiveShadow=true;root.add(top);
 if(isOpenConcept){const roof=new THREE.Mesh(new THREE.ExtrudeGeometry(shape,{depth:.10,bevelEnabled:false}),mats.ceiling);roof.name='White continuous ceiling';roof.rotation.x=-Math.PI/2;roof.position.y=3.7;roof.receiveShadow=true;roof.castShadow=false;ceiling.add(roof);}
 if(hasFacade)for(const source of facadeData.meshes){
  if(source.classification==='slab')continue;
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(source.positions,3));geometry.setIndex(source.triangles);
  // Flat normals preserve the authored narrow frame and terracotta edges.
  const flat=geometry.toNonIndexed();geometry.dispose();flat.computeVertexNormals();flat.computeBoundingSphere();
  const original=source.material||{},rgba=original.baseColorFactor||[.5,.5,.5,1];
  const material=source.surfaceType==='glass'?new THREE.MeshPhysicalMaterial({color:'#bdd2cb',roughness:.12,metalness:.05,transparent:true,opacity:.12,depthWrite:false,side:THREE.DoubleSide}):new THREE.MeshStandardMaterial({color:new THREE.Color().fromArray(rgba),roughness:original.roughnessFactor??.65,metalness:original.metallicFactor??0,side:THREE.DoubleSide});
  if(source.classification==='terracotta')material.color.set('#a04e38');
  const mesh=new THREE.Mesh(flat,material);mesh.name=source.sourceNodeName||source.id;mesh.userData.sourceNode=source.sourceNode;mesh.userData.classification=source.classification;mesh.castShadow=source.surfaceType!=='glass';mesh.receiveShadow=true;facade.add(mesh);diagnostics.sourceFacadeMeshCount++;
 }
 // Glazed terracotta perimeter; upper envelope is hidden in cutaway mode.
 if(!hasFacade)for(let i=0;i<footprint.length;i++){const a=footprint[i],b=footprint[(i+1)%footprint.length];segment(root,a,b,.18,0,mats.terracotta,.24);segment(upper,a,b,2.75,.18,mats.glass,.025);segment(upper,a,b,.18,2.93,mats.terracotta,.24);const len=Math.hypot(b[0]-a[0],b[1]-a[1]);for(let j=0;j<Math.ceil(len/2.5);j++){const t=j/Math.ceil(len/2.5);box(upper,'Terracotta facade fin',a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]),.12,.22,3.1,0,mats.terracotta);}}
 function place(item,x,n,rotation=0){item.position.set(x,0,-n);item.rotation.y=rotation;furniture.add(item);return item;}
 function wall(a,b,glazed=false){if(glazed){segment(root,a,b,.08,0,mats.frame,.08);segment(upper,a,b,2.92,.08,mats.glass,.035);segment(upper,a,b,.07,2.94,mats.frame,.08);const len=Math.hypot(b[0]-a[0],b[1]-a[1]);for(let i=0;i<=Math.ceil(len/1.3);i++){let t=i/Math.ceil(len/1.3);box(upper,'Glazing mullion',a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]),.045,.045,3.0,0,mats.frame)}}else{segment(root,a,b,.85,0,mats.wall);segment(upper,a,b,2.15,.85,mats.wall);segment(root,a,b,.08,.03,mats.trim,.15)}}
 function slattedSide(a,b,room,door){
  // Keep the complete 80 mm slat depth inside its zone and off circulation.
  const insetX=Math.abs(a[0]-b[0])<1e-8?Math.sign((room.rect[0]+room.rect[2])/2-a[0])*.04:0;
  const insetN=Math.abs(a[1]-b[1])<1e-8?Math.sign((room.rect[1]+room.rect[3])/2-a[1])*.04:0;
  a=[a[0]+insetX,a[1]+insetN];b=[b[0]+insetX,b[1]+insetN];
  const length=Math.hypot(b[0]-a[0],b[1]-a[1]),height=room.partitionHeight||2.5,width=room.slatWidth||.035,spacing=room.slatSpacing||.16,angle=Math.atan2(b[1]-a[1],b[0]-a[0]);
  const point=t=>[a[0]+(b[0]-a[0])*t/length,a[1]+(b[1]-a[1])*t/length];
  const gap=door?[(door.offset??length/2)-(door.width||1.4)/2,(door.offset??length/2)+(door.width||1.4)/2]:null;
  const spans=gap?[[0,Math.max(0,gap[0])],[Math.min(length,gap[1]),length]]:[[0,length]];
  for(const [start,end] of spans){if(end-start<width)continue;const p=point(start),q=point(end);segment(upper,p,q,.035,.015,lib.materials.oak,.08).name='Open slat bottom rail';segment(upper,p,q,.035,height-.035,lib.materials.oak,.08).name='Open slat top rail';
   for(let t=start+width/2;t<=end-width/2+1e-6;t+=spacing){const xy=point(t);box(upper,'Vertical pale oak slat',xy[0],xy[1],width,.08,height,0,lib.materials.oak).rotation.y=angle;diagnostics.slatCount++;}
  }
 }
 const wallIntervals=new Map();let roomKey='';function uniqueWall(a,b,glazed){const horizontal=Math.abs(a[1]-b[1])<1e-6,axis=horizontal?0:1,constant=horizontal?a[1]:a[0],key=roomKey+'|'+axis+'|'+constant.toFixed(5);const lo=Math.min(a[axis],b[axis]),hi=Math.max(a[axis],b[axis]);let pieces=[[lo,hi]];const previous=wallIntervals.get(key)||[];for(const [l,h]of previous){pieces=pieces.flatMap(([x,y])=>h<=x||l>=y?[[x,y]]:[[x,Math.min(l,y)],[Math.max(h,x),y]].filter(([u,v])=>v-u>1e-5));}for(const [l,h]of pieces){const p=horizontal?[l,constant]:[constant,l],q=horizontal?[h,constant]:[constant,h];wall(p,q,glazed);}previous.push([lo,hi]);wallIntervals.set(key,previous);}
 const descriptions={office:'Private workspace with timber desks, ergonomic chairs, storage and planting.',team:'A shared team studio with glazing that brings daylight into the corridor.',meeting:'A collaborative meeting space with a display, whiteboard and conference table.',lounge:'A relaxed space for conversation or reading.',pantry:'A shared kitchen and coffee area with storage, worktops and seating.',phone:'A quiet booth for short calls and focused work.',core:'Concept circulation and service spaces; positions have not been verified against as-built drawings.',open:'A flexible workspace with shared desks and low planting.',reception:'Reception and waiting area for visitors.'};
 for(const r of config.rooms){roomKey=r.rotationDeg?r.id:'';const before=[root,upper,furniture,ceiling].map(g=>new Set(g.children));const [x0,y0,x1,y1]=r.rect,w=x1-x0,d=y1-y0,cx=(x0+x1)/2,cy=(y0+y1)/2; r.description=r.description||descriptions[r.type];
 const roomMat=mats.carpet.clone();roomMat.color.set(r.color||({meeting:'#9da99e',office:'#b6b5a6',team:'#a7b1af',phone:'#a79c8c',lounge:'#a5af98',pantry:'#c4b79c'}[r.type]||'#c3bcae'));
 box(root,r.name+' floor',cx,cy,w-.15,d-.15,.018,.015,roomMat);
 picks.push({room:r,box:new THREE.Box3(new THREE.Vector3(x0,0,-y1),new THREE.Vector3(x1,3,-y0))});labels.push({room:r,position:new THREE.Vector3(cx,.10,-cy)});
 const enclosed=r.partition!=='open'&&r.partition!=='slats'&&!['open','common','lounge','reception'].includes(r.type);
 const sides={south:[[x0,y0],[x1,y0]],north:[[x0,y1],[x1,y1]],west:[[x0,y0],[x0,y1]],east:[[x1,y0],[x1,y1]]};
 if(r.partition==='slats')for(const side of r.partitionSides||[]){const pair=sides[side];if(pair)slattedSide(...pair,r,r.door?.side===side?r.door:null);}
 if(enclosed){if(!isOpenConcept)box(ceiling,'Ceiling',cx,cy,w,d,.12,3.13,mats.ceiling).castShadow=false;for(const [side,[a,b]] of Object.entries(sides)){const door=r.door?.side===side?r.door:null;const glazed=side===(r.door?.side||'east')&&r.type!=='core';if(door){const len=Math.hypot(b[0]-a[0],b[1]-a[1]);const offset=door.offset??len/2;const width=door.width||1.05;const point=t=>[a[0]+(b[0]-a[0])*t/len,a[1]+(b[1]-a[1])*t/len];const p=point(offset-width/2),q=point(offset+width/2);uniqueWall(a,p,glazed);uniqueWall(q,b,glazed);segment(upper,p,q,.28,2.72,mats.wall);const leaf=segment(upper,p,q,2.4,.1,mats.glass,.045);leaf.name='Glass door';for(const t of [offset-width/2,offset+width/2]){const pt=point(t);box(upper,'Door jamb',pt[0],pt[1],.055,.055,2.72,0,mats.frame)}// floor threshold and brass handle suggest an openable door
 segment(root,p,q,.018,.04,mats.trim,.12);
 }else uniqueWall(a,b,glazed)}}
 const plant=(x,y,size=.75)=>place(lib.plant({height:size}),x,y);
 if(['office','team','open'].includes(r.type)){const seats=Math.max(1,r.capacity||2);const cols=Math.max(1,Math.min(Math.floor((w-1.3)/1.9),seats));const rows=Math.ceil(seats/cols);for(let k=0;k<seats;k++){const col=k%cols,row=Math.floor(k/cols),x=cx+(col-(cols-1)/2)*1.9,y=cy+(row-(rows-1)/2)*2.45;place(lib.desk(),x,y);place(lib.chair(),x,y-1.0)}place(lib.shelf({width:Math.min(2.2,w-1.2)}),x0+.5+Math.min(2.2,w-1.2)/2,y1-.35);plant(x1-.65,y1-.7,1.3);if(w>5&&d>5)place(lib.whiteboard(),x0+.25,cy,Math.PI/2).position.y=1.0;}
 if(r.type==='meeting'){place(lib.meetingTable({seats:r.capacity||6,width:Math.min(4,w-2.5),depth:Math.min(1.5,d-2.4)}),cx,cy);place(lib.whiteboard(),x0+.23,cy,Math.PI/2).position.y=1.0;plant(x1-.6,y1-.65,1.4);}
 if(r.type==='phone'){place(lib.desk({width:1.1,depth:.55}),cx,y0+.45,Math.PI);place(lib.chair(),cx,y0+1.15,Math.PI);}
 if(r.type==='lounge'||r.type==='reception'){place(lib.rug({width:w-1,depth:d-1}),cx,cy);place(lib.sofa({width:Math.min(2.7,w-1)}),cx,cy+Math.min(1.1,d/2-.6));place(lib.coffeeTable(),cx,cy-.3);if(d>4)place(lib.sofa({width:1.55}),cx-1.7,cy-.6,Math.PI/2);plant(x1-.8,y1-.7,1.5);place(lib.lamp(),x0+.8,y1-.8);if(r.type==='reception')place(lib.desk({width:2.1}),cx-2.3,y0+1.1,Math.PI);}
 if(r.type==='common'){
  // Slim ceiling tracks follow the same axes as the glazing and common room.
  for(const offset of [-2.6,2.6]){box(ceiling,'Recessed ceiling track',cx,cy+offset,w-2.4,.10,.028,3.65,mats.frame);box(ceiling,'Warm linear ceiling light',cx,cy+offset,w-2.6,.055,.018,3.635,lib.materials.glow);}
  const pendantMaterial=new THREE.MeshStandardMaterial({color:'#f5f1e5',roughness:.45,emissive:'#fff2d9',emissiveIntensity:.32});
  const pendant=(x,y,width=1.6)=>{box(upper,'Common room pendant',x,y,width,.18,.075,2.9,pendantMaterial);for(const dx of [-width*.35,width*.35])box(upper,'Pendant suspension',x+dx,y,.008,.008,.72,2.98,mats.frame);};
  const armchair=(x,y,rotation=0,color='cream')=>place(lib.sofa({width:.87,seats:1,color}),x,y,rotation);
  for(const zone of r.furnitureZonesLocal||[]){const x=cx+zone.center[0],y=cy+zone.center[1],zw=zone.size[0],zd=zone.size[1];diagnostics.commonFurnitureZones++;diagnostics.commonSeating+=zone.seats||0;
   if(zone.type==='conversation'){
    place(lib.rug({width:zw-.25,depth:zd-.15,color:'#d3d0c4'}),x,y);
    place(lib.sofa({width:2.85,seats:3,color:'cream'}),x,y+1.18);
    place(lib.sofa({width:2.85,seats:3,color:zone.id.includes('east')?'sage':'cream'}),x,y-1.18,Math.PI);
    armchair(x-2.48,y,Math.PI/2,'cream');armchair(x+2.48,y,-Math.PI/2,'sage');
    place(lib.coffeeTable({width:1.25,depth:.7}),x-.37,y);
    place(lib.coffeeTable({width:.61,depth:.52,round:true}),x+.72,y+.13).scale.set(1,.82,1);
    plant(x-3.05,y+1.43,1.5);place(lib.lamp({height:1.75}),x+3.0,y+1.40);
    place(lib.plant({small:true,potColor:'ceramic'}),x+.72,y+.13).position.y=.38;
    pendant(x,y,1.8);
   }else if(zone.type==='communal_table'){
    place(lib.rug({width:zw-.25,depth:zd-.10,color:'#c8cec4'}),x,y);
    place(lib.meetingTable({width:4.8,depth:1.15,seats:8}),x,y);
    for(const dx of [-1.45,1.45]){const laptop=new THREE.Group();box(laptop,'Communal laptop base',0,0,.35,.24,.018,.80,lib.materials.chrome);box(laptop,'Communal laptop screen',0,.11,.35,.015,.22,.82,lib.materials.black);box(laptop,'Communal laptop display',0,.10,.32,.005,.19,.835,lib.materials.screen);place(laptop,x+dx,y,dx<0?0:Math.PI);}
    place(lib.plant({small:true,potColor:'ceramic'}),x,y).position.y=.80;pendant(x,y,3.8);
   }else if(zone.type==='reading'){
    place(lib.rug({width:zw-.2,depth:zd-.1,color:'#d7d4ca'}),x,y);
    for(const dx of [-1.05,1.05]){armchair(x+dx,y+.85,0,'cream');armchair(x+dx,y-.85,Math.PI,'sage');}
    place(lib.coffeeTable({width:.75,depth:.5}),x,y);
    place(lib.shelf({width:1.8,height:.93,levels:2,depth:.3}),x-2.60,y,Math.PI/2);
    place(lib.lamp({height:1.65}),x+2.5,y+.96);pendant(x,y,1.45);
   }else if(zone.type==='planting'){
    plant(x-.65,y+.55,1.85);plant(x+.65,y+.65,1.45);plant(x+.85,y-.5,.85);
    place(lib.coffeeTable({width:.58,depth:.48,round:true}),x-.65,y-.68);
   }
  }
 }
 if(r.type==='pantry'){place(lib.pantry({width:Math.min(w-1,4)}),cx,r.partition==='open'?y1-.55:y0+.55,r.partition==='open'?0:Math.PI);place(lib.meetingTable({seats:4,width:1.6,depth:1.1}),cx,cy-.5);plant(x0+.6,r.partition==='open'?y1-.6:y0+.6,1.3);}
 if(r.type==='core'){for(let i=0;i<12;i++)box(root,'Indicative stair',x0+1.15,y0+.4+i*.24,1.7,.24,.13*(i+1),0,mats.wall);box(root,'Service enclosure',x1-1.1,cy,1.5,1.6,2.65,0,mats.trim);}
 // Ceiling pendants keep the plan legible while giving every room a lighting rhythm.
 if(!['core','common'].includes(r.type)&&w>2.5){const emissive=new THREE.MeshStandardMaterial({color:'#fff2d4',emissive:'#fff0cf',emissiveIntensity:.9});box(upper,'Pendant luminaire',cx,cy,Math.min(w-1.5,2.3),.12,.07,2.82,emissive);for(const dx of [-.8,.8])box(upper,'Pendant cable',cx+dx,cy,.008,.008,.3,2.87,mats.frame);}
 // Rotate each furnished room about its centre, following its facade-oriented axes.
 if(r.rotationDeg){const angle=THREE.MathUtils.degToRad(r.rotationDeg);[root,upper,furniture,ceiling].forEach((parent,i)=>{const children=parent.children.filter(o=>!before[i].has(o));const pivot=new THREE.Group();pivot.name=r.name+' / facade axis';pivot.position.set(cx,0,-cy);parent.add(pivot);for(const child of children){parent.remove(child);child.position.sub(pivot.position);pivot.add(child);}pivot.rotation.y=angle;});}
 }
 // Presentation route is derived from the configured floor circulation, not simulated traffic.
 const routePaths=config.circulationRoute?[config.circulationRoute.points,...(config.circulationRoute.branches||[])]:[];
 const routeMaterial=new THREE.LineDashedMaterial({color:'#47675e',dashSize:.35,gapSize:.20,transparent:true,opacity:.65,depthWrite:false});
 for(const path of routePaths){const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(path.map(p=>new THREE.Vector3(p[0],.065,-p[1]))),routeMaterial);line.computeLineDistances();route.add(line);for(let i=1;i<path.length;i++){const a=path[i-1],b=path[i];const band=segment(route,a,b,.008,.028,new THREE.MeshStandardMaterial({color:'#d8d9d2',roughness:.85}),config.circulationRoute.width||2.4);band.castShadow=false;}}
 // Furnished circulation nooks and subtle human scale figures (conceptual occupants).
 const corridorPlants=config.corridorPlants||[];for(const p of corridorPlants)place(lib.plant({height:1.3}),p[0],p[1]);
 const ppl=config.people||routePaths.flatMap(path=>path.slice(1).map((p,i)=>[(p[0]+path[i][0])/2,(p[1]+path[i][1])/2])).slice(0,7);for(const p of ppl){const o=lib.human();o.position.set(p[0],0,-p[1]);people.add(o)}
 // Merge static furniture by material; retain source room data separately for picking.
 function batch(group){group.updateMatrixWorld(true);const buckets=new Map();group.traverse(o=>{if(!o.isMesh||Array.isArray(o.material))return;const g=(o.geometry.index?o.geometry.toNonIndexed():o.geometry.clone()).applyMatrix4(o.matrixWorld);const key=o.material.uuid;if(!buckets.has(key))buckets.set(key,{mat:o.material,geos:[],names:new Set()});const bucket=buckets.get(key);bucket.geos.push(g);bucket.names.add(o.name)});group.clear();for(const {mat,geos,names} of buckets.values()){try{const geometry=mergeGeometries(geos,false);if(!geometry)throw new Error('Could not merge office geometry');const mesh=new THREE.Mesh(geometry,mat);mesh.name=group.name+' / '+[...names].filter(Boolean).slice(0,3).join(', ');mesh.castShadow=true;mesh.receiveShadow=true;group.add(mesh)}finally{geos.forEach(g=>g.dispose())}}}
 batch(furniture);batch(people);batch(upper);
 upper.visible=false;ceiling.visible=false;
 return {group:root,route,upper,facade,ceiling,furniture,people,labels,picks,diagnostics,materials:mats,setWalls:visible=>upper.visible=visible,setFacade:visible=>facade.visible=visible,setPeople:visible=>people.visible=visible,dispose(){const materials=new Set(),textures=new Set();root.traverse(o=>{o.geometry?.dispose();if(o.material)for(const m of Array.isArray(o.material)?o.material:[o.material]){materials.add(m);if(m.map)textures.add(m.map);}});materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());lib.dispose?.();}};
}
