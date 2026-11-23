import assert from 'node:assert/strict';
import fs from 'node:fs';
const {default:puppeteer}=await import(process.env.PUPPETEER_MODULE||'puppeteer-core');
const out=process.env.QA_OUTPUT||'cache/native-tube-review';fs.mkdirSync(out,{recursive:true});
const browser=await puppeteer.launch({executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface']});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
try{
 const page=await browser.newPage();await page.setViewport({width:1280,height:800});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.argv[2]||'http://127.0.0.1:8834/canopy/viewer/3d/?scene=imperial_corridor_8km');
 await page.waitForFunction(()=>window.viewer&&document.querySelector('#loading').classList.contains('hide'),{timeout:360000});console.log('Loaded full city');
 const click=shot=>page.click(`[data-shot="${shot}"]`);
 const seek=value=>page.$eval('#step',(e,v)=>{e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}))},value);
 assert(await page.evaluate(()=>document.querySelector('[data-shot="interior"]').nextElementSibling.dataset.shot==='londonTube'));
 // Network failure must preserve the current scene and provide a retry.
 await page.setRequestInterception(true);let rejectTube=true;
 page.on('request',r=>{if(rejectTube&&r.url().includes('/scene_data.js'))r.abort().catch(()=>{});else r.continue().catch(()=>{});});
 await click('londonTube');await page.waitForFunction(()=>document.querySelector('[data-shot="londonTube"]').textContent.includes('retry'));
 assert(await page.$eval('[data-shot="overview"]',e=>e.classList.contains('active')));
 rejectTube=false;await click('londonTube');await click('whiteCity');await sleep(500);
 assert(await page.$eval('[data-shot="whiteCity"]',e=>e.classList.contains('active')));
 await click('londonTube');await page.waitForFunction(()=>window.canopyTube?.group.visible,{timeout:120000});await page.select('#tube-view','940GZZLUSKS');await sleep(6000);
 assert(await page.evaluate(()=>canopyTube.group.parent===viewer.scene&&document.querySelectorAll('iframe').length===0));
 assert.equal(await page.evaluate(()=>canopyTube.sha256),'01697290c7b3018b4a7a48b1394294e491a288bd758f493d3926147192462db6');
 assert(await page.evaluate(()=>viewer.camera.position.y<0&&viewer.controls.enabled&&!canopyTube.journey.playing));
 await page.screenshot({path:`${out}/tube.png`});
 await page.click('#play');await sleep(400);await page.click('#play');const paused=await page.evaluate(()=>canopyTube.journey.time);await sleep(200);assert.equal(await page.evaluate(()=>canopyTube.journey.time),paused);
 await seek(3);assert.equal(await page.evaluate(()=>canopyTube.journey.time),3);
 await page.click('#play');await page.mouse.move(700,400);await page.mouse.wheel({deltaY:10});assert.equal(await page.evaluate(()=>canopyTube.journey.playing),false);
 // Starts from the exact currently rendered pose, including from underground and UAV.
 for(const shot of ['londonTube','overview','uavs','traffic']){
   await click(shot);await sleep(3000);
   const delta=await page.evaluate(()=>{const before=viewer.camera.position.clone();document.querySelector('[data-shot="interior"]').click();return before.distanceTo(viewer.camera.position)});assert(delta<1e-6);
   await sleep(300);assert(await page.evaluate(()=>ihubInterior.group.visible&&!canopyTube.group.visible));
   await seek(await page.evaluate(()=>ihubInterior.journey.duration));
   assert(await page.evaluate(()=>viewer.controls.enabled&&Math.abs(viewer.camera.position.y-(33.947796516331146+ihubInterior.group.position.y))<.02));
 }
 await page.screenshot({path:`${out}/ihub.png`});
 // Physics-to-interior also restores the shared city.
 await page.click('[data-field="solar"]');await sleep(1000);await click('interior');await sleep(500);
 assert(await page.evaluate(()=>ihubInterior.group.visible));
 await page.emulateMediaFeatures([{name:'prefers-reduced-motion',value:'reduce'}]);
 await click('londonTube');assert(await page.evaluate(()=>!canopyTube.journey.playing&&canopyTube.journey.time===canopyTube.journey.duration));
 await click('interior');assert(await page.evaluate(()=>!ihubInterior.journey.playing&&ihubInterior.journey.time===ihubInterior.journey.duration));
 await page.setViewport({width:768,height:1024});await click('londonTube');await page.screenshot({path:`${out}/tube-ipad.png`});
 assert(await page.$eval('.timebar',e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight}));
 await page.emulateMediaFeatures([{name:'prefers-reduced-motion',value:'no-preference'}]);await page.setViewport({width:1280,height:800});
 if(process.env.RECORD==='1'){
   await click('overview');await sleep(3000);
   const recorder=await page.screencast({path:`${out}/demo.webm`,format:'webm',fps:24,ffmpegPath:process.env.FFMPEG_PATH});
   await sleep(2000);await click('londonTube');await sleep(9000);
   await page.mouse.move(660,420);await page.mouse.down();await page.mouse.move(720,430,{steps:25});await page.mouse.up();await sleep(2000);
   assert(await page.evaluate(()=>viewer.camera.position.distanceTo(canopyTube.pose.pos)<2));
   await click('interior');await sleep(16000);await click('whiteCity');await sleep(3500);await recorder.stop();
 }
 assert.deepEqual(errors,[]);fs.writeFileSync(`${out}/verification.json`,JSON.stringify({passed:true,errors,checks:['single scene and renderer','source checksum','failure and retry','late-load cancellation','pause seek manual takeover','Tube Overview UAV Traffic and field to I-HUB','reduced motion','iPad viewport']},null,2));console.log('PASS native Tube / I-HUB transitions');
}finally{await browser.close()}
