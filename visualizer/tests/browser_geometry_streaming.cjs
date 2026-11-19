// Real London resources. Optional baseline URL measures residency at the same camera.
// Software WebGL: pause continuous drawing, then render explicit screenshot frames.
const assert=require('node:assert/strict'),fs=require('node:fs');
const puppeteer=require(process.env.PUPPETEER_MODULE||'puppeteer-core');
(async()=>{
 const base=new URL(process.argv[2]||'http://127.0.0.1:8778/streaming-preview-v3/canopy/');
 const baseline=process.argv[3]&&new URL(process.argv[3]);
 const browser=await puppeteer.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader']});
 const out='cache/qa/view-streaming';fs.mkdirSync(out,{recursive:true});const errors=[];
 const report={continuousRenderingPaused:true,scientificDataChanged:false,errors};
 async function open(root,quality=''){
  const page=await browser.newPage();page.setDefaultTimeout(180000);await page.setViewport({width:1000,height:700});
  const requests=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
  await page.goto(new URL(`viewer/3d/?scene=imperial_corridor_8km&lite=0&play=0&cam=1776,1300,2600,1776,0,848${quality}`,root).href,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.viewer);
  await page.evaluate(()=>{window.__qaRender=viewer.renderer.render;viewer.renderer.render=()=>{};});
  await page.waitForFunction(()=>document.querySelector('#loading').classList.contains('hide')&&window.cityDetailTiles);
  return {page,requests};
 }
 async function sample(page){return page.evaluate(()=>{
  const buffers=new Set();cityDetailTiles.group.traverse(o=>{if(o.geometry){for(const a of [...Object.values(o.geometry.attributes),o.geometry.index].filter(Boolean))buffers.add((a.array??a.data?.array).buffer);}});
  return {loadedTiles:cityDetailTiles.loaded.length,files:cityDetailTiles.progress.loaded,
   geometryBytes:[...buffers].reduce((n,b)=>n+b.byteLength,0),stats:cityDetailTiles.stats??null,
   coarseVisible:viewer.model.visible,groundReady:!!window.corridorContext};
 });}
 async function picture(page,name){
  // A low pixel ratio keeps the software GPU check practical; not an FPS benchmark.
  await page.evaluate(()=>{viewer.renderer.setPixelRatio(.5);window.__qaRender.call(viewer.renderer,viewer.scene,viewer.camera);});
  await page.screenshot({path:`${out}/${name}.png`});
 }
 try{
  if(baseline){const {page}=await open(baseline);await page.waitForFunction(()=>cityDetailTiles.progress.complete&&window.corridorContext);
   report.baseline=await sample(page);console.log('Baseline',JSON.stringify(report.baseline));await picture(page,'before-near');await page.close();}
  const {page,requests}=await open(base);
  assert(!requests.some(url=>/chunks\/|traffic-am\.(bin|json)|\/assets\/birds\//.test(url)),'Opening must not request physics frames, traffic or birds');
  await page.waitForFunction(()=>cityDetailTiles.progress.complete&&window.corridorContext);
  report.near=await sample(page);assert(report.near.loadedTiles>0&&report.near.loadedTiles<=6);assert(report.near.coarseVisible);
  assert.equal(report.near.stats.peakActive,4);assert.deepEqual(report.near.stats.errors,[]);
  console.log('Streamed near',JSON.stringify({...report.near,stats:undefined}));await picture(page,'after-near');
  // A stable view must not redraw just because the planner polls its queue.
  const renders=await page.evaluate(async()=>{let n=0;viewer.renderer.render=()=>{n++;};await new Promise(r=>setTimeout(r,800));viewer.renderer.render=()=>{};return n;});
  assert(renders<=2,`Idle view rendered ${renders} times`);report.idleRenders=renders;
  await page.evaluate(()=>{viewer.camera.position.set(0,11000,1);viewer.controls.target.set(0,0,0);viewer.controls.update();});
  await page.waitForFunction(()=>cityDetailTiles.stats.residentTiles===0&&cityDetailTiles.stats.jobs.length===0);
  report.overview=await sample(page);assert.equal(report.overview.geometryBytes,0);assert(report.overview.coarseVisible);await picture(page,'after-overview');
  // Move into a new area, then away while work is pending. Nothing stale may reappear.
  await page.evaluate(()=>{viewer.camera.position.set(-2200,500,-1000);viewer.controls.target.set(-1700,0,-1070);viewer.controls.update();});
  await page.waitForFunction(()=>cityDetailTiles.stats.jobs.length>4);
  await page.evaluate(()=>{viewer.camera.position.set(0,11000,1);viewer.controls.target.set(0,0,0);viewer.controls.update();});
  await page.waitForFunction(()=>cityDetailTiles.stats.residentTiles===0);
  await page.evaluate(()=>new Promise(r=>setTimeout(r,500)));
  report.cancelled=await sample(page);assert(report.cancelled.stats.cancelled>0);assert.equal(report.cancelled.geometryBytes,0);
  // Preserve playback on an existing route spanning seven required slots.
  await page.evaluate(()=>{
   document.querySelector('[data-shot=uavs]').click();
   viewer.renderer.domElement.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));
   viewer.uavs.select('R022-R083');viewer.uavs.focus();viewer.uavs.playing=false;
  });
  await page.waitForFunction(()=>viewer.uavs.geometryReady()&&cityDetailTiles.progress.complete);
  report.uav=await sample(page);assert.equal(report.uav.stats.requiredTiles,7);assert.equal(report.uav.loadedTiles,7);
  const t=await page.evaluate(()=>viewer.uavs.t);await page.click('#play');
  await page.waitForFunction(t=>viewer.uavs.t>t,{},t);await page.click('#play');
  console.log('Seven-tile UAV route plays with all required source geometry');
  await page.evaluate(()=>viewer.uavs.select('R064-R087'));
  await page.waitForFunction(()=>cityDetailTiles.progress.requiredOutside>0&&!document.querySelector('#geometry-retry').hidden);
  assert.equal(await page.evaluate(()=>viewer.uavs.geometryReady()),false);
  await page.click('#geometry-retry');
  await page.waitForFunction(()=>document.querySelector('[data-shot=overview]').getAttribute('aria-pressed')==='true');
  report.uncoveredRouteReported=true;
  // First physics selection initializes masks on demand; a later city click wins.
  await page.evaluate(()=>{document.querySelector('[data-field=solar]').click();document.querySelector('[data-shot=overview]').click();});
  await page.waitForFunction(()=>document.querySelector('[data-shot=overview]').getAttribute('aria-pressed')==='true');
  await page.evaluate(()=>new Promise(r=>setTimeout(r,500)));
  assert.equal(await page.$eval('[data-shot=overview]',el=>el.getAttribute('aria-pressed')),'true');
  // Existing first/final recorded samples and widget switching have a separate runner.
  report.requests=requests;await page.close();
  const full=await open(base,'&quality=full');
  assert.equal(await full.page.evaluate(()=>cityDetailTiles.group.name),'complete_detail_geometry');
  await full.page.close();
  assert.deepEqual(errors,[]);
  fs.writeFileSync(`${out}/comparison.json`,JSON.stringify(report,null,2)+'\n');
  console.log('PASS: residency, cancellation, fallback, idle rendering, field selection and full mode');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
