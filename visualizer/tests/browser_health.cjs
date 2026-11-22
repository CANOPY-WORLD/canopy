const assert=require('node:assert/strict');
const fs=require('node:fs');
const puppeteer=require(process.env.PUPPETEER_MODULE||'puppeteer-core');
(async()=>{
 const base=process.argv[2]||'http://127.0.0.1:8772';
 const browser=await puppeteer.launch({executablePath:process.env.CHROME_PATH,headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('requestfailed',r=>errors.push(r.url()));
  page.on('response',r=>{if(r.status()>=400)errors.push(`${r.status()} ${r.url()}`)});
  await page.setViewport({width:1440,height:1000});
  await page.goto(base+'/src/visualization/viewer/?scenario=health_example',{waitUntil:'networkidle0'});
  await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('8 / 8 layers ready'));
  assert.equal((await page.$$('.layer input[type=checkbox]')).length,8);
  assert.equal((await page.$$('canvas.series')).length,7);
  await page.$eval('#time',e=>{e.value=1800;e.dispatchEvent(new Event('input',{bubbles:true}))});
  assert.match(await page.$eval('#clock',e=>e.textContent),/1800/);
  await page.click('#play');await page.click('#play');
  const checkbox=await page.$('.layer input[type=checkbox]');await checkbox.click();await checkbox.click();
  fs.mkdirSync('cache/qa',{recursive:true});await page.screenshot({path:'cache/qa/health-local-viewer.png'});
  await page.setViewport({width:390,height:844});
  await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth,{timeout:5000});
  assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,layers:8,charts:7,seek_s:1800,errors}));
 } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
