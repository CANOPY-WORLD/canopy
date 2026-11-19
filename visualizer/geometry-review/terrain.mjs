// Review adapter: identical terrain grid interpolation and building height shader
// to site/viewer/3d/corridor-terrain.js. No solver or new elevation estimate.
import * as THREE from './vendor/three/build/three.module.js';
export function grid(data) {
  const raw=Uint8Array.from(atob(data.z),c=>c.charCodeAt(0)),dv=new DataView(raw.buffer),h=new Float32Array(data.nx*data.ny);
  if(raw.length!==h.length*2)throw Error('Terrain sample count mismatch');
  for(let i=0;i<h.length;i++)h[i]=data.base_m+data.scale_m*dv.getInt16(i*2,true);
  return {data,h};
}
export function sample(dem,x,north) {
  const {data,h}=dem;
  const u=Math.max(0,Math.min(data.nx-1,(x-data.x0)/data.dx)),v=Math.max(0,Math.min(data.ny-1,(north-data.y0)/data.dx)),a=Math.min(data.nx-2,Math.floor(u)),b=Math.min(data.ny-2,Math.floor(v)),fx=u-a,fy=v-b,k=b*data.nx+a;
  return h[k]*(1-fx)*(1-fy)+h[k+1]*fx*(1-fy)+h[k+data.nx]*(1-fx)*fy+h[k+data.nx+1]*fx*fy;
}
const patched=new WeakSet();
export function patch(material) {
  if(patched.has(material))return;patched.add(material);const previous=material.onBeforeCompile;
  material.onBeforeCompile=(shader,renderer)=>{previous?.call(material,shader,renderer);shader.vertexShader='attribute float canopyHeight;\n'+shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\ntransformed.y += canopyHeight;');};
  const key=material.customProgramCacheKey.bind(material);material.customProgramCacheKey=()=>key()+'|review-terrain-v1';material.needsUpdate=true;
}
export function drape(root,dem) {
  root.updateWorldMatrix(true,true);const p=new THREE.Vector3();
  root.traverse(mesh=>{if(!mesh.isMesh||mesh.isInstancedMesh||!mesh.geometry.attributes.position)return;
    const g=mesh.geometry,pos=g.attributes.position,h=new Float32Array(pos.count),sy=mesh.matrixWorld.elements[5];
    if(Math.abs(mesh.matrixWorld.elements[4])+Math.abs(mesh.matrixWorld.elements[6])>1e-5)throw Error('Unsupported tilted building transform');
    for(let i=0;i<pos.count;i++){p.fromBufferAttribute(pos,i).applyMatrix4(mesh.matrixWorld);h[i]=sample(dem,p.x,-p.z)/sy;}
    g.setAttribute('canopyHeight',new THREE.BufferAttribute(h,1));
    (Array.isArray(mesh.material)?mesh.material:[mesh.material]).forEach(patch);
    g.computeBoundingBox();g.boundingBox.min.y-=5/Math.abs(sy);g.boundingBox.max.y+=75/Math.abs(sy);g.computeBoundingSphere();g.boundingSphere.radius+=75/Math.abs(sy);
  });
}
