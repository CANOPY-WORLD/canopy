// Uses an explicitly prepared local private workspace; outputs no participant values.
const assert=require('node:assert/strict');
const p=require(process.env.PUPPETEER_MODULE||'puppeteer-core');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const base=process.argv[2]||'http://127.0.0.1:8784';
 const browser=await p.launch({executablePath:process.env.CHROME_PATH,headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('Ready.'));
  assert.equal(await page.$eval('#travel_mode',e=>e.value),'walk');
  const rejected=await page.evaluate(async()=> (await fetch('/api/health/plan',{method:'POST',body:'{}',headers:{'Content-Type':'application/json'}})).status);
  assert.equal(rejected,403);
  const job=await page.evaluate(async()=> (await fetch('/api/health/job')).json());
  if(job.status==='idle')await page.click('#calculate');
  await page.waitForFunction(async()=> (await (await fetch('/api/health/job')).json()).status==='complete',{timeout:240000});
  for(const viewport of [{width:1440,height:1000},{width:390,height:844}]){
   await page.setViewport(viewport);await page.goto(base+'/src/visualization/viewer/?scenario=imperial_corridor_8km');
   await page.waitForFunction(()=>window.urbanViewer&&document.querySelector('#health-inspection'),{timeout:60000});
   assert.equal(await page.$$eval('[data-health-plot]',e=>e.length),7);
   const seek=t=>page.$eval('#time',(e,t)=>{e.value=t;e.dispatchEvent(new Event('input'));},t);
   await seek(0);const initial=await page.$eval('[data-metric=distance]',e=>e.textContent),startPosition=await page.evaluate(()=>window.urbanViewer.healthInspections[0].position);
   const end=await page.$eval('#time',e=>Number(e.max));await seek(end);
   assert.notEqual(await page.$eval('[data-metric=distance]',e=>e.textContent),initial);
   assert.notDeepEqual(await page.evaluate(()=>window.urbanViewer.healthInspections[0].position),startPosition);
   await page.click('#play');await page.waitForFunction(()=>Number(document.querySelector('#time').value)>0&&Number(document.querySelector('#time').value)<Number(document.querySelector('#time').max));
   await page.click('#play');const paused=await page.$eval('#time',e=>e.value);await delay(350);assert.equal(await page.$eval('#time',e=>e.value),paused);
   await page.click('#health-inspection button');assert.equal(await page.$eval('#health-inspection button',e=>e.getAttribute('aria-pressed')),'true');
   await seek(0);const camera=await page.evaluate(()=>window.urbanViewer.healthInspections[0].camera);await seek(end);
   assert.notDeepEqual(await page.evaluate(()=>window.urbanViewer.healthInspections[0].camera),camera);
   await page.click('#health-inspection button:nth-of-type(2)');assert.equal(await page.$eval('#health-inspection button:nth-of-type(2)',e=>e.textContent),'Show route');
   assert.equal(await page.evaluate(()=>window.urbanViewer.healthInspections[0].visible),false);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  }
  for(const corrupt of [false,true]){
   const failure=await browser.newPage();await failure.setRequestInterception(true);
   failure.on('request',r=>r.url().endsWith('/health-recording.json')?r.respond({status:corrupt?200:503,contentType:'application/json',body:'{}'}):r.continue());
   await failure.goto(base+'/src/visualization/viewer/?scenario=imperial_corridor_8km');
   await failure.waitForFunction(()=>!document.querySelector('#error').hidden);
   assert.match(await failure.$eval('#error',e=>e.textContent),corrupt?/checksum mismatch/:/unavailable/);
   await failure.close();
  }
  assert.deepEqual(errors,[]);console.log('PASS: local planning boundary, recorded inspection, seek, playback, pause, restart, follow and visibility; desktop/mobile');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
