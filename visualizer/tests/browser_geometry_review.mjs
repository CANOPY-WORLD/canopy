// Real-data review QA. Set PUPPETEER_MODULE to an installed ESM module entry.
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
const {default:puppeteer}=await import(process.env.PUPPETEER_MODULE||'puppeteer-core');
const base=process.argv[2]||'http://127.0.0.1:8824/';
const output='cache/qa/geometry-review';await mkdir(output,{recursive:true});
const browser=await puppeteer.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',
  headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader']});
const errors=[],results=[];
try {
 const page=await browser.newPage();await page.setViewport({width:1440,height:1050});
 page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)errors.push(`${r.status()} ${r.url()}`);});
 await page.goto(base,{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>!!window.review,{timeout:30000});
 // Software WebGL is unsuitable for load-time benchmarking. Pause repeated drawing;
 // explicit comparison frames below still exercise real shaders and textures.
 await page.evaluate(()=>{review.realRender=review.renderer.render;review.renderer.render=()=>{};});
 const ready=async()=>{await page.waitForFunction(()=>review.ready||review.error,{timeout:180000});assert.equal(await page.evaluate(()=>review.error),null);};
 await ready();
 async function compare(label,pixels=true) {
  const result=await page.evaluate(async({label,pixels})=>{
   const THREE=await import('./vendor/three/build/three.module.js');
   const hash=async a=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',a)),v=>v.toString(16).padStart(2,'0')).join('');
   const records=[];
   for(const side of review.groups){const record=[];for(const kind of ['buildings','ground']){
    const meshes=[];side[kind].traverse(o=>{if(o.isMesh)meshes.push(o);});
    for(const mesh of meshes){const attrs={};for(const [name,attr] of Object.entries(mesh.geometry.attributes).sort(([a],[b])=>a.localeCompare(b))){
      const values=new Float64Array(attr.count*attr.itemSize);for(let i=0;i<attr.count;i++)for(let c=0;c<attr.itemSize;c++)values[i*attr.itemSize+c]=attr.getComponent(i,c);
      attrs[name]={count:attr.count,itemSize:attr.itemSize,hash:await hash(values.buffer)};
    }
    const route=[];let owner=mesh;while(owner.parent&&owner.parent!==side[kind]){route.unshift(owner.parent.children.indexOf(owner));owner=owner.parent;}
    const index=mesh.geometry.index;record.push({key:kind+'/'+owner.name+'/'+route.join('/'),kind,name:mesh.name,attrs,index:index?await hash(index.array.buffer.slice(index.array.byteOffset,index.array.byteOffset+index.array.byteLength)):null,matrix:mesh.matrixWorld.elements});
   }}records.push(record.sort((a,b)=>a.key.localeCompare(b.key)));}
   const same=JSON.stringify(records[0])===JSON.stringify(records[1]);
   let pixelDifference=null;
   if(pixels){const target=new THREE.WebGLRenderTarget(600,400);const savedAspect=review.camera.aspect;review.camera.aspect=1.5;review.camera.updateProjectionMatrix();review.renderer.setRenderTarget(target);review.renderer.setViewport(0,0,600,400);review.renderer.setScissorTest(false);
    const frames=[];for(const scene of review.scenes){review.realRender.call(review.renderer,scene,review.camera);const bytes=new Uint8Array(600*400*4);review.renderer.readRenderTargetPixels(target,0,0,600,400,bytes);frames.push(bytes);}
    pixelDifference=frames[0].reduce((n,v,i)=>n+(v!==frames[1][i]?1:0),0);
    review.renderer.setRenderTarget(null);target.dispose();review.camera.aspect=savedAspect;review.camera.updateProjectionMatrix();
   }
   const mismatch=records[0].findIndex((r,i)=>JSON.stringify(r)!==JSON.stringify(records[1][i]));
   return {label,same,mismatch:same?null:[records[0][mismatch],records[1][mismatch]],meshes:records[0].length,attributes:records[0].reduce((n,x)=>n+Object.keys(x.attrs).length,0),pixelDifference,timings:review.timings};
  },{label,pixels});
  console.log(JSON.stringify(result));assert(result.same,`${label}: decoded scene attributes differ`);assert.equal(result.pixelDifference,pixels?0:null,`${label}: rendered pixels differ`);results.push(result);
 }
 await compare('Battersea');
 await page.evaluate(()=>{review.renderer.render=review.realRender;review.draw();});
 await page.screenshot({path:output+'/desktop.png',fullPage:true});
 await page.click('[data-layer="ground"]');assert(await page.evaluate(()=>review.groups.every(g=>!g.buildings.visible&&g.ground.visible)));
 await page.click('#wireframe');assert(await page.evaluate(()=>{let valid=true;review.groups[0].ground.traverse(o=>{if(o.isMesh&&!o.material.wireframe)valid=false;});return valid;}));
 await page.click('#wireframe');await page.click('[data-layer="both"]');
 await page.evaluate(()=>review.setSplit(72));assert.equal(await page.$eval('#divider-control',e=>e.value),'72');
 await page.setViewport({width:390,height:844});await page.evaluate(()=>{review.setSplit(50);review.draw();});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:output+'/mobile.png',fullPage:true});
 await page.setViewport({width:1440,height:1050});await page.evaluate(()=>review.renderer.render=()=>{});
 // Switch district and concurrency, checking the previous scene was released.
 await page.select('#concurrency','1');await page.select('#location','b_5_3');await ready();await compare('South Kensington',false);
 assert.equal(await page.evaluate(()=>review.groups[0].buildings.children.length),63);
 await page.select('#concurrency','4');await page.select('#location','overview');await ready();await compare('Whole 8 km',false);
 assert.equal(await page.evaluate(()=>review.groups[0].buildings.children.length),1);
 await page.select('#concurrency','3');await page.select('#location','b_7_1');await ready();
 assert.equal(await page.evaluate(()=>review.groups[0].buildings.children.length),4);
 assert.deepEqual(errors,[]);await writeFile(output+'/browser-results.json',JSON.stringify({errors,results,limits:'Software WebGL; repeated draws paused. Timings are QA diagnostics, not speed benchmarks.'},null,2)+'\n');
} finally {await browser.close();}
