// Actual city Health + WASD interaction; run against the local Health service.
const assert=require('node:assert/strict');
(async()=>{
 const {default:puppeteer}=await import(process.env.CANOPY_PUPPETEER||'puppeteer-core');
 const browser=await puppeteer.launch({executablePath:process.env.CANOPY_BROWSER_PATH||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage();await page.setViewport({width:1280,height:800});
  await page.goto(process.env.CANOPY_CITY_URL||'http://127.0.0.1:8827/viewer/3d/?scene=imperial_corridor_8km&health=local&pedestrian=1&play=0&lite=0');
  await page.waitForFunction(()=>window.viewer?.renderer,{timeout:180000});
  if(process.env.CANOPY_QA_PAUSE_RENDER==='1')await page.evaluate(()=>{viewer.renderer.render=()=>{}});
  await page.waitForFunction(()=>window.canopyLocalHealth?.active&&window.canopyNavigation,{timeout:180000});
  await page.click('#cr-follow');
  await page.click('.navigation-control button');
  assert.equal(await page.$eval('#cr-follow',e=>e.checked),false,'WASD releases follow');
  assert.equal(await page.evaluate(()=>canopyNavigation.active),true);
  const start=await page.evaluate(()=>viewer.camera.position.toArray());
  await page.keyboard.down('w');await new Promise(r=>setTimeout(r,200));await page.keyboard.up('w');
  assert.notDeepEqual(await page.evaluate(()=>viewer.camera.position.toArray()),start);
  await page.click('#cr-follow');
  assert.equal(await page.evaluate(()=>canopyNavigation.manual),false,'Follow releases manual ownership');
  await page.click('.navigation-control button');await page.click('#cr-focus');
  assert.equal(await page.evaluate(()=>canopyNavigation.active),false,'Frame route exits WASD');
  await page.evaluate(()=>{const h=canopyLocalHealth;h.seekWorld(h.start);h.setPlaying(true)});
  await new Promise(r=>setTimeout(r,100));
  await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));});
  const before=await page.evaluate(()=>canopyLocalHealth.time);await new Promise(r=>setTimeout(r,400));
  assert.equal(await page.evaluate(()=>canopyLocalHealth.time),before,'Hidden tab does not advance');
  await page.evaluate(()=>{delete document.hidden;document.dispatchEvent(new Event('visibilitychange'));});
  await new Promise(r=>setTimeout(r,100));
  assert((await page.evaluate(()=>canopyLocalHealth.time))-before<.3,'No background catch-up');
  await page.click('#tabs [data-shot=overview]');assert.equal(await page.evaluate(()=>canopyLocalHealth.active),false);
  console.log('PASS Health follow/WASD handoff, route focus, background clock, widget exit');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
