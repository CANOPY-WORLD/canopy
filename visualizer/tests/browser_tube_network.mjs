import assert from 'node:assert/strict';
import fs from 'node:fs';
const {default:puppeteer}=await import(process.env.PUPPETEER_MODULE||'puppeteer-core');
const out=process.env.QA_OUTPUT||'cache/tube-network-review';fs.mkdirSync(out,{recursive:true});
const browser=await puppeteer.launch({executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface']});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
try{
 const page=await browser.newPage();await page.setViewport({width:1280,height:800});const errors=[];let sourceRequests=0;
 page.on('pageerror',e=>{errors.push(e.message);console.error(e.message);});page.on('request',r=>{if(r.url().includes('/scene_data.js'))sourceRequests++;});
 await page.goto(process.argv[2]||'http://127.0.0.1:8835/canopy/viewer/3d/?scene=imperial_corridor_8km');
 await page.waitForFunction(()=>window.viewer&&document.querySelector('#loading').classList.contains('hide'),{timeout:360000});console.log('Full city loaded');
 await page.click('[data-shot="londonTube"]');await page.waitForFunction(()=>window.canopyTube?.group.visible,{timeout:120000});await sleep(3000);
 assert.deepEqual(await page.evaluate(()=>[canopyTube.stations.length,canopyTube.platformCount,canopyTube.routes.length]),[4,8,6]);
 assert(await page.evaluate(()=>canopyTube.selection==='network'&&canopyTube.network.visible&&canopyTube.group.parent===viewer.scene&&document.querySelectorAll('iframe').length===0));
 await page.screenshot({path:`${out}/network.png`});
 const ids=await page.evaluate(()=>canopyTube.stations.map(s=>s.id));
 for(const id of ids){
   await page.select('#tube-view',id);await page.waitForFunction(()=>!canopyTube.journey.playing,{timeout:15000});
   assert(await page.evaluate(id=>canopyTube.platform.station_id===id&&viewer.camera.position.y<0&&!canopyTube.network.visible,id));
   await page.screenshot({path:`${out}/${id}.png`});
   await page.click('#play');await sleep(200);await page.click('#play');const t=await page.evaluate(()=>canopyTube.journey.time);await sleep(200);assert.equal(await page.evaluate(()=>canopyTube.journey.time),t);
   await page.$eval('#step',e=>{e.value=e.max;e.dispatchEvent(new Event('input',{bubbles:true}))});
 }
 assert.equal(sourceRequests,1);
 await page.select('#tube-view','network');await page.click('[data-shot="interior"]');await sleep(300);assert(await page.$eval('#tube-view',e=>e.hidden));assert.equal(await page.evaluate(()=>canopyTube.journey.playing),false);
 await page.click('[data-shot="londonTube"]');await page.emulateMediaFeatures([{name:'prefers-reduced-motion',value:'reduce'}]);await page.select('#tube-view','940GZZLUSKS');assert.equal(await page.evaluate(()=>canopyTube.journey.playing),false);
 await page.select('#tube-view','network');await page.setViewport({width:768,height:1024});await page.$eval('#tube-view',e=>e.scrollIntoView({block:'nearest',inline:'nearest'}));
 assert(await page.$eval('#tube-view',e=>{const r=e.getBoundingClientRect();return !e.hidden&&r.left>=0&&r.right<=innerWidth}));await page.screenshot({path:`${out}/network-ipad.png`});
 // Bounds of all four stations remain in view after fitting the narrow viewport.
 const fits=await page.evaluate(()=>canopyTube.stations.every(s=>{const o=canopyTube.group.getObjectByName(s.primary),p=o.getWorldPosition(new viewer.THREE.Vector3()).project(viewer.camera);return Math.abs(p.x)<.95&&Math.abs(p.y)<.95}));assert(fits);
 await page.emulateMediaFeatures([{name:'prefers-reduced-motion',value:'no-preference'}]);await page.setViewport({width:1280,height:800});await page.select('#tube-view','network');await sleep(3000);
 if(process.env.RECORD==='1'){
   const rec=await page.screencast({path:`${out}/demo.webm`,format:'webm',fps:24,ffmpegPath:process.env.FFMPEG_PATH});await sleep(3000);
   for(const id of ['940GZZLUSKS','940GZZLUKNB','940GZZLUGTR','940GZZLUECT']){await page.select('#tube-view',id);await sleep(7500);}
   await page.select('#tube-view','network');await sleep(4000);await rec.stop();
 }
 assert.deepEqual(errors,[]);fs.writeFileSync(`${out}/verification.json`,JSON.stringify({passed:true,errors,stations:ids,platforms:8,connections:6,sourceRequests,checks:['source routes and eight platforms','native scene','station selector','bounded playback','inactive clock','reduced motion','iPad network fit','one source download']},null,2));console.log('PASS four-station Tube network');
}finally{await browser.close()}
