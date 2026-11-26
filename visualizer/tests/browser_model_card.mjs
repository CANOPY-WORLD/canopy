// Run against a Pages build served under /canopy/.
// PUPPETEER_MODULE may point to an installed puppeteer-core ESM entry.
const {default: puppeteer} = await import(process.env.PUPPETEER_MODULE || 'puppeteer-core');
const base = process.argv[2] || 'http://localhost:8870/canopy';
import assert from 'node:assert/strict';
const browser=await puppeteer.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
try{const page=await browser.newPage();await page.goto(base + '/viewer/model-cards/imperial_corridor_8km.json');
await page.evaluate(async(base)=>{const cards=JSON.parse(document.body.innerText);document.body.innerHTML='<nav id="tabs" style="height:50px"></nav>';document.body.className='widget-player';const style=document.createElement('link');style.rel='stylesheet';style.href=base+'/viewer/3d/style.css';document.head.append(style);const {installModelCard}=await import(base+'/viewer/3d/model-card.js');window.card=installModelCard(document.querySelector('#tabs'),cards);card.select('uavs');window.keys=0;window.addEventListener('keydown',()=>keys++);},base);
assert.equal(await page.$eval('#model-card h2',e=>e.textContent),'WavePDE');
await page.click('#model-card button');await page.evaluate(()=>card.select('wind'));
assert(await page.$eval('#model-card-body',e=>e.hidden));
await page.focus('#model-card button');await page.keyboard.press('Space');assert.equal(await page.evaluate(()=>keys),0);assert(await page.$eval('#model-card-body',e=>!e.hidden));
await page.evaluate(()=>card.select('missing'));assert(await page.$eval('#model-card',e=>e.hidden));
await page.evaluate(()=>card.select('poll'));
for(const width of [1280,768,320]){await page.setViewport({width,height:800});const r=await page.$eval('#model-card',e=>({right:e.getBoundingClientRect().right,w:innerWidth}));assert(r.right<=r.w);}
await page.evaluate(()=>{
 card.select('localHealth');
 window.healthFixture={start:0,end:10,time:0,result:{physiology_input_kind:'synthetic',samples:[
 {world_seconds:0,seconds:0,health_score:95,breathing:12,pollution_proxy:0},
 {world_seconds:5,seconds:5,health_score:null,breathing:null,pollution_proxy:null},
 {world_seconds:10,seconds:10,health_score:90,breathing:14,pollution_proxy:3,gap_before:true}]}};
 card.updateHealth(healthFixture);
});
assert.equal(await page.$eval('#health-assessment [data-pollution]',e=>e.textContent),'0.0');
await page.evaluate(()=>{healthFixture.time=4;card.updateHealth(healthFixture);});
assert.equal(await page.$eval('#health-assessment [data-breathing]',e=>e.textContent),'12.0');
await page.evaluate(()=>{healthFixture.time=5;card.updateHealth(healthFixture);});
assert.equal(await page.$eval('#health-assessment [data-score]',e=>e.textContent),'Unavailable');
assert.equal(await page.$eval('#health-assessment [data-trend]',e=>(e.getAttribute('d').match(/M/g)||[]).length),2);
await page.evaluate(()=>card.select('wind'));
assert(await page.$eval('#health-assessment',e=>e.hidden));
console.log('PASS selection, unknown card, collapsed-state persistence, Space isolation and 320–1280 px bounds');
}finally{await browser.close()}
