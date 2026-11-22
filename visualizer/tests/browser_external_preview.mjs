// Live integration check: requires Chrome, Puppeteer, and both public sites.
const {default: puppeteer} = await import(process.env.PUPPETEER_MODULE || 'puppeteer-core');
import assert from 'node:assert/strict';
import fs from 'node:fs';
fs.mkdirSync('cache/tube-review',{recursive:true});
const browser=await puppeteer.launch({executablePath:process.env.CHROME_PATH || '/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface']});
try {
const page=await browser.newPage();await page.setViewport({width:1280,height:800,deviceScaleFactor:1});
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.goto(process.argv[2] || 'http://127.0.0.1:8831/canopy/viewer/3d/?scene=imperial_corridor_8km&lite=1&play=0');
await page.waitForFunction(()=>window.viewer&&document.querySelector('#loading').classList.contains('hide'),{timeout:360000});
console.log('Viewer ready');
assert.equal(await page.$('iframe'),null);
const order=await page.$$eval('#tabs [data-shot]',els=>els.map(e=>e.dataset.shot));assert.equal(order[order.indexOf('interior')+1],'londonTube');
await page.click('[data-shot="londonTube"]');
await page.waitForFunction(()=>document.querySelector('#external-preview iframe'));
const frame=await (await page.$('#external-preview iframe')).contentFrame();
await frame.waitForFunction(()=>window.canopyTubeIntro,{timeout:180000});
assert.equal(await frame.evaluate(()=>canopyTubeIntro.phase),'overview');
await frame.waitForFunction(()=>canopyTubeIntro.phase==='station',{timeout:25000});
console.log('External preview intro ready');
assert.equal(await page.$eval('[data-shot="londonTube"]',e=>e.getAttribute('aria-pressed')),'true');
assert.equal(await page.$eval('.timebar',e=>getComputedStyle(e).display),'none');
await frame.click('#play');await frame.click('#quick-journey');
await page.screenshot({path:'cache/tube-review/desktop.png'});
await page.setViewport({width:768,height:1024,deviceScaleFactor:1});
await page.screenshot({path:'cache/tube-review/ipad.png'});
const bounds=await page.$eval('#external-preview',e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,width:r.width};});
assert(bounds.top>50&&bounds.bottom===1024&&bounds.width===768);
await page.click('[data-shot="overview"]');assert.equal(await page.$('iframe'),null);assert.notEqual(await page.$eval('.timebar',e=>getComputedStyle(e).display),'none');
await page.click('[data-shot="interior"]');assert.equal(await page.$eval('[data-shot="interior"]',e=>e.getAttribute('aria-pressed')),'true');
await page.click('[data-shot="londonTube"]');await page.click('[data-shot="overview"]');assert.equal(await page.$('iframe'),null);
// Reduced motion keeps the region overview and does not start an automatic zoom.
await page.emulateMediaFeatures([{name:'prefers-reduced-motion',value:'reduce'}]);
await page.click('[data-shot="londonTube"]');
const reducedFrame=await (await page.$('#external-preview iframe')).contentFrame();
await reducedFrame.waitForFunction(()=>window.canopyTubeIntro?.phase==='overview-static',{timeout:180000});
assert.equal(await page.$eval('#external-preview iframe',e=>e.sandbox.contains('allow-same-origin')),false);
await page.click('[data-shot="overview"]');
await page.emulateMediaFeatures([{name:'prefers-reduced-motion',value:'no-preference'}]);
await page.click('[data-shot="londonTube"]');
const manualFrame=await (await page.$('#external-preview iframe')).contentFrame();
await manualFrame.waitForFunction(()=>window.canopyTubeIntro,{timeout:180000});
await manualFrame.click('#toggle');
await manualFrame.waitForFunction(()=>canopyTubeIntro.phase==='manual');
await page.click('[data-shot="overview"]');
assert.equal(await page.$('iframe'),null);
fs.writeFileSync('cache/tube-review/browser.json',JSON.stringify({passed:true,order,bounds,errors},null,2));assert.deepEqual(errors,[]);console.log('PASS');
}finally{await browser.close()}
