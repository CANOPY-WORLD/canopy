import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const three=new URL('../site/vendor/three/build/three.module.js',import.meta.url).href;
const THREE=await import(three);
async function moduleAt(name){
 const source=(await readFile(new URL('../site/viewer/3d/'+name,import.meta.url),'utf8')).replace("from 'three'",`from '${three}'`);
 return import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
}
test('short source segments retain a complete stripe and road alignment filtering',async()=>{
 const {createRoadCrossings}=await moduleAt('road-crossings.js'),previous=globalThis.fetch;
 globalThis.fetch=async()=>new Response(JSON.stringify({features:[{line_enu_m:[[0,0],[.2,0],[.5,0],[1,0]]}],attribution:'synthetic'}));
 try{
  const terrain={match:()=>({height:10,distance:0})};
  const mesh=await createRoadCrossings({url:'synthetic',terrain});
  const p=mesh.geometry.attributes.position;let area=0;
  for(let i=0;i<p.count;i+=3){
   const a=new THREE.Vector3().fromBufferAttribute(p,i),b=new THREE.Vector3().fromBufferAttribute(p,i+1),c=new THREE.Vector3().fromBufferAttribute(p,i+2);
   area+=b.sub(a).cross(c.sub(a)).length()/2;
  }
  assert(Math.abs(area-1.5)<1e-5,'The 0.5 m stripe must survive split source segments');
  for(let i=0;i<p.count;i++)assert(Math.abs(p.getY(i)-10.04)<1e-5);
  const rejected=await createRoadCrossings({url:'synthetic',terrain:{match:()=>({height:10,distance:10})}});
  assert.equal(rejected.geometry.attributes.position.count,0);
  for(const object of [mesh,rejected]){const elevated=object.geometry;object.setTerrain(false);object.geometry.dispose();elevated.dispose();object.material.dispose();}
 }finally{globalThis.fetch=previous;}
});
test('unknown signal phases never illuminate all three lenses',async()=>{
 const {trafficSignalAsset}=await moduleAt('source-traffic-signal.js');
 const group=trafficSignalAsset.build({THREE,kit:{mat:(color,options)=>new THREE.MeshStandardMaterial({color,...options})}});
 group.traverse(object=>{if(object.isMesh){assert.equal(object.material.emissive.getHex(),0);object.geometry.dispose();object.material.dispose();}});
});
