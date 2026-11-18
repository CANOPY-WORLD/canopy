// Real London data, widget switching and the sole visible playback controls.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const puppeteer = require(process.env.PUPPETEER_MODULE || 'puppeteer-core');

(async () => {
  const base = new URL(process.argv[2] || 'http://127.0.0.1:8784/canopy/');
  const pauseRender = process.env.CANOPY_QA_PAUSE_RENDER === '1';
  const browser = await puppeteer.launch({executablePath:process.env.CHROME_PATH || '/opt/google/chrome/chrome',
    headless:true, args:['--no-sandbox','--enable-unsafe-swiftshader']});
  const errors = [], checks = [];
  try {
    const page = await browser.newPage();
    page.setDefaultTimeout(60000);
    page.on('pageerror', e => { errors.push(e.message); console.error(e.message); });
    page.on('console', m => { if(m.type() === 'error') errors.push(m.text()); });
    page.on('response', r => { if(r.status() >= 400 && !r.url().endsWith('/favicon.ico')) errors.push(`${r.status()} ${r.url()}`); });
    await page.setViewport({width:1440,height:1000});
    await page.goto(new URL('viewer/3d/?scene=imperial_corridor_8km&lite=1',base).href,{waitUntil:'domcontentloaded'});
    await page.waitForFunction(() => !!window.viewer,{timeout:120000});
    if(pauseRender) await page.evaluate(() => { window.qaRender=viewer.renderer.render; viewer.renderer.render=()=>{}; });
    await page.waitForFunction(() => viewer.model.children.length && document.querySelector('#loading').classList.contains('hide'),{timeout:120000});
    const ready = () => page.waitForFunction(() => !document.querySelector('#play').disabled);
    const clickWidget = async selector => {
      await page.$eval(selector, el => el.scrollIntoView({block:'nearest',inline:'nearest'}));
      await page.click(selector);
      await page.waitForFunction(selector => document.querySelector(selector).getAttribute('aria-pressed') === 'true',{},selector);
    };
    const pause = async () => {
      if(await page.$eval('#play', el => el.getAttribute('aria-label') === 'Pause')) await page.click('#play');
      await page.waitForFunction(() => document.querySelector('#play').getAttribute('aria-label') === 'Play');
    };
    const seek = async value => {
      await page.$eval('#step', (el,value) => {el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));},value);
    };
    const stationary = async read => {
      const before = await page.evaluate(read);
      await new Promise(resolve => setTimeout(resolve,350));
      assert.equal(await page.evaluate(read),before,'Paused clock must stay fixed');
    };
    const advances = async read => {
      const before=await page.evaluate(read);
      await page.click('#play');
      const deadline=Date.now()+60000;
      while(await page.evaluate(read) === before && Date.now()<deadline) await new Promise(resolve=>setTimeout(resolve,100));
      assert.notEqual(await page.evaluate(read),before,'Playing must advance the selected clock');
      await pause();
    };
    const minimal = async () => {
      const controls=await page.evaluate(() => [...document.querySelectorAll('button,input,select,a,summary')]
        .filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden')
        .map(el => ({id:el.id,widget:!!el.closest('#tabs')})));
      assert(controls.length>2);
      assert(controls.every(c=>c.widget || ['play','step'].includes(c.id)),JSON.stringify(controls));
      assert.equal(await page.$eval('#viewer-details',el=>el.getBoundingClientRect().height),0);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    };
    await ready(); await minimal(); await pause();
    await seek(20);
    const orbit = () => Number(document.querySelector('#step').value);
    assert.equal(await page.evaluate(orbit),20);
    await stationary(orbit); await advances(orbit);
    checks.push('Overview orbit: pause, seek, resume'); console.log(checks.at(-1));

    await clickWidget('[data-shot=whiteCity]');
    await page.waitForFunction(()=>document.querySelector('#play').disabled && document.querySelector('#step').disabled);
    checks.push('Static campus view: no invented timeline');

    await clickWidget('[data-shot=traffic]'); await ready(); await pause();
    await seek(10);
    const traffic = () => corridorContext.frame;
    assert.equal(await page.evaluate(traffic),10);
    await stationary(traffic); await advances(traffic);
    await seek(await page.$eval('#step',el=>el.max));
    await page.click('#play');
    await page.waitForFunction(()=>corridorContext.frame < corridorContext.frames.length-1 && corridorContext.playing);
    await pause(); await minimal();
    checks.push('Traffic: play, pause, seek, restart'); console.log(checks.at(-1));

    await clickWidget('[data-shot=uavs]'); await ready(); await pause();
    const uav=()=>viewer.uavs.t;
    await seek(5); assert(Math.abs((await page.evaluate(uav))-5)<0.11);
    await stationary(uav); await advances(uav);
    await seek(await page.$eval('#step',el=>Number(el.max)-1));
    await page.click('#play');
    await page.waitForFunction(()=>viewer.uavs.t>=viewer.uavs.duration && !viewer.uavs.playing);
    await page.click('#play');
    await page.waitForFunction(()=>viewer.uavs.t<viewer.uavs.duration && viewer.uavs.playing);
    await pause(); await minimal();
    checks.push('UAV: play, pause, seek, restart'); console.log(checks.at(-1));

    await clickWidget('[data-shot=birds]'); await ready(); await pause();
    const birds=()=>canopyBirds.time;
    await seek(60); assert.equal(await page.evaluate(birds),60);
    await stationary(birds); await advances(birds); await minimal();
    checks.push('Birds: play, pause, seek'); console.log(checks.at(-1));

    const fieldNames=await page.$$eval('#tabs [data-field]',els=>els.map(el=>el.dataset.field));
    for(const field of fieldNames) {
      await clickWidget(`[data-field=${field}]`); await ready(); await pause();
      await page.waitForFunction(()=>!viewer.state.loading);
      const fieldStep=()=>viewer.state.step;
      await seek(2); await page.waitForFunction(()=>!viewer.state.loading && viewer.state.step===2);
      await stationary(fieldStep); await advances(fieldStep);
      await seek(await page.$eval('#step',el=>el.max));
      await page.waitForFunction(()=>!viewer.state.loading);
      const last=await page.evaluate(fieldStep);
      // Let the final sample finish naturally; it must keep this widget selected.
      await seek(last-1); await page.waitForFunction(()=>!viewer.state.loading);
      await page.click('#play');
      await page.waitForFunction(last=>viewer.state.step===last && !viewer.state.playing,{},last);
      assert.equal(await page.evaluate(()=>viewer.state.phase),field);
      await advances(fieldStep); await minimal();
      assert.equal(await page.evaluate(()=>corridorContext.playing),false);
      assert.equal(await page.evaluate(()=>viewer.uavs.playing),false);
      checks.push(`${field}: play, pause, seek, last sample, restart`); console.log(checks.at(-1));
    }

    // A field request followed immediately by another selection may finish later.
    await page.evaluate(()=>{document.querySelector('[data-field=wind]').click();document.querySelector('[data-shot=traffic]').click();});
    await page.waitForFunction(()=>document.querySelector('[data-shot=traffic]').getAttribute('aria-pressed')==='true');
    await ready(); await pause(); await seek(7);
    assert.equal(await page.evaluate(traffic),7);
    await stationary(traffic);
    checks.push('Rapid switching keeps the latest widget and clock');
    await clickWidget('[data-shot=overview]'); await ready(); await pause();
    await new Promise(resolve=>setTimeout(resolve,2800));
    fs.mkdirSync('cache/qa/widget-player',{recursive:true});
    for(const viewport of [{width:1440,height:1000},{width:390,height:844}]) {
      await page.setViewport(viewport); await minimal();
      if(pauseRender) await page.evaluate(()=>{viewer.renderer.setPixelRatio(.6);qaRender.call(viewer.renderer,viewer.scene,viewer.camera);});
      await page.screenshot({path:`cache/qa/widget-player/${viewport.width}.png`});
    }
    await page.focus('#step'); const before=await page.evaluate(orbit); await page.keyboard.press('ArrowRight');
    assert((await page.evaluate(orbit))>before);
    await minimal();
    assert.deepEqual(errors,[]);
    const result={passed:true,checks,geometry:'existing lightweight London mode',continuousRenderingPaused:pauseRender,viewports:[1440,390],errors};
    fs.writeFileSync('cache/qa/widget-player/results.json',JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify(result,null,2));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});
