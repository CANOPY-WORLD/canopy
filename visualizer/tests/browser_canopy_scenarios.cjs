// Requires the local imported scenes; generates no source data and starts no solver.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const puppeteer=require(process.env.PUPPETEER_MODULE||'puppeteer-core');
(async()=>{
 const base=process.argv[2]||'http://127.0.0.1:8769';
 const browser=await puppeteer.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)errors.push(`${r.status()} ${r.url()}`)});
  await page.setViewport({width:1440,height:1000});await page.goto(base+'/',{waitUntil:'networkidle0'});
  assert.match(page.url(),/catalog/);assert.equal((await page.$$('article.card')).length,1);
  assert.match(await page.$eval('article.card',e=>e.textContent),/imperial_corridor_8km/);
  fs.mkdirSync('cache/qa',{recursive:true});await page.screenshot({path:'cache/qa/canopy-catalog.png'});
  await page.setViewport({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:'cache/qa/canopy-catalog-mobile.png'});
  const summary=[];
  for(const [scenario,count] of [['imperial_corridor_8km',9]]){
   await page.setViewport({width:1440,height:1000});await page.goto(base+`/src/visualization/viewer/?scenario=${scenario}`,{waitUntil:'networkidle0',timeout:90000});
   await page.waitForFunction(()=>Boolean(window.urbanViewer),{timeout:90000});
   assert.equal(await page.$eval('#status',e=>e.textContent),`${count} / ${count} layers ready`);
   const frameChecks=await page.evaluate(async()=>{
    const out=[];
    for(const w of window.urbanViewer.widgets){
     if(w.layer.sampling==='static')continue;
     const sample=w.context.manifest.time.samples.at(-1);await w.setTime(sample);
     if(!w.available)throw new Error('Last sample unavailable: '+w.layer.id);
     out.push({layer:w.layer.id,last_sample:sample});
    }
    return out;
   });
   await page.evaluate(()=>window.urbanViewer.setTime(0));await page.click('#fit');await page.screenshot({path:`cache/qa/${scenario}-unified.png`});
   summary.push({scenario,layers:count,frames:frameChecks});
  }
  assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,scenarios:summary,errors},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
