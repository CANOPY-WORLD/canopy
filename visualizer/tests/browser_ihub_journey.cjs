const fs=require('fs'),assert=require('assert/strict');
fs.mkdirSync('cache/white-city-interior',{recursive:true});
(async()=>{
 const {default:p}=await import(process.env.PUPPETEER_MODULE||'puppeteer-core');
 const b=await p.launch({executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox',...(process.env.CANOPY_QA_VULKAN==='1'?['--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface']:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])]});
 try{
 const page=await b.newPage(),errors=[];await page.setViewport({width:960,height:640});
 await page.evaluateOnNewDocument(()=>Object.defineProperty(window,'devicePixelRatio',{get:()=>0.6}));
 page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400&&!r.url().includes('favicon'))errors.push(`${r.status()} ${r.url()}`)});
 await page.goto(process.argv[2]||'http://127.0.0.1:8823/canopy/viewer/3d/?scene=imperial_corridor_8km');
 await page.waitForFunction(()=>window.viewer&&document.querySelector('#loading').classList.contains('hide'),{timeout:360000});
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 await page.click('[data-shot="whiteCity"]');await sleep(3000);
 const recorder=await page.screencast({path:'cache/white-city-interior/journey.webm',format:'webm',fps:24,ffmpegPath:process.env.FFMPEG_PATH});
 await sleep(2000);
 await page.evaluate(()=>{window.journeySamples=[];window.journeySampler=setInterval(()=>{if(ihubInterior.group.visible)journeySamples.push({t:ihubInterior.journey.time,position:viewer.camera.position.toArray(),playing:ihubInterior.journey.playing});},100)});
 await page.click('[data-shot="interior"]');
 assert.equal(await page.$eval('#play',e=>e.disabled),false);
 await sleep(1500);await page.screenshot({path:'cache/white-city-interior/journey-outside.png'});
 await sleep(1000);await page.screenshot({path:'cache/white-city-interior/journey-entry.png'});
 await sleep(2000);await page.screenshot({path:'cache/white-city-interior/journey-arrival.png'});
 await page.waitForFunction(()=>ihubInterior.journey.time>=17,{timeout:45000});await page.screenshot({path:'cache/white-city-interior/journey-inside.png'});
 await page.waitForFunction(()=>!ihubInterior.journey.playing&&ihubInterior.journey.time===30,{timeout:45000});
 assert(await page.evaluate(()=>viewer.controls.enabled&&ihubInterior.group.getObjectByName('Retained v10 continuous ceiling').visible));
 await page.mouse.move(500,330);await page.mouse.down();await page.mouse.move(600,350,{steps:25});await page.mouse.up();await sleep(2000);
 await page.click('[data-shot="overview"]');await sleep(3000);await recorder.stop();
 const samples=await page.evaluate(()=>{clearInterval(journeySampler);return journeySamples});
 assert(samples.some(s=>s.t>4&&s.t<28));
 const interior=samples.filter(s=>s.t>4&&s.t<29);assert(interior.every(s=>Math.abs(s.position[1]-33.947796516331146)<.02));
 assert(Math.hypot(...interior.at(-1).position.map((v,i)=>v-interior[0].position[i]))>3);
 for(let i=1;i<samples.length;i++){const a=samples[i-1],c=samples[i],dt=c.t-a.t;if(dt<=0)continue;assert(Math.hypot(...c.position.map((v,k)=>v-a.position[k]))<dt*800+2);}
 // Pause and scrub use the same clock, and manual dragging takes over immediately.
 await page.click('[data-shot="interior"]');await sleep(500);await page.click('#play');
 const paused=await page.evaluate(()=>ihubInterior.journey.time);await sleep(300);assert.equal(await page.evaluate(()=>ihubInterior.journey.time),paused);
 await page.$eval('#step',e=>{e.value=25;e.dispatchEvent(new Event('input',{bubbles:true}))});assert.equal(await page.evaluate(()=>ihubInterior.journey.time),25);
 await page.click('#play');await page.mouse.move(640,360);await page.mouse.down();await page.mouse.move(690,360,{steps:10});await page.mouse.up();assert.equal(await page.evaluate(()=>ihubInterior.journey.playing),false);
 await page.click('[data-shot="traffic"]');assert.equal(await page.evaluate(()=>ihubInterior.journey.playing),false);
 await page.emulateMediaFeatures([{name:'prefers-reduced-motion',value:'reduce'}]);await page.click('[data-shot="interior"]');assert.equal(await page.evaluate(()=>ihubInterior.journey.time),30);assert.equal(await page.evaluate(()=>ihubInterior.journey.playing),false);
 assert.deepEqual(errors,[]);fs.writeFileSync('cache/white-city-interior/journey-verification.json',JSON.stringify({passed:true,errors,samples,checks:['continuous approach','eye-height indoor movement','roof retained','manual takeover','pause and seek','switch cancels','reduced motion']},null,2));console.log('PASS');
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exit(1)});
