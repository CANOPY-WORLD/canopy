// Default entry, actual field demand, and bounded memory ownership. This tests
// deterministic work budgets, not hardware-dependent FPS or network latency.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const puppeteer=require(process.env.PUPPETEER_MODULE||'puppeteer-core');
(async()=>{
 const base=new URL(process.argv[2]||'http://127.0.0.1:8769/canopy/');
 const browser=await puppeteer.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader']});
 const errors=[],requests=[];
 try{
  const page=await browser.newPage();page.setDefaultTimeout(120000);
  await page.setViewport({width:1000,height:700});
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
  await page.goto(new URL('?lite=0&play=0',base).href,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!!window.viewer);
  await page.evaluate(()=>{viewer.renderer.render=()=>{};});
  await page.waitForFunction(()=>document.querySelector('#loading').classList.contains('hide')&&!!window.corridorContext);
  assert.equal(await page.evaluate(()=>viewer.geometryQuality),'balanced');
  assert(await page.evaluate(()=>viewer.model.visible),'Overview buildings must be visible');
  assert(!requests.some(url=>url.includes('/tiles/')),'Default entry must not download complete detail tiles');
  assert(!requests.some(url=>/download-manifests?/.test(url)),'Opening must not trigger the complete offline download');
  const before=requests.length;
  const select=async field=>{
   await page.evaluate(field=>{document.querySelector(`[data-field=${field}]`).click();if(document.querySelector('#play').getAttribute('aria-label')==='Pause')document.querySelector('#play').click();},field);
   await page.waitForFunction(field=>viewer.state.phase===field&&viewer.state.introDone&&!viewer.state.loading,{},field);
  };
  await select('solar');
  await page.waitForFunction(()=>viewer.frameCacheInfo().pending===0);
  const solarReads=[...new Set(requests.slice(before).filter(url=>/chunks\/quantized8\/solar_.*\.gz/.test(url)))];
  assert(solarReads.length>0&&solarReads.length<=3,`Expected current + two solar frames, got ${solarReads.length}`);
  for(let i=0;i<6;i++)for(const field of ['poll','wind','solar'])await select(field);
  await page.waitForFunction(()=>viewer.frameCacheInfo().pending===0);
  const cache=await page.evaluate(()=>viewer.frameCacheInfo());
  assert(cache.bytes<=cache.cap);assert(cache.cap<=64*1024*1024);
  await page.evaluate(()=>{document.querySelector('[data-field=solar]').click();document.querySelector('[data-shot=traffic]').click();});
  await page.waitForFunction(()=>document.querySelector('[data-shot=traffic]').getAttribute('aria-pressed')==='true');
  await page.waitForFunction(()=>viewer.frameCacheInfo().pending===0);
  assert.equal(await page.evaluate(()=>viewer.frameCacheInfo().bytes),0,'Hidden fields must release their frame cache');
  assert.equal(await page.evaluate(()=>viewer.state.loading),false);
  assert.deepEqual(errors,[]);
  const result={passed:true,geometry:'balanced',solarReads:solarReads.length,switches:18,cache,continuousRenderingPaused:true,errors};
  fs.mkdirSync('cache/qa/loading-budget',{recursive:true});
  fs.writeFileSync('cache/qa/loading-budget/result.json',JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify(result,null,2));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
