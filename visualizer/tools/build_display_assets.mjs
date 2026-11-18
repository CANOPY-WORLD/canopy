#!/usr/bin/env node
// Generate a separate, reproducible display derivative of the published London
// geometry. Source files and scientific fields are never modified.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {gzipSync, gunzipSync} from 'node:zlib';
import {fileURLToPath} from 'node:url';

const options=Object.fromEntries(process.argv.slice(2).reduce((pairs,arg,i,args)=>i%2?pairs:[...pairs,[arg,args[i+1]]],[]));
if(!options['--source']||!options['--output']||!options['--dependencies'])throw Error('Usage: node build_display_assets.mjs --source <snapshot> --output <new directory> --dependencies <npm prefix>');
if(Number(process.versions.node.split('.')[0])<22)throw Error('Display export requires Node.js 22 or later');
const source=await fs.realpath(options['--source']),requestedOutput=path.resolve(options['--output']);
const output=path.join(await fs.realpath(path.dirname(requestedOutput)),path.basename(requestedOutput));
if(output===source||output.startsWith(source+path.sep))throw Error('Output must be outside the immutable source snapshot');
const dependencies=await fs.realpath(options['--dependencies']);
const versions={'@gltf-transform/core':'4.3.0','@gltf-transform/extensions':'4.3.0','@gltf-transform/functions':'4.3.0',meshoptimizer:'0.24.0'};
for(const [name,version] of Object.entries(versions)){
 const installed=JSON.parse(await fs.readFile(path.join(dependencies,'node_modules',name,'package.json')));
 if(installed.version!==version)throw Error(`Expected ${name}@${version}; install the locked display-asset dependencies`);
}
await fs.mkdir(output,{recursive:false}); // Never overwrite an earlier derivative.
const require=createRequire(path.join(dependencies,'package.json'));
const {NodeIO,Document}=require('@gltf-transform/core');
const {ALL_EXTENSIONS,EXTMeshoptCompression}=require('@gltf-transform/extensions');
const {dedup,dequantize,palette,join,weld,simplify,meshopt,reorder,quantize,prune,getBounds}=require('@gltf-transform/functions');
const {MeshoptEncoder,MeshoptDecoder,MeshoptSimplifier}=require('meshoptimizer');
await Promise.all([MeshoptEncoder.ready,MeshoptDecoder.ready,MeshoptSimplifier.ready]);
const io=new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.encoder':MeshoptEncoder,'meshopt.decoder':MeshoptDecoder});
const hash=b=>createHash('sha256').update(b).digest('hex');
const manifestBytes=await fs.readFile(path.join(source,'manifest.json'));
const manifest=JSON.parse(manifestBytes),entries=new Map(manifest.files.map(f=>[f.path,f]));
const inputs=[];
async function read(name){
 const item=entries.get(name);if(!item)throw Error('Undeclared input: '+name);
 const resolved=await fs.realpath(path.join(source,name));if(!resolved.startsWith(source+path.sep))throw Error('Input escapes snapshot');
 const bytes=await fs.readFile(resolved);if(bytes.length!==item.bytes||hash(bytes)!==item.sha256)throw Error('Input checksum mismatch: '+name);
 inputs.push({path:name,bytes:bytes.length,sha256:item.sha256});
 return name.endsWith('.gz')?gunzipSync(bytes):bytes;
}
const json=async name=>JSON.parse(await read(name));
function stats(doc){
 const primitives=doc.getRoot().listMeshes().flatMap(m=>m.listPrimitives());
 return {nodes:doc.getRoot().listNodes().length,primitives:primitives.length,
  triangles:primitives.reduce((n,p)=>n+(p.getIndices()?.getCount()??p.getAttribute('POSITION').getCount())/3,0),
  accessor_bytes:doc.getRoot().listAccessors().reduce((n,a)=>n+(a.getArray()?.byteLength??0),0),
  bounds_y_up:getBounds(doc.getRoot().getDefaultScene()??doc.getRoot().listScenes()[0])};
}
const files=[];
async function write(name,bytes){await fs.writeFile(path.join(output,name),bytes);files.push({path:name,bytes:bytes.length,sha256:hash(bytes)});}
async function writeGLB(name,doc){
 const bytes=await io.writeBinary(doc);await write(name,bytes);await write(name+'.gz',gzipSync(bytes,{level:9}));
 // Read the actual encoded file back, including Meshopt decoding.
 const decoded=await io.readBinary(bytes);return {...stats(decoded),glb_bytes:bytes.length,gzip_bytes:files.at(-1).bytes};
}

