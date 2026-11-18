// Two tiny isolated API fixtures exercise real Viewer navigation; no catalog edits.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const puppeteer = require(process.env.PUPPETEER_MODULE || 'puppeteer-core');

(async () => {
  const base = (process.argv[2] || 'http://127.0.0.1:8769').replace(/\/$/, '');
  const fixture = path.resolve(__dirname, '../../model/tests/fixtures/contract-v1');
  const original = JSON.parse(fs.readFileSync(path.join(fixture, 'manifest.json')));
  const scenarios = ['test_a','test_b'].map(id => ({scenario_id:id,title:`Scenario ${id}`,available:true}));
  scenarios.push({scenario_id:'unavailable',title:'Unavailable test data',available:false});
  const browser = await puppeteer.launch({executablePath:process.env.CHROME_PATH || '/opt/google/chrome/chrome',
    headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror',e => errors.push(e.message));
    await page.setRequestInterception(true);
    page.on('request',request => {
      const url = new URL(request.url());
      const reply = data => request.respond({status:200,contentType:'application/json',body:JSON.stringify(data)});
      if(url.pathname === '/api/canopy/scenarios') return reply(scenarios);
      const view = url.pathname.match(/^\/api\/canopy\/scenarios\/(test_[ab])\/visualization$/);
      if(view) {
        const id = view[1];
        return reply({scenario_id:id,title:`Scenario ${id}`,spatial:original.spatial,
          profile:{preset:'laboratory',time_alignment:'relative'},
          runs:[{url:`/project/${id}/runs/run_${id}/manifest.json`}],
          layers:original.layers.map(layer => ({run_id:`run_${id}`,layer_id:layer.id,visible:true}))});
      }
      const payload = url.pathname.match(/^\/project\/(test_[ab])\/runs\/run_test_[ab]\/(manifest.json|data\/[a-z_]+\.json)$/);
      if(payload) {
        const data = JSON.parse(fs.readFileSync(path.join(fixture,payload[2])));
        if(payload[2] === 'manifest.json') {data.scene_id=payload[1];data.run_id=`run_${payload[1]}`;}
        return reply(data);
      }
      request.continue();
    });
    const loaded = async id => {
      await page.waitForFunction(id => window.urbanViewer?.manifest.scene_id === id &&
        document.querySelector('#status').textContent === '5 / 5 layers ready', {}, id);
      assert.equal(await page.$eval('#scenario-tabs [aria-current]',el=>el.dataset.scenario),id);
      assert.equal((await page.$$('#viewport > canvas')).length,1);
      assert.equal(await page.evaluate(() => new Set(window.urbanViewer.widgets.map(w=>w.context.manifest.scene_id)).size),1);
    };
    await page.setViewport({width:1440,height:1000});
    await page.goto(base+'/src/visualization/viewer/?scenario=test_a',{waitUntil:'networkidle0'});
    await loaded('test_a');
    assert.equal((await page.$$('#scenario-tabs a')).length,2);
    assert.equal(await page.$eval('[data-scenario=unavailable]',el=>el.hasAttribute('href')),false);
    await page.focus('[data-scenario=test_a]');
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.evaluate(()=>document.activeElement.dataset.scenario),'test_b');
    await Promise.all([page.waitForNavigation({waitUntil:'networkidle0'}),page.keyboard.press('Enter')]);
    await loaded('test_b');
    assert.match(page.url(),/scenario=test_b$/);
    await page.goBack({waitUntil:'networkidle0'});
    await loaded('test_a');
    const renders = await page.evaluate(()=>window.urbanViewer.performanceStats.renders);
    await page.evaluate(()=>window.urbanViewer.setTime(1));
    await page.waitForFunction(before=>window.urbanViewer.performanceStats.renders>before,{timeout:5000},renders);
    await page.setViewport({width:390,height:844});
    await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth,{timeout:5000});
    const layout = await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,
      overflow:[...document.querySelectorAll('body *')].filter(el=>{const r=el.getBoundingClientRect();return r.width&&r.right>innerWidth+1;}).map(el=>({tag:el.tagName,id:el.id,class:el.className,right:el.getBoundingClientRect().right})).slice(0,12)}));
    assert(layout.scroll<=layout.width,JSON.stringify(layout));
    const pages = process.argv[3];
    if(pages) {
      const publicPage = await browser.newPage();
      publicPage.on('pageerror',e=>errors.push(e.message));
      await publicPage.setRequestInterception(true);
      publicPage.on('request',request=>{
        // Exercise the shipped header/navigation without downloading city data.
        if(new URL(request.url()).pathname.endsWith('/viewer/pages-bootstrap.js'))
          return request.respond({status:200,contentType:'text/javascript',body:"await import('./scene-navigation.js');"});
        request.continue();
      });
      await publicPage.setViewport({width:390,height:844});
      await publicPage.goto(new URL('viewer/3d/?scene=imperial_corridor_8km',pages).href,{waitUntil:'networkidle0'});
      await publicPage.waitForSelector('#scenario-tabs a[aria-current=page]');
      assert.equal((await publicPage.$$('#scenario-tabs a')).length,1);
      assert(await publicPage.$('#layers details #tabs'));
      assert.equal(await publicPage.$('.top-tabs'),null);
      assert(await publicPage.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      const unknown = await publicPage.evaluate(async()=>{
        history.replaceState(null,'','?scene=not_a_registered_case');
        const {loadScene}=await import('../scene.js');
        try {await loadScene();return null;} catch(error) {return error.message;}
      });
      assert.match(unknown,/Unknown Scenario/);
    }
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({passed:true,fixtureScenarios:2,disabledScenario:1,keyboard:true,history:true,
      publicNavigation:Boolean(pages),errors},null,2));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
