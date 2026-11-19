import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {MeshoptDecoder} from 'three/addons/libs/meshopt_decoder.module.js';
import {grid,drape,patch} from './terrain.mjs';
import {enhanceGroundMaterial} from './runtime/ground-materials.js';

const $=id=>document.getElementById(id),mb=n=>(n/1e6).toFixed(2)+' MB';
const params=new URLSearchParams(location.search);
for(const [id,key] of [['location','area'],['concurrency','concurrency']])if([...$(id).options].some(o=>o.value===params.get(key)))$(id).value=params.get(key);
const viewport=$('viewport'),renderer=new THREE.WebGLRenderer({canvas:$('canvas'),antialias:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.setClearColor('#e5ebe5');
renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.25;
const camera=new THREE.PerspectiveCamera(42,1,1,40000),controls=new OrbitControls(camera,renderer.domElement);
controls.maxPolarAngle=Math.PI*.48;controls.minDistance=30;controls.maxDistance=20000;
let split=.5,mode='both',pendingRender=false,loading=false,manifest,entries,worker,workerFailure=null,nextJob=0,center=[1500,500],overview=false;
const scenes=[0,1].map(()=>{const scene=new THREE.Scene();scene.add(new THREE.HemisphereLight(0xf5faf5,0x647266,2.0));const sun=new THREE.DirectionalLight(0xfff8e8,2.6);sun.position.set(-1600,3000,1800);scene.add(sun);return scene;});
let groups=[];const workerJobs=new Map();
function draw(){pendingRender=false;const w=viewport.clientWidth,h=viewport.clientHeight;renderer.setScissorTest(true);renderer.setViewport(0,0,w,h);renderer.setScissor(0,0,w*split,h);renderer.render(scenes[0],camera);renderer.setScissor(w*split,0,w*(1-split),h);renderer.render(scenes[1],camera);renderer.setScissorTest(false);}
function invalidate(){if(!pendingRender){pendingRender=true;requestAnimationFrame(draw);}}
controls.addEventListener('change',invalidate);
new ResizeObserver(()=>{const w=viewport.clientWidth,h=viewport.clientHeight;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();invalidate();}).observe(viewport);
function setSplit(value){split=Number(value)/100;$('divider').style.left=value+'%';$('wipe').style.left=`calc(${value}% - 24px)`;$('wipe').value=value;$('divider-control').value=value;invalidate();}
let dragging=false;
$('wipe').addEventListener('pointerdown',event=>{dragging=true;$('wipe').setPointerCapture(event.pointerId);event.preventDefault();});
$('wipe').addEventListener('pointermove',event=>{if(dragging){const r=viewport.getBoundingClientRect();setSplit(Math.max(0,Math.min(100,(event.clientX-r.left)/r.width*100)));}});
$('wipe').addEventListener('pointerup',()=>dragging=false);$('wipe').addEventListener('pointercancel',()=>dragging=false);
$('wipe').addEventListener('input',e=>setSplit(e.target.value));$('divider-control').addEventListener('input',e=>setSplit(e.target.value));
function reset(){const [x,z]=center,scale=overview?8:1;controls.target.set(x,30,z);camera.position.set(x+850*scale,900*scale,z+1000*scale);controls.update();invalidate();}
$('reset').onclick=reset;
function visibility(){groups.forEach(g=>{g.buildings.visible=mode!=='ground';g.ground.visible=mode!=='buildings';});invalidate();}
document.querySelectorAll('[data-layer]').forEach(button=>button.onclick=()=>{mode=button.dataset.layer;document.querySelectorAll('[data-layer]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));visibility();});
function wireframe(){groups.forEach(g=>Object.values(g).forEach(root=>root.traverse(o=>{if(o.isMesh)(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>m.wireframe=$('wireframe').checked);})));invalidate();}
$('wireframe').onchange=wireframe;
function dispose(root){const geometries=new Set(),materials=new Set(),textures=new Set();root.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.material)(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>materials.add(m));});materials.forEach(m=>Object.values(m).forEach(v=>{if(v?.isTexture)textures.add(v);}));geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>{t.source?.data?.close?.();t.dispose();});root.removeFromParent();}
function clear(){groups.forEach(g=>Object.values(g).forEach(dispose));renderer.renderLists.dispose();groups=scenes.map(scene=>{const buildings=new THREE.Group(),ground=new THREE.Group();scene.add(buildings,ground);return {buildings,ground};});visibility();}
function createWorker(){workerFailure=null;worker=new Worker(new URL('./ground-worker.mjs',import.meta.url),{type:'module'});worker.onmessage=({data})=>{const job=workerJobs.get(data.id);if(!job)return;workerJobs.delete(data.id);data.error?job.reject(Error(data.error)):job.resolve(data.result);};worker.onerror=event=>{workerFailure=Error(event.message||'Ground Worker failed');for(const job of workerJobs.values())job.reject(workerFailure);workerJobs.clear();};}
function ground(bytes,bounds){if(workerFailure)return Promise.reject(workerFailure);return new Promise((resolve,reject)=>{const id=nextJob++;workerJobs.set(id,{resolve,reject});worker.postMessage({id,bytes,bounds},[bytes]);});}
async function fetchBytes(file,side){
  const url=side?new URL(file.url,location.href):new URL(file.source,manifest.source.base_url);
  const response=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(30000)});if(!response.ok)throw Error(`HTTP ${response.status}: ${file.source}`);
  const bytes=await response.arrayBuffer();const expected=side?file.optimized_bytes:file.original_bytes;
  if(bytes.byteLength!==expected)throw Error(`Unexpected payload size: ${file.source}`);
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
  if(digest!==(side?file.optimized_sha256:file.source_sha256))throw Error(`Checksum mismatch: ${file.source}`);
  return {url,bytes};
}
async function unpack(bytes,gzip){return gzip?new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer():bytes;}
function updateTable(files){$('files').replaceChildren();let before=0,after=0;for(const f of files){before+=f.original_bytes;after+=f.optimized_bytes;const row=document.createElement('tr');for(const text of [f.source,mb(f.original_bytes),mb(f.optimized_bytes),((1-f.optimized_bytes/f.original_bytes)*100).toFixed(1)+'% smaller']){const cell=document.createElement('td');cell.textContent=text;row.append(cell);}$('files').append(row);}$('selected-total').textContent=`Geometry + terrain inputs: ${mb(before)} → ${mb(after)}; textures additional`;}
async function load(){if(loading)return;loading=true;window.review.ready=false;$('location').disabled=true;$('reload').disabled=true;$('concurrency').disabled=true;$('loading').hidden=false;$('loading').querySelector('strong').textContent='Loading both versions';$('load-progress').removeAttribute('value');
  clear();const started=performance.now(),locationId=$('location').value;overview=locationId==='overview';const tile=manifest.tiles.find(t=>t.id===locationId);center=overview?[0,0]:tile.centre_xz;reset();
  const bounds=overview?null:[center[0]-550,center[1]-550,center[0]+550,center[1]+550];
  const buildingPaths=overview?['models/buildings.glb.gz']:[tile.file,...tile.landmarks.map(l=>l.file)].map(f=>'tiles/detail_tiles_enu_20261030/'+f+'.gz');
  const groundPaths=manifest.ground.map(l=>'context/terrain/'+(l.name==='unclassified-base'?'unclassified-base-exposed.f32.gz':l.file+'.gz'));
  const paths=[...buildingPaths,...groundPaths],files=paths.map(p=>{const f=entries.get(p);if(!f)throw Error('Undeclared geometry '+p);return f;});
  updateTable([entries.get('context/terrain/terrain.json'),...files]);
  $('scope').textContent=overview?'Whole 8 km · existing overview mesh':'1 km district · source detail tiles + landmarks';
  let completed=0,preparation=Promise.resolve();const queue=[];const timings={network_ms:[0,0],prepare_ms:[0,0],tasks:files.length*2+2,concurrency:Number($('concurrency').value)};
  const prepare=fn=>{const work=preparation.then(fn);preparation=work.catch(()=>{});return work;};
  try{
    createWorker();
    // Read both versions of the real DEM before preparing geometry; do not substitute one side's data.
    const terrain=entries.get('context/terrain/terrain.json');
    const dem=[];for(let side=0;side<2;side++){const r=await fetchBytes(terrain,side);const raw=await unpack(r.bytes,side?terrain.gzip:terrain.original_gzip);dem.push(grid(JSON.parse(new TextDecoder().decode(raw)).terrain));}
    const a=new Uint8Array(dem[0].h.buffer),b=new Uint8Array(dem[1].h.buffer);if(a.length!==b.length||a.some((v,i)=>v!==b[i]))throw Error('Terrain differs after decompression');
    worker.postMessage({type:'init',dem:dem[0]});
    for(const file of files)for(let side=0;side<2;side++)queue.push({file,side});
    $('load-progress').max=queue.length;$('load-progress').value=0;
    await Promise.allSettled(Array.from({length:timings.concurrency},async()=>{while(queue.length){const {file,side}=queue.shift(),networkStart=performance.now();const fetched=await fetchBytes(file,side);timings.network_ms[side]+=performance.now()-networkStart;
      await prepare(async()=>{const t=performance.now(),bytes=await unpack(fetched.bytes,side?file.gzip:file.original_gzip);
        if(file.source.endsWith('.glb.gz')){const loader=new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);const gltf=await loader.parseAsync(bytes,new URL('.',fetched.url).href);drape(gltf.scene,dem[side]);gltf.scene.name=file.source;groups[side].buildings.add(gltf.scene);}
        else {const arrays=await ground(bytes,bounds),geometry=new THREE.BufferGeometry();for(const [name,array] of Object.entries(arrays))geometry.setAttribute(name,new THREE.BufferAttribute(array,name==='canopyHeight'?1:3));
          const index=groundPaths.indexOf(file.source),layer=manifest.ground[index];const material=enhanceGroundMaterial(new THREE.MeshStandardMaterial({color:layer.color,side:THREE.DoubleSide,roughness:1}),layer.name);patch(material);
          const mesh=new THREE.Mesh(geometry,material);mesh.name=file.source;mesh.frustumCulled=false;mesh.renderOrder=index;groups[side].ground.add(mesh);}
        timings.prepare_ms[side]+=performance.now()-t;completed++;$('load-progress').value=completed;$('load-status').textContent=`${completed} / ${files.length*2} geometry resources prepared`;wireframe();
        await new Promise(resolve=>requestAnimationFrame(resolve));
      });
    }})).then(results=>{const failure=results.find(r=>r.status==='rejected');if(failure)throw failure.reason;});
    timings.elapsed_ms=performance.now()-started;
    window.review.timings=timings;window.review.ready=true;window.review.error=null;$('loading').hidden=true;
    $('session-result').textContent=`Both versions ready in ${(timings.elapsed_ms/1000).toFixed(1)} s this session. ${timings.concurrency} geometry tasks allowed; ${completed} resources prepared. Vertex and texture memory is not reduced by compression.`;
  }catch(error){window.review.error=String(error);console.error(error);$('loading').querySelector('strong').textContent='Geometry could not be loaded';$('load-status').textContent=error.message+' Use Reload selected area to retry.';}
  finally{worker?.terminate();worker=null;loading=false;$('location').disabled=false;$('reload').disabled=false;$('concurrency').disabled=false;invalidate();}
}
$('location').onchange=load;$('reload').onclick=load;
window.review={ready:false,error:null,renderer,camera,controls,scenes,get groups(){return groups;},draw,setSplit,load};
try{
  const r=await fetch('manifest.json');if(!r.ok)throw Error(`Manifest HTTP ${r.status}`);manifest=await r.json();if(manifest.kind!=='canopy.geometry-compression-review'||manifest.schema_version!=='1.0.0')throw Error('Unsupported review manifest');
  entries=new Map(manifest.files.map(f=>[f.source,f]));
  for(const [group,prefix] of [['buildings','building'],['ground','ground']]){const g=manifest.groups[group];$(prefix+'-before').textContent=mb(g.original_bytes);$(prefix+'-after').textContent=mb(g.optimized_bytes);$(prefix+'-saving').textContent=((1-g.optimized_bytes/g.original_bytes)*100).toFixed(1)+'% smaller · source files retained';}
  $('verified').textContent=`${manifest.integrity.glbs} GLBs · ${manifest.integrity.buffer_views.toLocaleString()} buffer views verified`;
  await MeshoptDecoder.ready;await load();
}catch(error){window.review.error=String(error);$('load-status').textContent=error.message;console.error(error);}
