// Shared CPU geometry preparation: the main-thread fallback and Worker use identical operations.
import * as THREE from '../../vendor/three/build/three.module.js';

export function buildSurfaceArrays(original, elevated, dem) {
  const {data, h} = dem;
  function sample(x, north) {
    const u=Math.max(0,Math.min(data.nx-1,(x-data.x0)/data.dx)),v=Math.max(0,Math.min(data.ny-1,(north-data.y0)/data.dx)),a=Math.min(data.nx-2,Math.floor(u)),b=Math.min(data.ny-2,Math.floor(v)),fx=u-a,fy=v-b,k=b*data.nx+a;
    return h[k]*(1-fx)*(1-fy)+h[k+1]*fx*(1-fy)+h[k+data.nx]*(1-fx)*fy+h[k+data.nx+1]*fx*fy;
  }
  const terrain = terrainSurfaceGeometry(new Float32Array(elevated));
  const position = terrain.attributes.position, heights = new Float32Array(position.count);
  for (let i=0;i<position.count;i++) heights[i]=sample(position.getX(i),-position.getZ(i));
  terrain.setAttribute('canopyHeight',new THREE.BufferAttribute(heights,1));
  terrainNormals(terrain);
  const flat = new THREE.BufferGeometry();
  flat.setAttribute('position',new THREE.BufferAttribute(new Float32Array(original),3));
  flat.setAttribute('canopyHeight',new THREE.BufferAttribute(new Float32Array(original.byteLength/12),1));
  flat.computeVertexNormals();
  const arrays = geometry => Object.fromEntries(Object.entries(geometry.attributes).map(([name, attr]) => [name, attr.array]));
  return {terrain:arrays(terrain), flat:arrays(flat)};
}

export function terrainNormals(g){const original=g.attributes.position,temporary=new Float32Array(original.count*3),h=g.attributes.canopyHeight;for(let i=0;i<original.count;i++){temporary[i*3]=original.getX(i);temporary[i*3+1]=original.getY(i)+h.getX(i);temporary[i*3+2]=original.getZ(i)}g.setAttribute('position',new THREE.BufferAttribute(temporary,3));g.computeVertexNormals();g.setAttribute('position',original);}
// Split existing vector triangles; source boundary coordinates and holes remain intact.
export function terrainSurfaceGeometry(array,base=false){
 const out=[];function emit(a,b,c){const ab=(a[0]-b[0])**2+(a[2]-b[2])**2,bc=(b[0]-c[0])**2+(b[2]-c[2])**2,ca=(c[0]-a[0])**2+(c[2]-a[2])**2;
  if(Math.max(ab,bc,ca)<=400){out.push(...a,...b,...c);return}
  let u=a,v=b,w=c;if(bc>=ab&&bc>=ca){u=b;v=c;w=a}else if(ca>=ab&&ca>=bc){u=c;v=a;w=b}const mid=u.map((x,i)=>(x+v[i])/2);emit(u,mid,w);emit(mid,v,w);
 }
 if(base){const y=array[1];for(let x=-4096;x<4096;x+=20)for(let z=-4096;z<4096;z+=20){const xx=Math.min(x+20,4096),zz=Math.min(z+20,4096);out.push(x,y,z,xx,y,z,xx,y,zz,x,y,z,xx,y,zz,x,y,zz)}}
 else for(let i=0;i<array.length;i+=9)emit(Array.from(array.subarray(i,i+3)),Array.from(array.subarray(i+3,i+6)),Array.from(array.subarray(i+6,i+9)));
 const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(out,3));g.computeVertexNormals();return g;
}
