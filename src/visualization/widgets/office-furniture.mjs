import * as THREE from 'three';

/** Presentation-only, procedural interior assets. Local metres, Y up; desks face +Z.
 * All assets share geometry and materials. Dispose the library only after all its
 * groups have been removed. Pass {detail:false} to desks for distant furniture.
 */
export function createFurnitureLibrary({style='classic'}={}) {
  const modern=style==='modern';
  const geometries = new Map();
  const textures = [];
  const ownedMaterials = [];
  const unitBox = new THREE.BoxGeometry(1, 1, 1);
  geometries.set('box', unitBox);
  const cylinder = new THREE.CylinderGeometry(1, 1, 1, 16);
  geometries.set('cylinder', cylinder);
  const sphere = new THREE.SphereGeometry(1, 12, 8);
  geometries.set('sphere', sphere);
  const leaf = new THREE.SphereGeometry(1, 8, 5);
  geometries.set('leaf', leaf);
  let seed = 177;
  const random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  function texture(kind, variant = 0) {
    if (typeof document === 'undefined') return null;
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 256;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    if (kind === 'wood') {
      ctx.fillStyle = '#eee8dc'; ctx.fillRect(0, 0, 256, 256);
      for (let i = 0; i < 230; i++) {
        const x = random() * 256;
        ctx.strokeStyle = `rgba(${random() > .4 ? '129,113,91' : '255,253,244'},${.025 + random() * .07})`;
        ctx.lineWidth = .3 + random() * 1.2; ctx.beginPath(); ctx.moveTo(x, 0);
        ctx.bezierCurveTo(x + 6 * Math.sin(i), 80, x - 4 * Math.cos(i), 190, x + 2, 256); ctx.stroke();
      }
    } else if (kind === 'fabric') {
      ctx.fillStyle = '#f2f0ec'; ctx.fillRect(0, 0, 256, 256);
      for (let y = 0; y < 256; y += 3) { ctx.strokeStyle = 'rgba(75,68,57,.10)'; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(256, y); ctx.stroke(); }
      for (let x = 0; x < 256; x += 3) { ctx.strokeStyle = 'rgba(255,255,255,.16)'; ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, 256); ctx.stroke(); }
    } else if (kind === 'stone') {
      ctx.fillStyle = '#efefea'; ctx.fillRect(0, 0, 256, 256);
      for(let i=0;i<2600;i++) {ctx.fillStyle=`rgba(120,119,109,${.015+random()*.06})`;ctx.fillRect(random()*256,random()*256,.4+random()*1.8,.4+random()*1.8);}
    } else {
      // Three restrained, recognisable workspaces: analytics, document and CAD.
      ctx.fillStyle = '#eef0ed'; ctx.fillRect(0, 0, 256, 256);
      ctx.fillStyle = '#313b3b'; ctx.fillRect(0, 0, 256, 18);
      ctx.fillStyle = '#dce2dc'; ctx.fillRect(0,18,36,238);
      for(let i=0;i<7;i++){ctx.fillStyle=i===variant?'#879b90':'#b3beb5';ctx.fillRect(8,32+i*23,20,4);}
      ctx.fillStyle='#56675e';ctx.fillRect(49,32,104,6);
      if(variant===1){
        ctx.fillStyle='#fffefa';ctx.fillRect(66,51,155,191);
        ctx.fillStyle='#707a72';ctx.fillRect(81,67,98,5);
        for(let i=0;i<18;i++){ctx.fillStyle=i<3?'#a4afa7':'#b7beb7';ctx.fillRect(81,85+i*7, i%5===4?71:122,2);}
        ctx.fillStyle='#dce4da';ctx.fillRect(81,176,119,39);
      }else if(variant===2){
        ctx.fillStyle='#f9faf7';ctx.fillRect(47,49,198,190);
        ctx.strokeStyle='#dfe4de';ctx.lineWidth=.6;
        for(let i=0;i<13;i++){ctx.beginPath();ctx.moveTo(47+i*16,49);ctx.lineTo(47+i*16,239);ctx.moveTo(47,49+i*16);ctx.lineTo(245,49+i*16);ctx.stroke();}
        ctx.strokeStyle='#657e71';ctx.lineWidth=3;ctx.strokeRect(71,74,147,125);
        ctx.strokeRect(71,74,59,55);ctx.strokeRect(151,74,67,55);ctx.strokeRect(71,152,59,47);ctx.strokeRect(151,152,67,47);
        ctx.fillStyle='#b8c8bc';for(let i=0;i<4;i++){ctx.fillRect(81+i%2*82,87+Math.floor(i/2)*75,29,14);}
      }else{
        ctx.fillStyle='#fffefa';ctx.fillRect(47,56,190,112);ctx.fillRect(47,183,91,54);ctx.fillRect(146,183,91,54);
        ctx.strokeStyle='#dce1da';ctx.lineWidth=1;for(let i=0;i<4;i++){ctx.beginPath();ctx.moveTo(57,77+i*24);ctx.lineTo(226,77+i*24);ctx.stroke();}
        ctx.strokeStyle='#6f9482';ctx.lineWidth=3;ctx.beginPath();
        for(let i=0;i<8;i++){const x=57+i*24,y=142-i*7+Math.sin(i*2)*10;i?ctx.lineTo(x,y):ctx.moveTo(x,y);}ctx.stroke();
        for(let i=0;i<5;i++){ctx.fillStyle=i%2?'#b3c4b6':'#8aa492';ctx.fillRect(157+i*14,224-i*5,8,9+i*5);}
        ctx.fillStyle='#75897a';ctx.fillRect(58,199,52,4);ctx.fillStyle='#bdc7be';ctx.fillRect(58,214,67,3);
      }
    }
    const map = new THREE.CanvasTexture(canvas); map.colorSpace = THREE.SRGBColorSpace;
    map.wrapS = map.wrapT = THREE.RepeatWrapping; map.anisotropy = 4; textures.push(map); return map;
  }
  const woodMap = texture('wood'), fabricMap = texture('fabric'), stoneMap = texture('stone');
  const screenMaps = [0,1,2].map(variant => texture('screen',variant));
  const mat = (color, roughness = .7, metalness = 0, extra = {}) => {
    const result = new THREE.MeshStandardMaterial({color, roughness, metalness, ...extra}); ownedMaterials.push(result); return result;
  };
  const materials = {
    oak: mat('#eee9df', .60, 0, {map: woodMap}), walnut: mat('#9a8d7b', .60, 0, {map: woodMap}),
    white: mat('#eeefea', .70), paper: mat('#f8f8f1', .95), black: mat('#272d2d', .60),
    metal: mat('#303638', .42, .55), chrome: mat('#a8afac', .34, .75),
    fabric: mat('#969991', .94, 0, {map: fabricMap}), teal: mat('#788d7c', .94, 0, {map: fabricMap}),
    clay: mat('#b78d77', .94, 0, {map: fabricMap}), cream: mat('#d8d7ce', .95, 0, {map: fabricMap}),
    carpet: mat('#b7bab1', 1, 0, {map: fabricMap}), navy: mat('#566363', .96, 0, {map: fabricMap}),
    stone: mat('#e8e7df', .48, 0, {map:stoneMap}), concrete: mat('#bdbeb7', .90, 0, {map:stoneMap}),
    sage: mat('#879b85', .92, 0, {map:fabricMap}),
    terracotta: mat('#b28670', .86), ceramic: mat('#e1e0d6', .48), soil: mat('#302820', 1),
    leaf: mat('#43654a', .8), leafDark: mat('#234b3c', .78), leafLight: mat('#688363', .83),
    screen: mat('#ffffff', .42, 0, {map: screenMaps[0], emissive: '#dbe4de', emissiveMap: screenMaps[0], emissiveIntensity: .10}),
    glass: mat('#bcdddc', .12, .15, {transparent: true, opacity: .35}),
    coffee: mat('#39241b', .2), bookBlue: mat('#75888c'), bookRust: mat('#ac8c7c'),
    bookYellow: mat('#c1ba9c'), bookGrey: mat('#bdc3ba'), skin: mat('#b78565', .84),
    hair: mat('#3c302b', .92), glow: mat('#fff1d1', .3, 0, {emissive:'#ffdb9f', emissiveIntensity: .9}),
  };
  // Keep historic callers unchanged; the modern finish set is opt-in.
  if(modern){
    const finishes={oak:'#f1ece1',walnut:'#a19c90',white:'#f4f3ee',black:'#242a2b',metal:'#343b3c',chrome:'#c1c6c3',fabric:'#a3aaa4',teal:'#8b9e90',clay:'#c1a393',cream:'#e7e4da',carpet:'#c8ccc5',navy:'#646e70',stone:'#eeeee8',concrete:'#cfd1cb',sage:'#9ba997',ceramic:'#faf9f4'};
    for(const [key,color] of Object.entries(finishes))materials[key].color.set(color);
    materials.oak.roughness=.50;materials.stone.roughness=.43;materials.metal.roughness=.38;materials.chrome.roughness=.28;
  }
  materials.porcelain=mat(modern?'#fbfcf8':'#f1f3ed',.22);
  materials.brushedSteel=mat('#b8bfbc',.36,.8);
  materials.mirror=mat('#dbe2df',.08,.95);
  materials.water=mat('#d1e0da',.16,.08);
  for(const [name,material] of Object.entries(materials))material.name=`office-${style}-${name}`;
  const screenMaterials=[materials.screen,...screenMaps.slice(1).map(map=>mat('#ffffff',.42,0,{map,emissive:'#dbe4de',emissiveMap:map,emissiveIntensity:.10}))];
  let workstationCount=0;
  const customMaterials = new Map();
  const choose = (color, fallback) => {
    if (!color) return fallback;
    if (color.isMaterial) return color;
    if (materials[color]) return materials[color];
    if (!customMaterials.has(color)) customMaterials.set(color, mat(color, .85));
    return customMaterials.get(color);
  };
  function box(group, w, h, d, x, y, z, material = materials.white, radius = 0) {
    let geometry = unitBox;
    if (radius) {
      const r = Math.min(radius, w * .24, h * .24, d * .24);
      const key = ['rounded', w, h, d, r].join(':');
      geometry = geometries.get(key);
      if (!geometry) {
        const shape = new THREE.Shape(); const a = w / 2 - r, b = h / 2 - r;
        shape.moveTo(-a, -b); shape.lineTo(a, -b); shape.lineTo(a, b); shape.lineTo(-a, b); shape.closePath();
        geometry = new THREE.ExtrudeGeometry(shape, {depth:d - 2 * r, bevelEnabled:true, bevelSegments:2, steps:1, bevelSize:r, bevelThickness:r, curveSegments:2});
        geometry.translate(0, 0, -d / 2 + r); geometries.set(key, geometry);
      }
    }
    const mesh = new THREE.Mesh(geometry, material); if (!radius) mesh.scale.set(w, h, d);
    mesh.position.set(x, y, z); mesh.castShadow = mesh.receiveShadow = true; group.add(mesh); return mesh;
  }
  function cyl(group, radius, height, x, y, z, material = materials.metal) {
    const mesh = new THREE.Mesh(cylinder, material); mesh.scale.set(radius, height, radius); mesh.position.set(x, y, z);
    mesh.castShadow = mesh.receiveShadow = true; group.add(mesh); return mesh;
  }
  function ellipsoid(group, sx, sy, sz, x, y, z, material, geometry = sphere) {
    const mesh = new THREE.Mesh(geometry, material); mesh.scale.set(sx, sy, sz); mesh.position.set(x,y,z);
    mesh.castShadow = mesh.receiveShadow = true; group.add(mesh); return mesh;
  }
  function rod(group, from, to, radius, material = materials.metal) {
    const a = new THREE.Vector3(...from), b = new THREE.Vector3(...to), delta = b.clone().sub(a);
    const mesh = cyl(group, radius, delta.length(), ...(a.add(b).multiplyScalar(.5)).toArray(), material);
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0), delta.normalize()); return mesh;
  }
  function group(name, bounds) { const g = new THREE.Group(); g.name = name; g.userData.furniture = name; if (bounds) g.userData.nominalBounds = bounds; return g; }
  function add(parent, child, x, z, rotation = 0, y = 0) { child.position.set(x,y,z); child.rotation.y=rotation; parent.add(child); return child; }
  function mug(g, x,y,z, color = materials.ceramic) {
    cyl(g, .043,.09,x,y+.045,z,color); cyl(g,.034,.003,x,y+.092,z,materials.coffee);
    const key='mugHandle'; if (!geometries.has(key)) geometries.set(key,new THREE.TorusGeometry(.027,.008,5,12));
    const handle=new THREE.Mesh(geometries.get(key),color); handle.position.set(x+.048,y+.055,z); g.add(handle);
  }
  function book(g,x,y,z,w=.14,d=.2,h=.024,color=materials.bookRust) {
    box(g,w,h,d,x,y+h/2,z,color,.004); box(g,w-.009,h*.65,d-.012,x+.003,y+h/2,z,materials.paper);
  }
  function chair({color, arms=true, executive=false}={}) {
    const g=group('task-chair',[.65,1.05,.65]), fabric=choose(color,executive?materials.navy:materials.fabric);
    cyl(g,.045,.31,0,.29,0,materials.chrome); cyl(g,.085,.09,0,.12,0,materials.black);
    for(let i=0;i<5;i++) { const a=i*Math.PI*2/5; const x=Math.cos(a)*.27,z=Math.sin(a)*.27;
      rod(g,[0,.12,0],[x,.075,z],.022); const wheel=cyl(g,.035,.045,x,.044,z,materials.black); wheel.rotation.z=Math.PI/2;
    }
    box(g,.48,.10,.46,0,.47,0,fabric,.035);
    box(g,.46,executive?.57:.43,.065,0,executive?.83:.77,.205,fabric,.025).rotation.x=-.10;
    rod(g,[0,.38,.12],[0,.78,.23],.025,materials.black);
    if(executive) box(g,.29,.15,.07,0,1.08,.23,fabric,.03);
    if(arms) for(const s of [-1,1]) { rod(g,[s*.255,.45,.10],[s*.255,.65,.10],.018); box(g,.065,.045,.28,s*.255,.665,.02,materials.black,.014); }
    return g;
  }
  function desk({width=1.55, depth=.76, color, detail=true, chair:withChair=false, laptop=false, divider=false}={}) {
    const g=group('workstation',[width,.78,depth]), top=choose(color,materials.oak), y=.745;
    const displayMaterial=screenMaterials[workstationCount++%screenMaterials.length];
    box(g,width,.045,depth,0,y,0,top,.012);
    for(const s of [-1,1]) { const x=s*(width/2-.13); box(g,.055,.68,.055,x,.36,-depth*.32,materials.metal); box(g,.055,.68,.055,x,.36,depth*.32,materials.metal); box(g,.075,.045,depth*.82,x,.035,0,materials.metal,.008); }
    box(g,width-.22,.065,.045,0,.64,-depth*.31,materials.metal); box(g,width*.55,.07,.17,0,.62,-.14,materials.black);
    if(laptop) {
      box(g,.35,.018,.24,0,.783,-.06,materials.chrome,.008);
      const lid=box(g,.35,.24,.014,0,.90,-.177,materials.black,.006); lid.rotation.x=-.14;
      const display=box(g,.326,.208,.003,0,.90,-.167,displayMaterial); display.rotation.x=-.14;
    } else {
      box(g,.22,.014,.15,0,.776,-.21,materials.black,.008); box(g,.032,.17,.028,0,.86,-.245,materials.chrome);
      box(g,.55,.326,.032,0,1.06,-.258,materials.black,.012); box(g,.516,.288,.004,0,1.064,-.239,displayMaterial);
      box(g,.013,.004,.003,0,.911,-.237,materials.glow);
    }
    if(detail) {
      box(g,.47,.004,.30,.08,.772,.12,materials.navy,.008);
      box(g,.32,.014,.106,-.05,.783,.11,materials.black,.007);
      for(let row=0;row<4;row++) for(let col=0;col<10;col++) box(g,.021,.003,.015,-.18+col*.029,.792,.076+row*.022,materials.bookGrey);
      ellipsoid(g,.032,.018,.048,.274,.788,.12,materials.black);
      book(g,-width*.34,.77,.07,.19,.245,.025,materials.bookRust); box(g,.11,.002,.15,-width*.34,.799,.07,materials.paper);
      rod(g,[-width*.30,.806,-.01],[-width*.32,.806,.12],.003,materials.black); mug(g,width*.36,.77,-.12);
      cyl(g,.032,.09,-width*.38,.815,-.22,materials.terracotta);
      for(let i=0;i<3;i++) rod(g,[-width*.38+i*.012-.01,.80,-.22],[-width*.38+i*.012-.01,.92,-.22+i*.006],.003,materials.bookBlue);
    }
    if(divider) box(g,width-.04,.30,.035,0,.90,-depth/2,materials.fabric,.008);
    if(withChair) add(g,chair(),0,.72);
    return g;
  }
  function meetingTable({width=2.8,depth=1.15,seats=8,color,detail=true}={}) {
    const g=group('meeting-table',[width+.8,1.05,depth+1.15]);
    box(g,width,.065,depth,0,.755,0,choose(color,materials.oak),.028);
    for(const x of [-width*.28,width*.28]) { cyl(g,.10,.68,x,.36,0); box(g,.48,.035,.72,x,.035,0,materials.metal,.018); }
    box(g,.32,.008,.115,0,.792,0,materials.black,.01);
    const sideSeats=Math.floor((seats-2)/2);
    for(let i=0;i<sideSeats;i++) { const x=(i-(sideSeats-1)/2)*(width/(sideSeats+.3)); add(g,chair({color:'teal',arms:false}),x,depth/2+.37,0); add(g,chair({color:'teal',arms:false}),x,-depth/2-.37,Math.PI); }
    if(seats>=4) { add(g,chair({color:'teal',arms:false}),-width/2-.38,0,-Math.PI/2); add(g,chair({color:'teal',arms:false}),width/2+.38,0,Math.PI/2); }
    if(detail) for(let i=0;i<Math.min(sideSeats,3);i++) { const x=(i-(sideSeats-1)/2)*(width/(sideSeats+.3)); book(g,x,.79,.27,.2,.27,.015,materials.bookGrey); mug(g,x+.22,.79,-.27); }
    return g;
  }
  function sofa({width=2.1,color,seats=3}={}) {
    const g=group('sofa',[width,.88,.83]), fabric=choose(color,materials.teal);
    for(const x of [-width/2+.13,width/2-.13]) for(const z of [-.28,.28]) cyl(g,.028,.15,x,.09,z,materials.walnut);
    box(g,width-.08,.20,.75,0,.25,0,fabric,.055); box(g,width,.50,.16,0,.60,-.34,fabric,.055);
    for(const x of [-width/2+.09,width/2-.09]) box(g,.18,.41,.78,x,.46,0,fabric,.045);
    const seatW=(width-.42)/seats;
    for(let i=0;i<seats;i++) {const x=(i-(seats-1)/2)*(seatW+.012); box(g,seatW,.15,.58,x,.415,.07,fabric,.04); box(g,seatW,.35,.14,x,.66,-.20,fabric,.045).rotation.x=-.08;}
    const cushion=box(g,.34,.34,.12,-width*.31,.61,.02,materials.cream,.045); cushion.rotation.z=.17;cushion.rotation.x=-.24;
    const cushion2=box(g,.31,.31,.12,width*.30,.60,.01,materials.clay,.045);cushion2.rotation.z=-.18;cushion2.rotation.x=-.22;
    return g;
  }
  function coffeeTable({width=1.1,depth=.6,round=false}={}) {
    const g=group('coffee-table',[width,.44,depth]);
    if(round) cyl(g,width/2,.045,0,.43,0,materials.stone); else box(g,width,.045,depth,0,.43,0,materials.stone,.02);
    for(const x of [-width*.34,width*.34]) for(const z of [-depth*.30,depth*.30]) rod(g,[x,.41,z],[x*1.1,.02,z*1.1],.018);
    book(g,-.16,.455,.02,.22,.28,.028,materials.bookBlue); book(g,-.14,.485,.02,.20,.25,.023,materials.paper); mug(g,.25,.455,-.08);
    return g;
  }
  function plant({height=1.35,radius=.26,potColor,small=false}={}) {
    if(small) {height=.38;radius=.10;}
    const g=group('plant',[radius*3,height,radius*3]); const potH=height*.27;
    const key=`pot:${radius}:${potH}`;
    if(!geometries.has(key)) geometries.set(key,new THREE.CylinderGeometry(radius,radius*.78,potH,20));
    const pot=new THREE.Mesh(geometries.get(key),choose(potColor,small?materials.ceramic:materials.concrete));pot.position.y=potH/2;pot.castShadow=pot.receiveShadow=true;g.add(pot);
    cyl(g,radius*.87,.013,0,potH+.005,0,materials.soil);
    const leaves=small?8:14;
    for(let i=0;i<leaves;i++) {
      const angle=i*2.39996, h=potH+(height-potH)*(.36+.64*(i/(leaves-1))), spread=radius*(.75+.80*Math.sin(i*1.7));
      const x=Math.cos(angle)*spread,z=Math.sin(angle)*spread;
      rod(g,[0,potH*.8,0],[x,h,z],small?.004:.010,materials.leafDark);
      const mesh=ellipsoid(g,radius*.42,height*.14,radius*.105,x,h,z,[materials.leaf,materials.leafDark,materials.leafLight][i%3],leaf);
      mesh.rotation.set(Math.sin(angle)*.6,angle,Math.cos(angle)*.65);
    }
    return g;
  }
  function shelf({width=1.2,height=1.8,depth=.34,levels=4,color,books=true}={}) {
    const g=group('bookcase',[width,height,depth]), wood=choose(color,materials.oak);
    box(g,width,height,.024,0,height/2,-depth/2,materials.white);
    for(const x of [-width/2+.018,width/2-.018]) box(g,.036,height,depth,x,height/2,0,wood);
    for(let level=0;level<=levels;level++) {
      const y=.06+(height-.08)*level/levels; box(g,width,.03,depth,0,y,0,wood);
      if(books && level<levels) {const count=level%2?7:10;for(let i=0;i<count;i++) {
        const h=.20+((i*13+level*7)%9)*.014, w=.037+(i%3)*.012, x=-width/2+.09+i*.066;
        if(x>width*.22)break;
        box(g,w,h,depth*.65,x,y+h/2+.018,.005,[materials.bookBlue,materials.bookRust,materials.bookYellow,materials.bookGrey][(i+level)%4],.002);
        box(g,w*.7,.008,.003,x,y+h*.73,.005+depth*.326,materials.paper);
      }}
      if(level===1) {box(g,.25,.20,.25,width*.29,y+.12,0,materials.cream,.008);box(g,.08,.02,.003,width*.29,y+.14,.127,materials.black);}
      if(level===2) add(g,plant({small:true}),width*.28,0,0,y+.015);
    }
    return g;
  }
  function pantry({width=3,depth=.65}={}) {
    const g=group('pantry',[width,2.05,depth]);
    box(g,width,.78,depth-.04,0,.43,0,materials.white);
    box(g,width,.055,depth+.03,0,.85,0,materials.stone,.008);
    const n=Math.max(2,Math.round(width/.6));
    for(let i=0;i<n;i++) {const x=-width/2+(i+.5)*width/n;box(g,width/n-.014,.70,.025,x,.44,depth/2,materials.cream,.006);box(g,.16,.016,.023,x,.70,depth/2+.024,materials.metal,.005);}
    box(g,width,.08,.08,0,.05,depth/2-.08,materials.black);
    box(g,.53,.014,.39,-width*.25,.882,0,materials.chrome,.035);box(g,.43,.015,.29,-width*.25,.89,0,materials.metal,.025);
    rod(g,[-width*.25,.88,-.23],[-width*.25,1.16,-.23],.012,materials.chrome);rod(g,[-width*.25,1.16,-.23],[-width*.25,1.16,-.06],.012,materials.chrome);
    box(g,.38,.37,.34,width*.23,1.06,-.06,materials.black,.025);box(g,.30,.16,.025,width*.23,1.09,.118,materials.chrome,.012);
    box(g,.24,.013,.15,width*.23,.895,.13,materials.chrome);mug(g,width*.23,.90,.10);
    cyl(g,.012,.015,width*.30,1.185,.136,materials.glow).rotation.x=Math.PI/2;
    box(g,width-.4,.55,.29,0,1.72,-depth/2+.14,materials.oak,.012);
    for(let i=0;i<n;i++){const x=-(width-.4)/2+(i+.5)*(width-.4)/n;box(g,(width-.4)/n-.012,.52,.025,x,1.72,-.025,materials.white,.005);}
    box(g,width-.43,.018,.025,0,1.43,-.06,materials.glow);
    add(g,plant({small:true,potColor:'terracotta'}),width*.43,0,0,.88);
    mug(g,-.03,.88,.04,materials.clay);mug(g,.09,.88,.04,materials.teal);
    return g;
  }
  function whiteboard({width=1.5,height=.9,mobile=false}={}) {
    const g=group('whiteboard',[width,mobile?1.85:height,.07]); const y=mobile?1.34:height/2;
    box(g,width,height,.045,0,y,0,materials.chrome,.015);box(g,width-.045,height-.045,.012,0,y,.03,materials.paper,.006);
    box(g,width*.8,.024,.09,0,y-height/2-.015,.055,materials.chrome);
    for(let i=0;i<3;i++) box(g,.08,.008,.012,-width*.27+i*.12,y-height/2+.001,.07,[materials.bookBlue,materials.bookRust,materials.black][i]);
    for(let i=0;i<3;i++) {const x=-width*.31+i*width*.29;box(g,width*.19,.12,.002,x,y+.15,.038,[materials.bookBlue,materials.bookRust,materials.bookYellow][i]);box(g,.002,.17,.002,x,y-.015,.039,materials.bookGrey);}
    box(g,width*.7,.006,.002,0,y-.10,.039,materials.bookGrey);
    if(mobile) for(const x of [-width*.40,width*.40]){rod(g,[x,.06,0],[x,y-height/2,0],.016,materials.chrome);box(g,.07,.04,.55,x,.05,0,materials.chrome);}
    return g;
  }
  function human({seated=false,color='navy',skinColor}={}) {
    const g=group(seated?'seated-person':'standing-person',[.5,seated?1.24:1.76,.5]);const fabric=choose(color,materials.navy),skin=choose(skinColor,materials.skin);
    const hip=seated?.60:.94, shoulder=seated?1.01:1.37;
    ellipsoid(g,.20,.27,.115,0,(hip+shoulder)/2,0,fabric);
    cyl(g,.053,.11,0,shoulder+.08,0,skin);ellipsoid(g,.10,.136,.10,0,shoulder+.22,0,skin);ellipsoid(g,.102,.075,.104,0,shoulder+.30,-.015,materials.hair);
    for(const s of [-1,1]) {
      if(seated){rod(g,[s*.09,hip,0],[s*.10,.48,-.32],.065,fabric);rod(g,[s*.10,.48,-.32],[s*.10,.09,-.32],.046,materials.navy);ellipsoid(g,.065,.042,.12,s*.10,.055,-.38,materials.black);}
      else {rod(g,[s*.09,hip,0],[s*.10,.50,s*.04],.065,fabric);rod(g,[s*.10,.50,s*.04],[s*.12,.09,s*.04],.047,materials.navy);ellipsoid(g,.066,.044,.13,s*.12,.055,-.05+s*.04,materials.black);}
      rod(g,[s*.18,shoulder,0],[s*.24,shoulder-.21,-.06],.047,fabric);rod(g,[s*.24,shoulder-.21,-.06],[s*.18,shoulder-.26,seated?-.32:-.12],.037,skin);
      ellipsoid(g,.039,.027,.055,s*.18,shoulder-.26,seated?-.32:-.12,skin);
    }
    return g;
  }
  function rug({width=2.8,depth=2,color}={}) {
    const g=group('woven-rug',[width,.012,depth]);const base=choose(color,materials.carpet);
    box(g,width,.012,depth,0,.012,0,base,.003);
    for(const s of [-1,1]) box(g,width-.05,.002,.025,0,.019,s*(depth/2-.065),materials.cream);
    return g;
  }
  function printer() {
    const g=group('office-printer',[.62,1.02,.57]);
    box(g,.56,.70,.52,0,.36,0,materials.white,.018);box(g,.59,.18,.54,0,.78,0,materials.black,.022);
    box(g,.57,.06,.52,0,.90,0,materials.white,.02);box(g,.35,.035,.26,0,.945,.02,materials.white,.01);
    box(g,.37,.025,.21,0,.967,.02,materials.paper);box(g,.39,.08,.01,0,.62,.268,materials.black);
    for(const y of [.19,.39]){box(g,.49,.18,.018,0,y,.267,materials.white,.005);box(g,.16,.018,.02,0,y+.06,.28,materials.black);}
    const control=box(g,.14,.025,.10,.20,.91,.18,materials.screen,.004);control.rotation.x=.25;
    return g;
  }
  function lamp({height=1.65,color,desk=false}={}) {
    if(desk)height=.45;const g=group('floor-lamp',[height*.38,height,height*.38]); const m=choose(color,materials.metal);
    cyl(g,height*.12,.025,0,.018,0,m);rod(g,[0,.025,0],[0,height*.85,0],desk?.008:.014,m);
    const r=height*.16,key=`shade:${r}`;
    if(!geometries.has(key))geometries.set(key,new THREE.CylinderGeometry(r*.65,r,height*.18,24,1,true));
    const shade=new THREE.Mesh(geometries.get(key),materials.cream);shade.position.y=height*.89;shade.castShadow=true;g.add(shade);
    cyl(g,r*.92,.008,0,height*.80,0,materials.glow);return g;
  }
  /** Six-seat bench by default. Width/depth describe worktops; chairs add 1.68 m depth. */
  function hotDeskIsland({seats=6,width=4.8,depth=1.6}={}) {
    const count=Math.max(2,Math.floor(seats)),columns=Math.ceil(count/2),module=width/columns;
    const g=group('hot-desk-island',[width,1.22,depth+1.68]);
    g.userData.seats=count;g.userData.worktopBounds=[width,depth];
    for(let i=0;i<count;i++){
      const row=i<columns?0:1,col=i%columns,side=row===0?1:-1,x=(col-(columns-1)/2)*module;
      add(g,desk({width:module-.045,depth:depth/2-.025,detail:true}),x,side*depth/4,row?Math.PI:0);
      add(g,chair({color:modern?'cream':'fabric'}),x,side*(depth/2+.55),row?Math.PI:0);
    }
    box(g,width-.08,.32,.045,0,.91,0,materials.sage,.012).name='Shared acoustic divider';
    box(g,width-.24,.06,.12,0,.67,0,materials.metal,.008).name='Shared cable channel';
    for(const x of [-width/2+.12,width/2-.12])box(g,.06,.10,.10,x,.80,0,materials.metal,.008).name='Desktop power module';
    return g;
  }
  function lift({width=2.6,depth=2.6,height=3}={}) {
    const g=group('passenger-lift',[width,height,depth]),front=depth/2-.055,doorW=Math.min(1.4,width-.52),doorH=Math.min(2.3,height-.20),wall=.10;
    g.userData.front='+Z';g.userData.doorWidth=doorW;
    box(g,width,.065,depth,0,.0325,0,materials.stone).name='Lift cabin floor';
    box(g,width,height,wall,0,height/2,-depth/2+wall/2,materials.white).name='Lift back wall';
    for(const s of [-1,1]){
      box(g,wall,height,depth,s*(width/2-wall/2),height/2,0,materials.white).name='Lift side wall';
      const pier=(width-doorW)/2;box(g,pier,height,wall,s*(doorW/2+pier/2),height/2,front,materials.concrete).name='Lift entrance pier';
      box(g,.055,doorH+.08,.09,s*(doorW/2+.03),(doorH+.08)/2,front+.006,materials.brushedSteel).name='Brushed steel lift jamb';
      box(g,doorW/2-.009,doorH,.032,s*doorW/4,doorH/2+.025,front+.028,materials.brushedSteel,.008).name=s<0?'Left lift door':'Right lift door';
      rod(g,[s*(width/2-.14),.95,-depth/2+.20],[s*(width/2-.14),.95,depth/2-.30],.02,materials.chrome).name='Lift handrail';
    }
    box(g,doorW+.10,.07,.09,0,doorH+.07,front+.006,materials.brushedSteel).name='Lift door header';
    box(g,doorW,.02,.12,0,.025,front+.015,materials.chrome).name='Lift threshold';
    box(g,width,height-doorH-.10,wall,0,(height+doorH+.10)/2,front,materials.white).name='Lift entrance soffit';
    box(g,.34,.13,.018,0,doorH+.20,front+.065,materials.black,.012).name='Lift floor indicator';
    box(g,.014,.058,.004,.02,doorH+.20,front+.077,materials.glow).name='Lift level indicator';
    box(g,.09,.24,.02,doorW/2+.22,1.15,front+.06,materials.brushedSteel,.01).name='Lift call panel';
    for(const y of [1.105,1.195]){const b=cyl(g,.018,.008,doorW/2+.22,y,front+.076,materials.glow);b.rotation.x=Math.PI/2;b.name='Lift call button';}
    box(g,width*.62,.95,.018,0,1.48,-depth/2+.061,materials.mirror,.01).name='Cabin mirror';
    return g;
  }
  /** Straight flight; local +Z is the lower approach and -Z the upper landing. */
  function stair({width=2.4,depth=5.8,height=3.7,maxVisibleHeight=Infinity}={}) {
    if(!(maxVisibleHeight>0))throw new RangeError('maxVisibleHeight must be positive');
    const g=group('straight-stair',[width,Math.min(height+.95,maxVisibleHeight),depth]),steps=Math.max(2,Math.ceil(height/.175)),rise=height/steps,going=depth/steps;
    g.userData.riseHeight=height;g.userData.stepCount=steps;g.userData.riserHeight=rise;g.userData.treadDepth=going;g.userData.ascent='-Z';
    g.userData.oneFloorCut=Number.isFinite(maxVisibleHeight);g.userData.visibleStepCount=0;
    if(g.userData.oneFloorCut){g.userData.maxVisibleHeight=maxVisibleHeight;g.userData.presentationNote='Single-floor presentation cut of a conceptual stair; no code compliance is asserted.';}
    const clippedRod=(from,to,radius,material,name)=>{
      const limit=maxVisibleHeight-radius;let a=[...from],b=[...to];
      if(a[1]>limit&&b[1]>limit)return;
      if(a[1]>limit||b[1]>limit){const t=(limit-a[1])/(b[1]-a[1]),cross=a.map((value,i)=>value+t*(b[i]-value));if(a[1]>limit)a=cross;else b=cross;}
      if(new THREE.Vector3(...a).distanceToSquared(new THREE.Vector3(...b))<1e-10)return;
      rod(g,a,b,radius,material).name=name;
    };
    for(let i=0;i<steps;i++){
      const y=(i+1)*rise,z=depth/2-(i+.5)*going;
      if(y+.004>maxVisibleHeight)continue;
      g.userData.visibleStepCount++;
      box(g,width-.12,.07,going,0,y-.035,z,materials.stone,.007).name=`Stair tread ${i+1}`;
      box(g,width-.12,Math.max(.02,rise-.07),.025,0,i*rise+(rise-.07)/2,depth/2-i*going-.0125,materials.white).name=`Stair riser ${i+1}`;
      box(g,width-.16,.004,.018,0,y+.002,depth/2-i*going-.025,materials.metal).name='Nonslip tread nosing';
    }
    for(const s of [-1,1]){
      const x=s*(width/2-.07);
      clippedRod([x,.06,depth/2-.03],[x,height-.13,-depth/2+.03],.055,materials.metal,'Stair stringer');
      for(let i=0;i<steps;i+=3){const y=(i+1)*rise,z=depth/2-(i+.5)*going;clippedRod([x,y,z],[x,y+.90,z],.017,materials.metal,'Handrail upright');}
      clippedRod([x,rise+.90,depth/2-going/2],[x,height+.90,-depth/2+going/2],.023,materials.metal,'Continuous stair handrail');
      clippedRod([x,rise+.48,depth/2-going/2],[x,height+.48,-depth/2+going/2],.012,materials.metal,'Intermediate guard rail');
    }
    return g;
  }
  function wc({accessible=false}={}) {
    const g=group(accessible?'accessible-intent-wc':'toilet',[accessible?.88:.40,accessible?.83:.78,.74]),lift=accessible?.03:0;
    g.userData.front='+Z';g.userData.seatHeight=.47+lift;
    ellipsoid(g,.14,.18+lift,.22,0,.18+lift,.03,materials.porcelain).name='Porcelain pedestal';
    ellipsoid(g,.20,.14,.285,0,.31+lift,.07,materials.porcelain).name='Porcelain bowl';
    ellipsoid(g,.13,.012,.205,0,.447+lift,.095,materials.black).name='Bowl opening';
    const key='wc-seat-ring';if(!geometries.has(key))geometries.set(key,new THREE.TorusGeometry(.16,.017,8,28));
    const seat=new THREE.Mesh(geometries.get(key),materials.porcelain);seat.name='Toilet seat ring';seat.rotation.x=Math.PI/2;seat.scale.set(1.05,1.43,1);seat.position.set(0,.464+lift,.095);g.add(seat);
    box(g,.36,.43,.18,0,.555+lift,-.265,materials.porcelain,.035).name='Concealed-edge cistern';
    box(g,.37,.022,.19,0,.78+lift,-.265,materials.porcelain,.009).name='Cistern lid';
    const button=cyl(g,.022,.005,.09,.794+lift,-.265,materials.chrome);button.name='Dual flush control';
    if(accessible)for(const s of [-1,1]){rod(g,[s*.41,.78,-.23],[s*.41,.78,.34],.018,materials.chrome).name='WC support rail';rod(g,[s*.41,.48,-.23],[s*.41,.78,-.23],.018,materials.chrome).name='Rail rear support';}
    return g;
  }
  function washbasin({width=.65}={}) {
    const g=group('vanity-washbasin',[width,1.82,.53]);g.userData.front='+Z';
    box(g,width,.62,.48,0,.49,.012,materials.oak,.012).name='Floating vanity cabinet';
    box(g,width-.025,.29,.022,0,.49,.263,materials.white,.007).name='Handleless vanity drawer';
    box(g,width-.05,.008,.008,0,.645,.277,materials.metal).name='Drawer finger reveal';
    box(g,width+.01,.065,.52,0,.84,0,materials.porcelain,.025).name='Basin rim';
    ellipsoid(g,Math.max(.12,width*.34),.016,.17,0,.875,.025,materials.water).name='Basin recess';
    cyl(g,.018,.004,0,.893,.025,materials.chrome).name='Basin drain';
    rod(g,[0,.875,-.17],[0,1.055,-.17],.013,materials.chrome);rod(g,[0,1.055,-.17],[0,1.055,-.035],.013,materials.chrome);
    rod(g,[.025,.965,-.17],[.075,.965,-.17],.007,materials.chrome).name='Mixer lever';
    box(g,width-.02,.75,.027,0,1.43,-.247,materials.metal,.025).name='Mirror frame';
    box(g,width-.05,.72,.006,0,1.43,-.229,materials.mirror,.02).name='Vanity mirror';
    box(g,width-.10,.012,.014,0,1.82,-.222,materials.glow).name='Mirror task light';
    return g;
  }
  function fridge({width=.7,depth=.7,height=1.9}={}) {
    const g=group('fridge-freezer',[width,height,depth]);g.userData.front='+Z';
    box(g,width,height-.04,depth-.035,0,height/2+.02,-.0175,modern?materials.white:materials.brushedSteel,.02).name='Refrigerator cabinet';
    const split=height*.31,front=depth/2-.018;
    box(g,width-.025,split-.025,.035,0,split/2+.025,front,materials.white,.012).name='Freezer drawer';
    box(g,width-.025,height-split-.04,.035,0,(height+split)/2,front,materials.white,.012).name='Refrigerator door';
    box(g,.018,height*.29,.03,width*.33,height*.66,depth/2+.012,materials.metal,.006).name='Refrigerator handle';
    box(g,width*.52,.018,.03,0,split-.055,depth/2+.012,materials.metal,.006).name='Freezer handle';
    box(g,.11,.045,.005,0,height*.83,depth/2+.003,materials.black,.006).name='Temperature display';
    box(g,.025,.012,.003,.015,height*.83,depth/2+.007,materials.glow).name='Temperature indicator';
    box(g,width-.08,.04,depth-.08,0,.02,0,materials.black).name='Appliance plinth';
    return g;
  }
  function kitchenette({width=8,depth=.7}={}) {
    if(width<3.4)throw new RangeError('Kitchenette width must be at least 3.4 m for the requested appliances');
    const g=group('integrated-kitchenette',[width,2.13,depth+.04]),fridgeW=.70,workW=width-fridgeW-.12,workCenter=-fridgeW/2-.06;
    g.userData.front='+Z';g.userData.appliances=['fridge','coffee-machine','sink','microwave','dishwasher'];
    const left=-width/2,right=left+workW,top=.91;
    box(g,workW,.79,depth-.05,workCenter,.47,-.015,materials.white,.01).name='Kitchen base cabinetry';
    box(g,workW,.055,depth,workCenter,top-.0275,0,materials.stone,.012).name='Stone kitchen counter';
    box(g,workW,.08,.07,workCenter,.045,depth/2-.08,materials.metal).name='Recessed kitchen plinth';
    const modules=Math.max(3,Math.round(workW/.60));
    for(let i=0;i<modules;i++){const x=left+(i+.5)*workW/modules;box(g,workW/modules-.015,.74,.025,x,.48,depth/2-.01,modern?materials.oak:materials.cream,.005).name='Handleless kitchen door';box(g,workW/modules-.06,.018,.015,x,.815,depth/2+.012,materials.metal).name='Cabinet finger pull';}
    box(g,workW,.48,.025,workCenter,1.16,-depth/2+.015,materials.stone).name='Stone backsplash';
    const sinkX=left+workW*.64,coffeeX=left+workW*.14,microX=left+workW*.37,dishX=right-.34;
    box(g,.59,.012,.45,sinkX,top+.006,.015,materials.chrome,.025).name='Sink rim';
    box(g,.47,.013,.33,sinkX,top+.014,.015,materials.metal,.025).name='Sink basin';
    cyl(g,.022,.004,sinkX,top+.023,.015,materials.chrome).name='Sink drain';
    rod(g,[sinkX,top,-.23],[sinkX,top+.29,-.23],.014,materials.chrome);rod(g,[sinkX,top+.29,-.23],[sinkX,top+.29,-.04],.014,materials.chrome);
    box(g,.42,.40,.38,coffeeX,top+.20,-.04,materials.black,.023).name='Espresso machine';
    box(g,.32,.17,.018,coffeeX,top+.25,.159,materials.brushedSteel,.01).name='Coffee machine fascia';
    box(g,.27,.015,.16,coffeeX,top+.012,.18,materials.chrome,.005).name='Coffee drip tray';
    mug(g,coffeeX,top+.025,.16);box(g,.09,.055,.006,coffeeX,top+.29,.171,materials.screen,.005).name='Coffee touchscreen';
    box(g,.52,.30,.42,microX,top+.15,-.04,materials.brushedSteel,.015).name='Microwave cabinet';
    box(g,.39,.23,.015,microX-.035,top+.15,.179,materials.black,.012).name='Microwave door';
    box(g,.015,.17,.02,microX+.19,top+.15,.193,materials.chrome,.004).name='Microwave handle';
    box(g,.58,.74,.033,dishX,.48,depth/2+.005,materials.brushedSteel,.009).name='Integrated dishwasher';
    box(g,.48,.04,.01,dishX,.78,depth/2+.025,materials.black,.005).name='Dishwasher control strip';
    box(g,.25,.018,.03,dishX,.70,depth/2+.03,materials.metal,.005).name='Dishwasher handle';
    const fridgeX=width/2-fridgeW/2;add(g,fridge({width:fridgeW,depth,height:2.0}),fridgeX,0);
    const shelfW=Math.max(.8,workW-.12);box(g,shelfW,.42,.30,workCenter,1.82,-depth/2+.15,materials.white,.012).name='Upper kitchen cabinets';
    for(let i=1;i<modules;i++)box(g,.009,.38,.005,left+i*workW/modules,1.82,-depth/2+.303,materials.metal).name='Upper cabinet reveal';
    box(g,shelfW-.08,.014,.023,workCenter,1.595,-depth/2+.25,materials.glow).name='Undercabinet task light';
    if(workW>4.0){add(g,plant({small:true}),left+workW*.53,.02,0,top);mug(g,left+workW*.65,top,.11,materials.sage);}
    return g;
  }
  function locker({width=2.4,height=1.8,depth=.45}={}) {
    const g=group('personal-lockers',[width,height,depth+.025]),columns=Math.max(2,Math.round(width/.4)),rows=2,cw=width/columns,rh=(height-.09)/rows;
    g.userData.front='+Z';g.userData.compartments=columns*rows;
    box(g,width,height-.04,depth,0,height/2+.02,0,materials.white,.008).name='Locker carcass';
    box(g,width-.08,.06,depth-.06,0,.03,0,materials.metal).name='Locker recessed plinth';
    for(let i=0;i<columns;i++)for(let j=0;j<rows;j++){
      const x=-width/2+(i+.5)*cw,y=.075+(j+.5)*rh;
      box(g,cw-.015,rh-.015,.022,x,y,depth/2+.005,(i+j)%4===0?materials.sage:materials.oak,.005).name=`Locker ${i+1}-${j+1}`;
      box(g,.026,.075,.013,x+cw*.31,y,depth/2+.023,materials.metal,.004).name='Locker digital latch';
      box(g,.046,.018,.004,x-cw*.27,y+rh*.35,depth/2+.02,materials.paper).name='Locker number plaque';
    }
    return g;
  }
  function receptionDesk({width=2.6,depth=.75}={}) {
    const g=group('reception-desk',[width,1.56,depth]);g.userData.front='+Z';
    box(g,width-.09,.91,depth-.07,0,.505,0,materials.oak,.025).name='Reception desk body';
    box(g,width-.23,.06,depth-.15,0,.03,0,materials.metal).name='Reception recessed plinth';
    box(g,width,.07,depth,0,1.085,0,materials.stone,.025).name='Reception counter';
    box(g,width-.04,.73,.025,0,.66,depth/2-.012,materials.white,.012).name='Warm white reception front';
    box(g,width-.20,.045,.025,0,.135,depth/2-.025,materials.metal).name='Reception shadow gap';
    box(g,width*.42,.025,depth*.55,-width*.17,.80,-depth*.22,materials.oak,.01).name='Staff worktop';
    box(g,.33,.22,.022,-width*.19,.94,-depth*.20,materials.black,.01).name='Reception display';
    box(g,.30,.19,.004,-width*.19,.94,-depth*.215,materials.screen).name='Staff screen';
    box(g,.16,.012,.10,-width*.19,.82,-depth*.12,materials.metal,.004).name='Display stand';
    add(g,plant({small:true,potColor:'ceramic'}),width*.33,0,0,1.12);
    book(g,width*.12,1.12,.05,.19,.24,.018,materials.bookGrey);
    return g;
  }
  // Furniture is static. Bake its small parts into one mesh per material, and
  // cache the result so repeated workstations share the same GPU buffers.
  function batch(g) {
    g.updateMatrixWorld(true);
    const buckets = new Map();
    g.traverse(mesh => {
      if (!mesh.isMesh) return;
      const list = buckets.get(mesh.material) || [];
      list.push(mesh); buckets.set(mesh.material, list);
    });
    const merged = [];
    const p = new THREE.Vector3(), n = new THREE.Vector3(), nm = new THREE.Matrix3();
    for (const [material, meshes] of buckets) {
      const key = 'batch:' + meshes.map(mesh => mesh.geometry.uuid + ':' + mesh.matrixWorld.elements.join(',')).join('|');
      let geo = geometries.get(key);
      if (!geo) {
        const count = meshes.reduce((sum, mesh) => sum + (mesh.geometry.index?.count ?? mesh.geometry.attributes.position.count), 0);
        const positions = new Float32Array(count * 3), normals = new Float32Array(count * 3), uvs = new Float32Array(count * 2);
        let offset = 0;
        for (const mesh of meshes) {
          const source = mesh.geometry, index = source.index, position = source.attributes.position, normal = source.attributes.normal, uv = source.attributes.uv;
          nm.getNormalMatrix(mesh.matrixWorld);
          const length = index?.count ?? position.count;
          for (let i = 0; i < length; i++) {
            const vertex = index ? index.getX(i) : i;
            p.fromBufferAttribute(position, vertex).applyMatrix4(mesh.matrixWorld); p.toArray(positions, offset * 3);
            n.fromBufferAttribute(normal, vertex).applyNormalMatrix(nm); n.toArray(normals, offset * 3);
            if (uv) { uvs[offset * 2] = uv.getX(vertex); uvs[offset * 2 + 1] = uv.getY(vertex); }
            offset++;
          }
        }
        geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geo.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
        geo.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
        geo.computeBoundingBox(); geo.computeBoundingSphere(); geometries.set(key, geo);
      }
      const mesh = new THREE.Mesh(geo, material); mesh.name = g.name+' / '+(material.name||'surface');mesh.userData.parts=[...new Set(meshes.map(part=>part.name).filter(Boolean))]; mesh.castShadow = mesh.receiveShadow = true; merged.push(mesh);
    }
    g.clear(); g.add(...merged);
    const bounds=new THREE.Box3().setFromObject(g);g.userData.actualBounds={min:bounds.min.toArray(),max:bounds.max.toArray(),size:bounds.getSize(new THREE.Vector3()).toArray()};g.userData.style=style;
    return g;
  }
  function dispose(){for(const geo of geometries.values())geo.dispose();for(const material of ownedMaterials)material.dispose();for(const map of textures)map.dispose();}
  const factories = {desk,chair,meetingTable,sofa,coffeeTable,shelf,plant,pantry,whiteboard,human,rug,printer,lamp,hotDeskIsland,lift,stair,wc,washbasin,fridge,kitchenette,locker,receptionDesk};
  return {materials,...Object.fromEntries(Object.entries(factories).map(([name, factory]) => [name, options => batch(factory(options))])),dispose};
}
