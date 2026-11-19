// Build an isolated review distribution from the locked, already-public snapshot.
import {readFile, writeFile, mkdir, cp, access} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {gzipSync, gunzipSync} from 'node:zlib';
import assert from 'node:assert/strict';
import {compressGlb, sha256} from './lossless.mjs';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const [sourceArg, outputArg] = process.argv.slice(2);
if (!sourceArg || !outputArg) throw Error('Usage: node build.mjs PUBLIC_SNAPSHOT EMPTY_OUTPUT_DIRECTORY');
const source = path.resolve(sourceArg), output = path.resolve(outputArg);
assert(output !== source && !output.startsWith(source + path.sep), 'Output must be outside source');
try { await access(path.join(output, 'manifest.json')); throw Error('Refusing to overwrite a completed review'); }
catch(error) { if(error.code !== 'ENOENT') throw error; }
await mkdir(output, {recursive:true});
const publication = JSON.parse(await readFile(path.join(repo,'scenario/imperial_corridor_8km/publication.json')));
const locked = await readFile(path.join(repo,'scenario/imperial_corridor_8km/data/manifest.json'));
assert.equal(sha256(locked), publication.manifest.sha256, 'Locked manifest changed');
const inventory = JSON.parse(locked), entries = new Map(inventory.files.map(f=>[f.path,f]));
async function input(relative) {
  const entry=entries.get(relative); assert(entry, `Undeclared source ${relative}`);
  const bytes=await readFile(path.join(source,relative));
  assert.equal(bytes.length,entry.bytes); assert.equal(sha256(bytes),entry.sha256,relative);
  return bytes;
}
const manifest = {schema_version:'1.0.0',kind:'canopy.geometry-compression-review',
  scenario_id:'imperial_corridor_8km',created_at:new Date().toISOString(),
  source:{repository:publication.repository,revision:publication.revision,snapshot:publication.snapshot,
    manifest_sha256:publication.manifest.sha256,base_url:publication.base_url},
  recipe:{converter_sha256:sha256(await readFile(new URL('./lossless.mjs',import.meta.url))),
    builder_sha256:sha256(await readFile(fileURLToPath(import.meta.url))),
    meshoptimizer:'0.24.0',extension:'EXT_meshopt_compression',filter:'NONE',index_mode:'INDICES',
    gzip_level:9,quantization:false,simplification:false,vertex_reordering:false},
  files:[],groups:{}};
const proofs=[];
async function save(relative, bytes) {
  await mkdir(path.dirname(path.join(output,relative)), {recursive:true});
  await writeFile(path.join(output,relative),bytes);
}
for(const entry of inventory.files) {
  const p=entry.path;
  const building=p==='models/buildings.glb.gz'||p.startsWith('tiles/detail_tiles_enu_20261030/');
  const ground=p.startsWith('context/vector_landscape/')||p.startsWith('context/terrain/')||p.startsWith('context/vector_roads_20261103/');
  if(!building&&!ground) continue;
  // Keep historical authoring/source exports in the source snapshot. Only these source bytes are runtime inputs.
  if(p.includes('/source/')&&!p.endsWith('/source/scene-meta.json')) continue;
  if(!/\.(glb\.gz|f32(?:\.gz)?|json(?:\.gz)?|png|jpe?g|webp)$/.test(p)) continue;
  const original=await input(p), raw=p.endsWith('.gz')?gunzipSync(original):original;
  let candidate, detail;
  if(p.endsWith('.glb.gz')) {
    detail=await compressGlb(raw); candidate=gzipSync(detail.bytes,{level:9});
    proofs.push({path:p,descriptors_equal:true,views:detail.proofs});
  } else {
    candidate=/\.(png|jpe?g|webp)$/.test(p)?original:gzipSync(raw,{level:9});
    assert.deepEqual(/\.(png|jpe?g|webp)$/.test(p)?candidate:gunzipSync(candidate),raw);
  }
  // A compression candidate is optional; never increase a payload just to force a codec.
  const changed=candidate.length < original.length;
  const bytes=changed?candidate:original;
  const compressed=changed||p.endsWith('.gz');
  const relative='data/'+p+(changed&&!p.endsWith('.gz')&&!/\.(png|jpe?g|webp)$/.test(p)?'.gz':'');
  await save(relative,bytes);
  const group=building?'buildings':'ground';
  manifest.files.push({source:p,url:relative,group,original_bytes:original.length,optimized_bytes:bytes.length,
    source_sha256:sha256(original),optimized_sha256:sha256(bytes),decoded_source_bytes:raw.length,
    gzip:compressed,meshopt:!!(changed&&detail),triangles:detail?.triangles,
    verified_views:detail?.proofs.length,decoded_equal:!detail,
    original_gzip:p.endsWith('.gz')});
  const totals=manifest.groups[group]??={files:0,original_bytes:0,optimized_bytes:0,triangles:0};
  totals.files++; totals.original_bytes+=original.length;totals.optimized_bytes+=bytes.length;
  totals.triangles+=detail?.triangles||0;
  if(detail&&manifest.files.filter(f=>f.verified_views).length%50===0) console.log(`Verified ${manifest.files.length} resources`);
}
const indexPath='tiles/detail_tiles_enu_20261030/index.json';
manifest.tiles=JSON.parse(await input(indexPath)).tiles;
manifest.ground=JSON.parse(await input('context/vector_landscape/manifest.json')).layers;
manifest.integrity={glbs:proofs.length,buffer_views:proofs.reduce((n,p)=>n+p.views.length,0),
  geometry_equal:true,descriptors_equal:true,proof_file:'verification.json'};
await save('verification.json',Buffer.from(JSON.stringify({source:manifest.source,recipe:manifest.recipe,files:proofs})));
manifest.integrity.proof_sha256=sha256(await readFile(path.join(output,'verification.json')));
await save('manifest.json',Buffer.from(JSON.stringify(manifest,null,2)+'\n'));
await cp(path.join(repo,'visualizer/geometry-review'),output,{recursive:true});
await cp(path.join(repo,'visualizer/site/vendor/three'),path.join(output,'vendor/three'),{recursive:true});
for(const name of ['corridor-terrain.js','ground-materials.js']) {
  await mkdir(path.join(output,'runtime'),{recursive:true});
  await cp(path.join(repo,'visualizer/site/viewer/3d',name),path.join(output,'runtime',name));
}
const terrainCode=await readFile(path.join(repo,'visualizer/site/viewer/3d/corridor-terrain.js'),'utf8');
const surfaceStart=terrainCode.indexOf('export function terrainSurfaceGeometry(');
assert(surfaceStart>=0,'Production ground preparation function missing');
const surfaceEnd=terrainCode.indexOf('\nexport function ',surfaceStart+1);
assert(surfaceEnd>surfaceStart,'Production ground preparation boundary missing');
await save('runtime/ground-surface.mjs',Buffer.from('// Copied without changes from the production ground preparation function.\n'+
  "import * as THREE from '../vendor/three/build/three.module.js';\n"+terrainCode.slice(surfaceStart,surfaceEnd)+'\n'));
await save('SOURCE-NOTICES.txt',Buffer.from('Source: '+publication.repository+' at '+publication.revision+'\n'+
  'London public snapshot '+publication.snapshot+'. Original provenance and notices remain in that snapshot.\n'+
  'Overture Maps / OpenStreetMap-derived geographic data: ODbL where specified by source metadata.\n'+
  'Three.js and meshoptimizer are MIT-licensed; bundled source notices are retained.\n'));
console.log(JSON.stringify({output,groups:manifest.groups,integrity:manifest.integrity},null,2));
