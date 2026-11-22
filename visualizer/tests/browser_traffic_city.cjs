// Real-data regression: run against a built Canopy website with the pinned London snapshot.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const base=process.argv[2] || 'http://127.0.0.1:8822/canopy/';
const output=process.env.CANOPY_QA_OUTPUT || 'cache/traffic-city';
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const {default:p}=await import(process.env.PUPPETEER_MODULE || 'puppeteer-core');
 const browser=await p.launch({executablePath:process.env.CHROME_PATH || '/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface']});
 try{
  const page=await browser.newPage(),errors=[];page.setDefaultTimeout(120000);await page.setViewport({width:1280,height:720});
  page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('favicon.ico'))errors.push(m.text())});
  page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400&&!r.url().endsWith('favicon.ico'))errors.push(`${r.status()} ${r.url()}`)});
  await page.goto(new URL('viewer/3d/?scene=imperial_corridor_8km',base).href,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.viewer&&document.querySelector('#loading').classList.contains('hide'),{timeout:240000});
  assert.equal(await page.$eval('[data-shot="overview"]',e=>e.getAttribute('aria-pressed')),'true');
  await page.click('[data-shot="traffic"]');await new Promise(r=>setTimeout(r,2000));
  assert(await page.evaluate(()=>corridorContext.nativeTraffic&&corridorContext.meta.dt===.1&&corridorContext.frames.length===410));
  await page.click('#play');assert.equal(await page.evaluate(()=>corridorContext.playing),false);
  const seek=async value=>{await page.$eval('#step',(e,value)=>{e.value=value;e.dispatchEvent(new Event('input',{bubbles:true}))},value);await new Promise(r=>setTimeout(r,150));await page.waitForFunction(()=>!viewer.state.loading);};
  await seek(125.5);assert.equal(await page.evaluate(()=>corridorContext.position),125.5);
  await page.screenshot({path:path.join(output,'traffic.jpg'),type:'jpeg',quality:90});
  const traffic=await page.evaluate(()=>({meta:corridorContext.meta,position:corridorContext.position,visible:viewer.scene.children.filter(x=>x.visible).map(x=>x.name||x.type)}));console.log('Traffic',JSON.stringify(traffic));
  assert(await page.evaluate(()=>cityDetailTiles.group.visible && cityDetailTiles.loaded.length===64));
  assert(await page.evaluate(()=>!corridorTerrain.enabled && corridorContext.ground.visible && corridorContext.vegetation.visible));
  assert(traffic.visible.length>4);
  console.log('City context visible');
  await seek(409);await page.click('#play');await page.waitForFunction(()=>corridorContext.playing&&corridorContext.position<50);await page.click('#play');
  await page.click('[data-field="solar"]');await page.waitForFunction(()=>viewer.state.phase==='solar'&&!viewer.state.loading&&viewer.state.fields.solar);
  console.log('Solar bounds',await page.$eval('#step',e=>[e.min,e.max,e.value]));
  assert.deepEqual(await page.$eval('#step',e=>[Number(e.min),Number(e.max)]),[21,88]);
  if(await page.$eval('#play',e=>e.getAttribute('aria-label')==='Pause'))await page.click('#play');
  await seek(88);await page.click('#play');await page.waitForFunction(()=>viewer.state.step>=21&&viewer.state.step<30);
  await page.click('#play');await seek(55);assert(await page.evaluate(()=>viewer.state.fields.solar.reduce((a,b)=>Math.max(a,b),0)>800));await page.screenshot({path:path.join(output,'solar.jpg'),type:'jpeg',quality:90});
  await page.select('#solar-mode','shadow');await page.waitForFunction(()=>!viewer.state.loading&&viewer.state.fields.shadow);
  assert.deepEqual(await page.$eval('#step',e=>[Number(e.min),Number(e.max)]),[21,88]);
  await page.click('[data-shot="overview"]');await new Promise(r=>setTimeout(r,1200));
  assert.equal(await page.evaluate(()=>corridorContext.playing),false);
  assert(await page.evaluate(()=>corridorTerrain.enabled && cityDetailTiles.group.visible));
  await page.screenshot({path:path.join(output,'overview-restored.jpg'),type:'jpeg',quality:90});
  await page.setViewport({width:1024,height:768});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.goto(new URL('viewer/3d/?scene=imperial_corridor_8km&fields=1&phase=solar&solar_day=full&step=1',base).href,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.viewer&&document.querySelector('#loading').classList.contains('hide')&&!viewer.state.loading);
  assert.deepEqual(await page.$eval('#step',e=>[Number(e.min),Number(e.max)]),[1,100]);
  assert(await page.evaluate(()=>viewer.state.fields.solar.every(v=>v===0)));
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(output,'verification.json'),JSON.stringify({passed:true,traffic,daylight:[21,88],fullDay:[1,100],errors},null,2));console.log('PASS');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
