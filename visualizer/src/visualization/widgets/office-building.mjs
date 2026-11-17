/** Full authored building in the office's local frame. No new exterior geometry is inferred. */
import * as THREE from 'three';

export function createOfficeBuilding(data, config) {
  if (!Array.isArray(data?.meshes) || !data.meshes.length) throw new Error('The building model contains no meshes.');
  if (!Array.isArray(data.originENU) || data.originENU.some((value, i) => Math.abs(value - config.originENU[i]) > 1e-6)) {
    throw new Error('The building and office coordinate origins do not match.');
  }
  const group = new THREE.Group(), envelope = new THREE.Group(), marker = new THREE.Group();
  group.name = 'I-HUB / complete authored building'; envelope.name = 'Original building exterior';
  marker.name = 'Concept office floor location'; group.add(envelope, marker);
  const geometries = new Set(), materials = new Set();
  const clipPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), -.34);
  const diagnostics = {sourceMeshCount:0, vertexCount:0, triangleCount:0, sourceNodes:[], mode:'building',
    coordinateFrame:'Office-local Three.js: east, up, -north', originENU:[...data.originENU],
    cutawayHeightLocal:-.34, revealProgress:0, exteriorStatus:'Existing authored model; not an as-built survey'};
  const ownMaterial = value => {materials.add(value); return value;};
  const ownGeometry = value => {geometries.add(value); return value;};
  for (const source of data.meshes) {
    if (!source.positions?.length || source.positions.length % 3 || !source.triangles?.length || source.triangles.length % 3) {
      throw new Error('Invalid building mesh: ' + source.id);
    }
    const positions = new Float32Array(source.positions.length);
    for (let i=0; i<positions.length; i+=3) {
      const x=source.positions[i], north=source.positions[i+1], up=source.positions[i+2];
      if (![x,north,up].every(Number.isFinite)) throw new Error('Non-finite building coordinates.');
      positions[i]=x; positions[i+1]=up; positions[i+2]=-north;
    }
    if (source.triangles.some(i=>!Number.isInteger(i)||i<0||i>=positions.length/3)) throw new Error('Invalid building index.');
    const indexed = new THREE.BufferGeometry();
    indexed.setAttribute('position',new THREE.BufferAttribute(positions,3)); indexed.setIndex(source.triangles);
    // Flat normals preserve the narrow authored ribs, frames and coping edges.
    const geometry=ownGeometry(indexed.toNonIndexed()); indexed.dispose(); geometry.computeVertexNormals(); geometry.computeBoundingBox();
    const original=source.material||{}, rgba=original.baseColorFactor||[.45,.45,.45,1];
    const isGlass=source.surfaceType==='glass'||source.classification==='glass';
    const material=ownMaterial(new THREE.MeshStandardMaterial({
      color:new THREE.Color().fromArray(rgba), roughness:original.roughnessFactor??(isGlass?.22:.72),
      metalness:original.metallicFactor??(isGlass?.12:0), side:THREE.DoubleSide,
      transparent:(rgba[3]??1)<1, opacity:rgba[3]??1, depthWrite:(rgba[3]??1)>=1,
      clipShadows:true
    }));
    const mesh=new THREE.Mesh(geometry,material); mesh.name=source.sourceNodeName||source.id;
    mesh.userData={sourceNode:source.sourceNode,classification:source.classification,surfaceType:source.surfaceType};
    mesh.castShadow=!isGlass; mesh.receiveShadow=true; envelope.add(mesh);
    // GTAO uses an override material that cannot honour this envelope's clip plane.
    // Render the authored context in the beauty pass, outside the office AO layer.
    mesh.layers.set(1);
    diagnostics.sourceMeshCount++; diagnostics.vertexCount+=positions.length/3; diagnostics.triangleCount+=source.triangles.length/3;
    if (!diagnostics.sourceNodes.includes(source.sourceNode)) diagnostics.sourceNodes.push(source.sourceNode);
  }
  envelope.updateMatrixWorld(true);
  const bounds = new THREE.Box3().setFromObject(envelope), groundY=bounds.min.y;
  diagnostics.boundsThree={min:bounds.min.toArray(),max:bounds.max.toArray()};
  const stroke=ownMaterial(new THREE.MeshBasicMaterial({color:'#ebc88d',transparent:true,opacity:.88,depthTest:false,depthWrite:false}));
  const cylinder=ownGeometry(new THREE.CylinderGeometry(.085,.085,1,6));
  const edge=(a,b)=>{
    const direction=new THREE.Vector3().subVectors(b,a),length=direction.length(); if(length<1e-5)return;
    const mesh=new THREE.Mesh(cylinder,stroke);mesh.position.copy(a).add(b).multiplyScalar(.5);
    mesh.scale.y=length;mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),direction.normalize());
    mesh.layers.set(1);mesh.renderOrder=12;marker.add(mesh);return mesh;
  };
  const bandTop=config.floorSelection?.floorToFloorM??3.92;
  const outline=config.footprintLocal.map(([x,n])=>new THREE.Vector3(x,.06,-n));
  for(let i=0;i<outline.length;i++) {
    const a=outline[i],b=outline[(i+1)%outline.length];edge(a,b);
    edge(a.clone().setY(bandTop),b.clone().setY(bandTop));
    if(i===0||i===2||i===8||i===11)edge(a,a.clone().setY(bandTop));
  }
  const surfaceMaterial=ownMaterial(new THREE.MeshBasicMaterial({color:'#e2b870',transparent:true,opacity:.085,side:THREE.DoubleSide,depthTest:false,depthWrite:false}));
  const shape=new THREE.Shape(config.footprintLocal.map(([x,n])=>new THREE.Vector2(x,n)));
  const surface=new THREE.Mesh(ownGeometry(new THREE.ShapeGeometry(shape)),surfaceMaterial);
  surface.rotation.x=-Math.PI/2;surface.position.y=.05;surface.layers.set(1);surface.renderOrder=11;marker.add(surface);
  let clipping=false;
  function setClipping(enabled) {
    if(clipping===enabled)return;
    clipping=enabled;
    for(const mesh of envelope.children) {
      mesh.material.clippingPlanes=enabled?[clipPlane]:null;
      mesh.material.needsUpdate=true;
    }
  }
  function setReveal(progress) {
    if(!Number.isFinite(progress))throw new Error('Building reveal progress must be finite.');
    const t=THREE.MathUtils.clamp(progress,0,1);
    group.visible=true;
    setClipping(t>0);
    clipPlane.constant=THREE.MathUtils.lerp(bounds.max.y+.4,diagnostics.cutawayHeightLocal,t);
    marker.visible=t<.96;
    stroke.opacity=.88*(1-t);surfaceMaterial.opacity=.085*(1-t);
    diagnostics.revealProgress=t;diagnostics.clipHeightLocal=clipPlane.constant;
    diagnostics.mode=t===0?'building':t===1?'cutaway':'transition';
  }
  function setMode(mode) {
    if (!['building','cutaway','floor'].includes(mode)) throw new Error('Unknown building view: '+mode);
    if(mode==='floor'){group.visible=false;marker.visible=false;}
    else setReveal(mode==='cutaway'?1:0);
    diagnostics.mode=mode;
  }
  function dispose() {group.removeFromParent();for(const geometry of geometries)geometry.dispose();for(const material of materials)material.dispose();group.clear();}
  group.userData=diagnostics;setMode('building');
  return {group,envelope,marker,bounds,groundY,setMode,setReveal,dispose,diagnostics};
}
