// Run against prepare_city_health.py's explicitly synthetic local example.
const assert=require('node:assert/strict'),fs=require('node:fs');
const puppeteer=require(process.env.CANOPY_PUPPETEER||'puppeteer-core');
const url=process.env.CANOPY_CITY_URL||'http://127.0.0.1:8826/viewer/3d/?scene=imperial_corridor_8km&health=local&pedestrian=1&play=0&lite=1';
(async()=>{const browser=await puppeteer.launch({executablePath:process.env.CANOPY_BROWSER_PATH,protocolTimeout:300000,headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader']});try{
 const page=await browser.newPage(),errors=[],posts=[];let expectedFailure=false;
 await page.setViewport({width:1440,height:1000});page.on('pageerror',e=>errors.push(e.message));
 page.on('response',r=>{if(r.status()>=400&&new URL(r.url()).origin===new URL(url).origin&&!(expectedFailure&&r.url().endsWith('/api/health/walk')))errors.push(r.status()+' '+r.url())});
 page.on('request',r=>{if(r.method()==='POST'&&new URL(r.url()).origin===new URL(url).origin)posts.push(r.url())});
 await page.goto(url,{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>window.canopyLocalHealth?.active&&document.querySelector('#loading').classList.contains('hide'),{timeout:240000});
 const initial=await page.evaluate(()=>({asset:canopyLocalHealth.result.recording.asset,kind:canopyLocalHealth.result.physiology_input_kind,start:canopyLocalHealth.start,end:canopyLocalHealth.end,position:canopyLocalHealth.position}));
 assert.equal(initial.kind,'synthetic');assert.equal(posts.length,0);
 assert.match(await page.$eval('#cr-estimate-note',e=>e.textContent),/Fictional/);
 assert.equal(await page.$$eval('#cr-charts svg',s=>s.length),7);
 const native=await page.evaluate(()=>JSON.stringify({layers:viewer.LAYERS,phases:viewer.PHASES}));
 const seek=t=>page.evaluate(t=>{const s=document.querySelector('#step');s.value=t;s.dispatchEvent(new Event('input',{bubbles:true}));},t);
 await page.click('#play');await new Promise(r=>setTimeout(r,450));await page.click('#play');
 const paused=await page.evaluate(()=>canopyLocalHealth.time);assert(paused>initial.start);
 await new Promise(r=>setTimeout(r,250));assert.equal(await page.evaluate(()=>canopyLocalHealth.time),paused);
 await seek(initial.end);assert.equal(await page.evaluate(()=>viewer.scene.getObjectByName('health-walker').userData.status),'Arrived');
 assert.notDeepEqual(await page.evaluate(()=>canopyLocalHealth.position),initial.position);
 await page.click('#play');await new Promise(r=>setTimeout(r,150));await page.click('#play');assert(await page.evaluate(()=>canopyLocalHealth.time<canopyLocalHealth.end));
 await page.click('#cr-followup');await seek(initial.start+299.99);
 const before=await page.evaluate(()=>canopyLocalHealth.result.samples.findLast(s=>s.world_seconds<=canopyLocalHealth.time).model_updates);
 await seek(initial.start+300);const after=await page.evaluate(()=>canopyLocalHealth.result.samples.findLast(s=>s.world_seconds<=canopyLocalHealth.time).model_updates);assert.equal(after,before+1);
 await page.select('#cr-speed','60');assert.equal(await page.evaluate(()=>canopyLocalHealth.speed),60);
 await page.click('#cr-visible');assert.equal(await page.evaluate(()=>canopyLocalHealth.visible),false);await page.click('#cr-visible');
 // Two explicit calculations exercise another start time and reversed endpoints.
 const calculations=[];
 for(const clock of ['12:50:37','18:50:37']){
  await page.click('#cr-swap');
  await page.$eval('#cr-departure',(e,value)=>{e.value=value;e.dispatchEvent(new Event('change',{bubbles:true}));},clock);
  await page.click('#cr-calculate');await page.waitForFunction(()=>!document.querySelector('#cr-calculate').disabled,{timeout:360000});
  assert.match(await page.$eval('#cr-route-status',e=>e.textContent),/^Ready:/);
  calculations.push(await page.evaluate(()=>{const r=canopyLocalHealth.result;return {asset:r.recording.asset,start:canopyLocalHealth.start,kind:r.physiology_input_kind,nativeUnavailable:r.samples.every(s=>s.pmx===null&&s.temperature===null),finite:r.samples.every(s=>Number.isFinite(s.health_score)&&Number.isFinite(s.breathing)),strict:r.samples.every((s,i)=>!i||s.world_seconds>r.samples[i-1].world_seconds)};}));
 }
 assert.deepEqual(calculations.map(r=>r.start),[14437,36037]);assert(calculations.every(r=>r.kind==='synthetic'&&r.nativeUnavailable&&r.finite&&r.strict));
 assert.equal(await page.evaluate(()=>JSON.stringify({layers:viewer.LAYERS,phases:viewer.PHASES})),native);
 await page.click('#tabs [data-field="poll"]');assert.equal(await page.evaluate(()=>canopyLocalHealth.active),false);
 await page.waitForFunction(()=>+document.querySelector('#step').max===viewer.PHASES.poll.end);assert.equal(await page.evaluate(()=>canopyLocalHealth.playing),false);
 await page.evaluate(()=>canopyLocalHealth.setActive(true));
 await page.setViewport({width:390,height:844});assert(await page.$eval('#city-recorded-health',e=>e.getBoundingClientRect().right<=innerWidth));
 await page.setViewport({width:1440,height:1000});
 expectedFailure=true;await page.setRequestInterception(true);page.on('request',r=>{if(r.isInterceptResolutionHandled())return;r.url().endsWith('/api/health/walk')?r.respond({status:503,contentType:'application/json',body:'{"error":"Test unavailable"}'}):r.continue()});
 await page.click('#cr-calculate');await page.waitForFunction(()=>document.querySelector('#cr-route-status').textContent.includes('Test unavailable'));
 assert.equal(await page.$eval('#cr-output',e=>e.hidden),true);await page.click('#cr-restore');assert.equal(await page.evaluate(()=>canopyLocalHealth.result.recording.asset),initial.asset);
 const tiles=await page.evaluate(()=>window.cityDetailTiles?.progress??null);if(url.includes('lite=0'))assert(tiles.complete&&tiles.loaded===64);
 assert.equal(posts.length,3);assert.deepEqual(errors,[]);
 await page.screenshot({path:'cache/pr-health-city.png'});
 // Ordinary city URL must not request a Health API or mount Health controls.
 const ordinary=await browser.newPage(),requests=[];ordinary.on('request',r=>{if(r.url().includes('/api/health/')||r.url().includes('/api/pedestrian/'))requests.push(r.url())});
 await ordinary.goto(new URL('/viewer/3d/?scene=imperial_corridor_8km&play=0&lite=1',url).href,{waitUntil:'domcontentloaded'});
 await ordinary.waitForFunction(()=>document.querySelector('#loading').classList.contains('hide'),{timeout:240000});assert.deepEqual(requests,[]);assert.equal(await ordinary.$('#city-recorded-health'),null);
 fs.writeFileSync('cache/pr-health-city-browser.json',JSON.stringify({initial,calculations,tiles,errors,posts,ordinaryHealthRequests:requests},null,2));console.log(JSON.stringify({calculations,tiles,errors,ordinaryHealthRequests:requests}));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
