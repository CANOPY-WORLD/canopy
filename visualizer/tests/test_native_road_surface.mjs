import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
async function load(){
 const three=new URL('../site/vendor/three/build/three.module.js',import.meta.url).href;
 const code=(await readFile(new URL('../site/viewer/3d/native-road-surface.js',import.meta.url),'utf8')).replace("from 'three'",`from '${three}'`);
 return import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
}
test('junction boundary matches road ends without mutating source heights or joining bridge levels',async()=>{
 const {nativeRoadTriangles}=await load();
 const data={lanes:[{shape:[[0,0,.45],[10,0,.45]],width:4}],junctions:[{shape:[[10,-2,.1],[12,-2,.1],[12,2,.1],[10,2,.1]]}]};
 const original=JSON.stringify(data),triangles=nativeRoadTriangles(data);
 for(let i=18;i<triangles.length;i+=3)if(triangles[i]===10)assert(Math.abs(triangles[i+1]-.47)<1e-12);
 assert.equal(JSON.stringify(data),original);
 data.lanes[0].to_junction='connected';data.junctions[0].id='connected';
 data.junctions[0].shape.forEach(p=>p[2]=2);
 const connected=nativeRoadTriangles(data);for(let i=18;i<connected.length;i+=3)if(connected[i]===10)assert(Math.abs(connected[i+1]-.47)<1e-12);
 data.junctions[0].id='unrelated';
 data.junctions[0].shape.forEach(p=>p[2]=5);
 const bridge=nativeRoadTriangles(data);for(let i=18;i<bridge.length;i+=3)assert.equal(bridge[i+1],5.02);
});
test('adjacent curved lane strips share identical seam vertices',async()=>{
 const {nativeRoadTriangles}=await load();
 const points=nativeRoadTriangles({lanes:[{shape:[[0,0,0],[10,0,0],[15,5,0]],width:4}],junctions:[]});
 assert.deepEqual(points.slice(6,9),points.slice(18,21));
 assert.deepEqual(points.slice(12,15),points.slice(21,24));
 assert(points.every(Number.isFinite));
});

test('paint follows the upper overlapping road surface without jumping to another level',async()=>{
 const {roadHeightAt}=await load();
 const tri=z=>[0,z+.02,0,10,z+.02,0,0,z+.02,-10];
 assert(Math.abs(roadHeightAt([...tri(.4),...tri(.6),...tri(5)],1,1,.4)-.6)<1e-12);
 assert.equal(roadHeightAt(tri(.6),20,20,.4),.4);
});
