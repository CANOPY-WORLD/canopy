// PUPPETEER_MODULE=/path/to/puppeteer-core node visualizer/tests/browser_canopy.cjs http://127.0.0.1:8769
const assert=require('node:assert/strict');
const fs=require('node:fs');
const puppeteer=require(process.env.PUPPETEER_MODULE||'puppeteer-core');
(async()=>{
 const base=process.argv[2]||'http://127.0.0.1:8769';
 const browser=await puppeteer.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('requestfailed',r=>errors.push(r.url()+': '+r.failure().errorText));page.on('response',r=>{if(r.status()>=400)errors.push(`${r.status()} ${r.url()}`)});
  await page.setViewport({width:1440,height:1000});
  await page.goto(base+'/src/visualization/viewer/?scenario=demo',{waitUntil:'networkidle0'});
  await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('6 / 6 layers ready'));
  assert.equal(await page.$eval('body',e=>e.dataset.preset),'laboratory');
  const checks=await page.$$('.layer input[type=checkbox]');assert.equal(checks.length,6);await checks[0].click();await checks[0].click();
  await page.$eval('#time',e=>{e.value=1;e.dispatchEvent(new Event('input',{bubbles:true}))});assert.match(await page.$eval('#clock',e=>e.textContent),/1.00/);
  await page.click('#play');await page.click('#play');await page.click('#fit');
  fs.mkdirSync('cache/qa',{recursive:true});await page.screenshot({path:'cache/qa/canopy-desktop.png'});
  await page.setViewport({width:390,height:844});await page.screenshot({path:'cache/qa/canopy-mobile.png'});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile overflow');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,layers:6,viewport:[1440,1000],mobile:[390,844],errors},null,2));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
