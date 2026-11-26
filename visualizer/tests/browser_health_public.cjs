// Public recorded-only Health at a project subpath; no local service allowed.
const assert=require('node:assert/strict');
(async()=>{
 const {default:puppeteer}=await import(process.env.CANOPY_PUPPETEER||'puppeteer-core');
 const browser=await puppeteer.launch({executablePath:process.env.CANOPY_BROWSER_PATH||'/usr/bin/google-chrome',protocolTimeout:300000,headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage(),errors=[],api=[];await page.setViewport({width:1280,height:800});
  page.on('pageerror',e=>{errors.push(e.message);console.error(e.stack)});page.on('request',r=>{if(r.url().includes('/api/'))api.push(r.url())});
  page.on('response',r=>{if(r.status()>=400)errors.push(r.status()+' '+r.url())});
  await page.goto(process.env.CANOPY_CITY_URL||'http://127.0.0.1:8829/canopy/viewer/3d/?scene=imperial_corridor_8km&play=0&lite=0',{waitUntil:'domcontentloaded'});
  console.log('Page opened');
  await page.waitForFunction(()=>window.viewer?.renderer,{timeout:240000});
  console.log('Renderer ready');
  if(process.env.CANOPY_QA_PAUSE_RENDER==='1')await page.evaluate(()=>{window.qaRender=viewer.renderer.render.bind(viewer.renderer);viewer.renderer.render=()=>{}});
  await page.waitForFunction(()=>window.canopyLocalHealth&&document.querySelector('#loading').classList.contains('hide'),{timeout:240000});
  assert.equal(await page.evaluate(()=>canopyLocalHealth.active),false,'Overview remains default');
  await page.waitForSelector('#model-card',{timeout:60000});
  await page.click('#canopy-walking-mode');
  await page.waitForFunction(()=>!document.querySelector('#model-card').hidden&&document.querySelector('#model-card h2').textContent.includes('CVAE'));
  assert.equal(await page.evaluate(()=>canopyLocalHealth.result.physiology_input_kind),'synthetic');
  assert.equal(await page.$eval('#city-recorded-health',e=>e.hidden),true,'No public inspection panel');
  assert.equal(await page.$('#cr-calculate'),null);
  assert.equal(await page.evaluate(()=>canopyLocalHealth.speed),10);
  await page.click('#play');await new Promise(r=>setTimeout(r,250));await page.click('#play');
  const paused=await page.evaluate(()=>canopyLocalHealth.time);assert(paused>await page.evaluate(()=>canopyLocalHealth.start));
  await new Promise(r=>setTimeout(r,150));assert.equal(await page.evaluate(()=>canopyLocalHealth.time),paused);
  await page.evaluate(()=>{const e=document.querySelector('#step');e.value=e.max;e.dispatchEvent(new Event('input',{bubbles:true}))});
  assert.equal(await page.evaluate(()=>viewer.scene.getObjectByName('health-walker').userData.status),'Arrived');
  await page.click('#play');await new Promise(r=>setTimeout(r,100));await page.click('#play');assert(await page.evaluate(()=>canopyLocalHealth.time<canopyLocalHealth.end));
  await page.click('#tabs [data-field="wind"]');assert.equal(await page.evaluate(()=>canopyLocalHealth.active),false);
  await page.click('#canopy-walking-mode');await page.click('#tabs [data-shot="overview"]');assert.equal(await page.evaluate(()=>canopyLocalHealth.active),false);
  await page.click('#canopy-walking-mode');
  await page.setViewport({width:390,height:844});assert(await page.$eval('#model-card',e=>e.getBoundingClientRect().right<=innerWidth));
  await page.setViewport({width:1280,height:800});
  if(process.env.CANOPY_QA_PAUSE_RENDER==='1'){await page.evaluate(()=>{viewer.renderer.render=window.qaRender;window.dispatchEvent(new Event('resize'))});await new Promise(r=>setTimeout(r,1500));}
  await page.screenshot({path:'cache/health-public-preview.png'});
  assert.deepEqual(api,[]);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({status:'PASS',api,errors,tiles:await page.evaluate(()=>window.cityDetailTiles?.progress)}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
