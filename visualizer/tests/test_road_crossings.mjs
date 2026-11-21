import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const threeURL=new URL('../site/vendor/three/build/three.module.js',import.meta.url).href;
const source=(await readFile(new URL('../site/viewer/3d/road-crossings.js',import.meta.url),'utf8')).replace("'three'",JSON.stringify(threeURL));
const {createRoadCrossings}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
test('crossing stripes follow source path, switch height and reject unmatched roads',async()=>{
 const originalFetch=globalThis.fetch;
 try {
  globalThis.fetch=async()=>({ok:true,json:async()=>({attribution:'test',features:[{line_enu_m:[[0,0],[5,0]]}]})});
  const terrain={match:()=>({height:10,distance:0})};
  const mesh=await createRoadCrossings({url:'https://example.test/crossings.json',terrain});
  assert.equal(mesh.userData.stripes,5);assert(Math.abs(mesh.geometry.attributes.position.getY(0)-10.29)<1e-5);
  mesh.setTerrain(false);assert(Math.abs(mesh.geometry.attributes.position.getY(0)-.29)<1e-5);
  terrain.match=()=>({height:10,distance:null});
  const excluded=await createRoadCrossings({url:'https://example.test/crossings.json',terrain});assert.equal(excluded.userData.stripes,0);
 } finally {globalThis.fetch=originalFetch;}
});