const buildings=await io.readBinary(new Uint8Array(await read('models/buildings.glb.gz')));
const buildingAttribution=structuredClone(buildings.getRoot().getAsset());
const buildingBefore=stats(buildings);
await buildings.transform(dequantize(),dedup(),palette({min:2}),join({keepMeshes:true}),weld(),
 simplify({simplifier:MeshoptSimplifier,ratio:0.5,error:0.0001,lockBorder:true}),prune(),
 meshopt({encoder:MeshoptEncoder,level:'medium',quantizePosition:16,quantizeNormal:10,quantizeTexcoord:12}));
const buildingAfter=await writeGLB('buildings.glb',buildings);
console.log('Buildings',JSON.stringify({before:buildingBefore,after:buildingAfter}));

const terrain=await json('context/terrain/terrain.json');
const dem=terrain.terrain,raw=Buffer.from(dem.z,'base64');
if(raw.length!==dem.nx*dem.ny*2)throw Error('Unexpected terrain sample count');
function height(x,z){
 const u=Math.max(0,Math.min(dem.nx-1,(x-dem.x0)/dem.dx)),v=Math.max(0,Math.min(dem.ny-1,(-z-dem.y0)/dem.dx));
 const a=Math.min(dem.nx-2,Math.floor(u)),b=Math.min(dem.ny-2,Math.floor(v)),fx=u-a,fy=v-b,k=b*dem.nx+a;
 const h=i=>dem.base_m+dem.scale_m*raw.readInt16LE(i*2);
 return h(k)*(1-fx)*(1-fy)+h(k+1)*fx*(1-fy)+h(k+dem.nx)*(1-fx)*fy+h(k+dem.nx+1)*fx*fy;
}
const land=await json('context/vector_landscape/manifest.json');
const ground=new Document(),buffer=ground.createBuffer(),scene=ground.createScene('Display ground');
ground.getRoot().setDefaultScene(scene);
const surfaceReport=[];
for(const layer of land.layers){
 const name='context/terrain/'+(layer.name==='unclassified-base'?'unclassified-base-exposed.f32.gz':layer.file+'.gz');
 const bytes=await read(name),array=new Float32Array(bytes.buffer,bytes.byteOffset,bytes.byteLength/4),positions=[];
 function emit(a,b,c){
  const lengths=[[a,b,c],[b,c,a],[c,a,b]].map(([u,v,w])=>({u,v,w,d:(u[0]-v[0])**2+(u[2]-v[2])**2}));
  const edge=lengths.reduce((a,b)=>b.d>a.d?b:a);
  let error=Infinity;
  if(edge.d<=1600){const hs=[height(a[0],a[2]),height(b[0],b[2]),height(c[0],c[2])];error=0;
   for(const w of [[.5,.5,0],[0,.5,.5],[.5,0,.5],[1/3,1/3,1/3]]){const x=w[0]*a[0]+w[1]*b[0]+w[2]*c[0],z=w[0]*a[2]+w[1]*b[2]+w[2]*c[2];error=Math.max(error,Math.abs(w.reduce((s,v,i)=>s+v*hs[i],0)-height(x,z)));}}
  if(edge.d<=25||(edge.d<=1600&&error<=.5)){positions.push(...a,...b,...c);return;}
  const m=edge.u.map((x,i)=>(x+edge.v[i])/2);emit(edge.u,m,edge.w);emit(m,edge.v,edge.w);
 }
 for(let i=0;i<array.length;i+=9)emit([...array.subarray(i,i+3)],[...array.subarray(i+3,i+6)],[...array.subarray(i+6,i+9)]);
 const pos=new Float32Array(positions),normals=new Float32Array(pos.length),heights=new Float32Array(pos.length/3);
 for(let i=0;i<heights.length;i++)heights[i]=height(pos[3*i],pos[3*i+2]);
 let maxError=0,sumError=0,samples=0;
 for(let i=0;i<pos.length;i+=9){
  const a=[pos[i],pos[i+1]+heights[i/3],pos[i+2]],b=[pos[i+3],pos[i+4]+heights[i/3+1],pos[i+5]],c=[pos[i+6],pos[i+7]+heights[i/3+2],pos[i+8]];
  const u=b.map((x,k)=>x-a[k]),v=c.map((x,k)=>x-a[k]);const n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],length=Math.hypot(...n)||1;
  for(let k=0;k<3;k++)normals.set(n.map(x=>x/length),i+3*k);
  // Vertical interpolation error at edge midpoints and centroid against the
  // same DEM sampler. This is a sampled diagnostic, not a global error bound.
  for(const weights of [[.5,.5,0],[0,.5,.5],[.5,0,.5],[1/3,1/3,1/3]]){
   const x=weights[0]*a[0]+weights[1]*b[0]+weights[2]*c[0],z=weights[0]*a[2]+weights[1]*b[2]+weights[2]*c[2];
   const interpolated=weights.reduce((s,w,k)=>s+w*heights[i/3+k],0),error=Math.abs(interpolated-height(x,z));
   maxError=Math.max(maxError,error);sumError+=error;samples++;
  }
 }
 const accessor=(type,values)=>ground.createAccessor().setType(type).setArray(values).setBuffer(buffer);
 const color=layer.color.match(/[a-f0-9]{2}/gi).map(v=>parseInt(v,16)/255);
 const material=ground.createMaterial(layer.name).setBaseColorFactor([...color,1]).setMetallicFactor(0).setRoughnessFactor(1).setDoubleSided(true);
 const heightCodes=Int16Array.from(heights,h=>{const code=Math.round(h*100);if(code < -32768||code >32767)throw Error('Terrain height exceeds centimetre encoding');return code;});
 // Encode the raised surface as ordinary GLB geometry, so external GLB viewers
 // display the terrain correctly without Canopy's optional flattening shader.
 for(let i=0;i<heights.length;i++)pos[3*i+1]+=heights[i];
 const primitive=ground.createPrimitive().setAttribute('POSITION',accessor('VEC3',pos)).setAttribute('NORMAL',accessor('VEC3',normals)).setAttribute('_CANOPY_HEIGHT',accessor('SCALAR',heightCodes)).setMaterial(material);
 scene.addChild(ground.createNode(layer.name).setExtras({canopy_height_scale_m:.01,canopy_base_elevation:1}).setMesh(ground.createMesh(layer.name).addPrimitive(primitive)));
 surfaceReport.push({name:layer.name,source_triangles:array.length/9,display_triangles:pos.length/9,max_sampled_vertical_error_m:maxError,mean_sampled_vertical_error_m:sumError/samples});
 console.log('Ground',layer.name,pos.length/9,'triangles');
}
await ground.transform(quantize({pattern:/^(POSITION|NORMAL)$/,quantizePosition:16,quantizeNormal:8}),weld(),reorder({encoder:MeshoptEncoder}));
// Height codes are already bounded centimetres; exclude custom attributes from
// generic quantization. Meshopt coding itself preserves these integer values.
ground.createExtension(EXTMeshoptCompression).setRequired(true).setEncoderOptions({method:EXTMeshoptCompression.EncoderMethod.QUANTIZE});
const groundAfter=await writeGLB('ground.glb',ground);
const placements=await json('context/vector_landscape/source/scene-meta.json');
await write('placements.json.gz',gzipSync(Buffer.from(JSON.stringify({trees:placements.trees,fixtures:{hedge:placements.fixtures.hedge},placements:placements.placements})),{level:9}));
const report={schema_version:'1.0.0',kind:'canopy.display-derivative',scenario_id:manifest.scenario_id,
 source_snapshot:manifest.snapshot,source_manifest_sha256:hash(manifestBytes),source_files:inputs,
 source_attribution:{buildings:buildingAttribution,land_cover:land.source_metadata,terrain:terrain.terrain.source},
 generator:{path:'visualizer/tools/build_display_assets.mjs',sha256:hash(await fs.readFile(fileURLToPath(import.meta.url))),node:process.version,gltf_transform:'4.3.0',meshoptimizer:'0.24.0'},
 coordinate_frame:'glTF-y-up',units:'m',source_coordinates_preserved:true,
 transformations:{buildings:{source:'overview building mesh',palette:true,keep_mesh_nodes:true,simplify_ratio_target:0.5,simplify_relative_error_limit:0.0001,lock_borders:true,position_quantization_bits:16},
 ground:{maximum_horizontal_edge_m:40,adaptive_sampled_height_error_m:.5,minimum_subdivision_edge_m:5,position_quantization_bits:16,normal_quantization_bits:8,height_quantization_m:.01,boundaries:'Original vector polygon outlines and holes retained before position quantization; no polygon simplification',terrain:'Ordinary GLB positions include DEM elevation; centimetre offsets support optional flattening; original source heights unchanged',normals:'Precomputed from elevated triangles',runtime_attribute:'_CANOPY_HEIGHT codes multiplied by canopy_height_scale_m and divided by node world Y scale; shader subtracts this offset in flat physics views'},
 placements:'Original tree seeds, fixture locations and hedge paths; unrelated metadata omitted'},
 limits:['Display only; never use simplified meshes as replacement simulator geometry.','Ground interpolation errors are sampled, not certified maximum errors.','This is a display export, not a registered V2 scientific Asset. Registration and publication require a separate reviewed change.'],
 buildings:{before:buildingBefore,after:buildingAfter},ground:{...groundAfter,layers:surfaceReport},files};
await fs.writeFile(path.join(output,'provenance.json'),JSON.stringify(report,null,2)+'\n');
await fs.writeFile(path.join(output,'scene-display.json'),JSON.stringify({buildings:'display/buildings.glb',buildings_bytes:buildingAfter.glb_bytes,ground:'display/ground.glb',placements:'display/placements.json.gz'},null,2)+'\n');
console.log(JSON.stringify({output,buildings:buildingAfter,ground:groundAfter},null,2));
