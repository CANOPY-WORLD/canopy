import {test} from 'node:test';
import assert from 'node:assert/strict';
import {roadContactPolicy,contactTriangles} from '../site/viewer/3d/road-contact.mjs';
import {readFile} from 'node:fs/promises';
import {gzipSync} from 'node:zlib';

test('ordinary roads meet DEM exactly despite the display offset',()=>{
 const a=[0,0,10],b=[10,0,10];
 for(const ground of [8,12]){
  const triangles=contactTriangles(a,b,()=>ground,.22);
  assert.equal(triangles.length,6);
  assert.equal(triangles[2][2]+.22,ground);
  assert.equal(triangles[5][2]+.22,ground);
  assert.deepEqual(a,[0,0,10]);assert.deepEqual(b,[10,0,10]);
 }
 assert.equal(contactTriangles(a,b,()=>10,.22).length,6);
 assert.equal(contactTriangles(a,b,()=>10.22,.22).length,0);
});

test('bridge and positive-level clearances extend through connected junctions',()=>{
 for(const metadata of [{structure:['bridge']},{level:1},{structure:['tunnel']},{structure:['covered']}]){
  const p=roadContactPolicy({edges:[{from:'a',to:'b',...metadata},{from:'c',to:'d'}],junctions:[{id:'a'},{id:'c'}]});
  assert.equal(p.lane({edge:0}),false);assert.equal(p.lane({edge:1}),true);
  assert.equal(p.lane({edge:null,junction:0}),false);assert.equal(p.lane({edge:null,junction:1}),true);
  assert.equal(p.junction({id:'b'}),false);assert.equal(p.junction({id:'c'}),true);
  assert.equal(p.lane({edge:null}),false);
 }
});

test('cut/fill transitions split at the intersection',()=>{
 const triangles=contactTriangles([0,0,10],[10,0,10],x=>x===0?9.22:11.22,.22);
 assert.deepEqual(triangles[1],[5,0,10]);
 assert.deepEqual(triangles[3],[5,0,10]);
});

test('rendered lane and junction seams meet terrain and exclude bridge geometry',async()=>{
 const three=new URL('../site/vendor/three/build/three.module.js',import.meta.url).href;
 const contact=new URL('../site/viewer/3d/road-contact.mjs',import.meta.url).href;
 const source=(await readFile(new URL('../site/viewer/3d/corridor-terrain.js',import.meta.url),'utf8'))
  .replace("from 'three'",`from '${three}'`)
  .replace("import {enhanceGroundMaterial} from './ground-materials.js';",'const enhanceGroundMaterial=()=>{};')
  .replace("from './road-contact.mjs'",`from '${contact}'`);
 const module=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
 const grid={nx:2,ny:2,x0:0,y0:0,dx:100,base_m:8,scale_m:.01,z:Buffer.alloc(8).toString('base64'),source:{name:'synthetic'}};
 const network={edges:[{from:'a',to:'b'},{from:'c',to:'d',structure:['bridge']}],
  lanes:[{edge:0,width:2,shape:[[0,0,10],[10,0,10]]},{edge:1,width:2,shape:[[20,0,20],[30,0,20]]}],
  junctions:[{id:'a',shape:[[0,0,10],[1,0,10],[0,1,10]]},{id:'c',shape:[[20,0,20],[21,0,20],[20,1,20]]}]};
 const previousFetch=globalThis.fetch,previousWindow=globalThis.window;
 globalThis.window={};
 globalThis.fetch=async url=>new Response(url.endsWith('.gz')?gzipSync(JSON.stringify(network)):JSON.stringify({terrain:grid,road_surface:grid}));
 try{
  await module.loadCorridorTerrain(path=>path);
  const root=module.createElevatedRoads(),seam=root.getObjectByName('Terrain-to-road display seams');
  const p=seam.geometry.attributes.position,h=seam.geometry.attributes.canopyHeight;
  assert.equal(p.count,30); // Two lane edges and three junction edges, six vertices each.
  for(let i=0;i<p.count;i++){
   assert(p.getX(i)<=10,'Bridge geometry must remain unsupported');
   const y=p.getY(i)+h.getX(i);
   assert(Math.abs(y-8)<1e-5||Math.abs(y-10.22)<1e-5);
  }
  for(const child of root.children){child.geometry.dispose();child.material.dispose();}
 }finally{globalThis.fetch=previousFetch;globalThis.window=previousWindow;}
});
