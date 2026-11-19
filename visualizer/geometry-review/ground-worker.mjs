import * as THREE from './vendor/three/build/three.module.js';
// The worker uses the same triangle subdivision as the production site.
// Its dependency uses bare Three.js imports, resolved by the local module below.
import {sample} from './terrain.mjs';
import {terrainSurfaceGeometry} from './runtime/ground-surface.mjs';
let dem;
function crop(array,bounds) {
  if(!bounds)return array;
  const out=[];
  for(let i=0;i<array.length;i+=9){const xs=[array[i],array[i+3],array[i+6]],zs=[array[i+2],array[i+5],array[i+8]];
    if(Math.max(...xs)<bounds[0]||Math.min(...xs)>bounds[2]||Math.max(...zs)<bounds[1]||Math.min(...zs)>bounds[3])continue;
    for(let j=0;j<9;j++)out.push(array[i+j]);
  }return new Float32Array(out);
}
self.onmessage=({data})=>{if(data.type==='init'){dem=data.dem;return;}
  try{
    const g=terrainSurfaceGeometry(crop(new Float32Array(data.bytes),data.bounds));
    const pos=g.attributes.position,heights=new Float32Array(pos.count),temporary=new Float32Array(pos.count*3);
    for(let i=0;i<pos.count;i++){heights[i]=sample(dem,pos.getX(i),-pos.getZ(i));temporary[i*3]=pos.getX(i);temporary[i*3+1]=pos.getY(i)+heights[i];temporary[i*3+2]=pos.getZ(i);}
    g.setAttribute('position',new THREE.BufferAttribute(temporary,3));g.computeVertexNormals();g.setAttribute('position',pos);
    const result={position:pos.array,normal:g.attributes.normal.array,canopyHeight:heights};
    self.postMessage({id:data.id,result},Object.values(result).map(x=>x.buffer));
  }catch(error){self.postMessage({id:data.id,error:String(error)});}
};
