import test from 'node:test';
import assert from 'node:assert/strict';
import {compressGlb,writeGlb,readGlb} from './lossless.mjs';

function fixture() {
  const positions=new Float32Array(900);for(let i=0;i<positions.length;i++)positions[i]=i%3===1?0:(i%20)*.125;
  // Include negative zero: losslessness is bitwise, not approximate equality.
  positions[1]=-0;
  const indices=new Uint16Array(300);for(let i=0;i<indices.length;i++)indices[i]=i;
  const image=Buffer.from([0,1,2,3,4,5,6,7]);
  const bin=Buffer.concat([Buffer.from(positions.buffer),Buffer.from(indices.buffer),image]);
  return writeGlb({asset:{version:'2.0'},scene:0,scenes:[{nodes:[0]}],
    nodes:[{mesh:0,name:'preserved',translation:[2,3,4],extras:{entity_id:'building-1'}}],
    buffers:[{byteLength:bin.length,extras:{source:'test'}}],
    bufferViews:[{buffer:0,byteLength:positions.byteLength,target:34962},
      {buffer:0,byteOffset:positions.byteLength,byteLength:indices.byteLength,target:34963},
      {buffer:0,byteOffset:positions.byteLength+indices.byteLength,byteLength:image.length}],
    accessors:[{bufferView:0,componentType:5126,type:'VEC3',count:300,min:[0,0,0],max:[3,0,3]},
      {bufferView:1,componentType:5123,type:'SCALAR',count:300}],
    meshes:[{primitives:[{attributes:{POSITION:0},indices:1,material:0}]}],
    materials:[{name:'original',pbrMetallicRoughness:{baseColorFactor:[.2,.5,.7,1]}}],
    images:[{bufferView:2,mimeType:'image/png'}]},bin);
}
test('serialized lossless GLB preserves every view, indices, transforms and descriptors',async()=>{
  const source=fixture(),result=await compressGlb(source),before=readGlb(source),after=readGlb(result.bytes);
  assert(result.compressedViews>0);assert(result.bytes.length<source.length);assert.equal(result.triangles,100);
  for(const key of ['nodes','scenes','meshes','accessors','materials','images'])assert.deepEqual(after.json[key],before.json[key]);
  assert.deepEqual(after.json.buffers[0].extras,before.json.buffers[0].extras);
  assert(result.proofs.every(p=>p.sha256===p.decoded_sha256));
  assert(after.json.bufferViews.some(v=>v.extensions?.EXT_meshopt_compression.mode==='INDICES'));
  assert(after.json.bufferViews.every(v=>!v.extensions||v.extensions.EXT_meshopt_compression.filter==='NONE'));
});
test('source bytes are unchanged and compression is deterministic',async()=>{
  const source=fixture(),copy=Buffer.from(source),a=await compressGlb(source),b=await compressGlb(source);
  assert.deepEqual(source,copy);assert.deepEqual(a.bytes,b.bytes);
});
test('external buffers, compressed inputs and out-of-range views are rejected',async()=>{
  for(const change of [j=>j.buffers[0].uri='private.bin',j=>j.extensionsUsed=['KHR_draco_mesh_compression'],j=>j.bufferViews[0].byteLength=1e8]){
    const {json,bin}=readGlb(fixture());change(json);await assert.rejects(compressGlb(writeGlb(json,bin)));
  }
});
