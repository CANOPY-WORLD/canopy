// Real input regression: a tour must yield on the first drag/wheel, and the
// detail loader must follow navigation outside the initial campus footprint.
const assert = require('node:assert/strict'), fs = require('node:fs');
const puppeteer = require(process.env.PUPPETEER_MODULE || 'puppeteer-core');
(async () => {
  const base = new URL(process.argv[2]);
  const browser = await puppeteer.launch({executablePath: process.env.CHROME_PATH || '/opt/google/chrome/chrome',
    headless: true, args: ['--no-sandbox', '--enable-unsafe-swiftshader']});
  const out = 'cache/qa/city-navigation'; fs.mkdirSync(out, {recursive: true});
  const errors = [], report = {continuousRenderingPaused: true, errors};
  try {
    const page = await browser.newPage(); page.setDefaultTimeout(180000);
    await page.setViewport({width: 1100, height: 750});
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(new URL('?play=0', base).href, {waitUntil: 'domcontentloaded'});
    await page.waitForFunction(() => window.viewer);
    await page.evaluate(() => {window.qaRender = viewer.renderer.render; viewer.renderer.render = () => {};});
    await page.waitForFunction(() => window.cityDetailTiles?.progress.complete && window.corridorContext);
    const state = () => page.evaluate(() => ({
      target: viewer.controls.target.toArray(), camera: viewer.camera.position.toArray(),
      distance: viewer.camera.position.distanceTo(viewer.controls.target), tiles: cityDetailTiles.loaded,
      errors: cityDetailTiles.progress.errors, residentTiles: cityDetailTiles.stats.residentTiles,
    }));
    const settle = () => page.evaluate(() => new Promise(resolve => setTimeout(resolve, 1000)));
    const delta = (a, b) => Math.hypot(...a.map((v, i) => v - b[i]));
    async function drag(x0, y0, x1, y1) {
      await page.mouse.move(x0, y0); await page.mouse.down({button: 'right'});
      await page.mouse.move(x1, y1, {steps: 16}); await page.mouse.up({button: 'right'}); await settle();
    }
    report.initial = await state();
    // No preparatory click: this exact gesture was swallowed by the old tour.
    await drag(400, 320, 800, 430);
    report.firstDrag = await state();
    assert(delta(report.initial.target, report.firstDrag.target) > 100, 'First drag must pan immediately');
    assert(Math.abs(report.initial.target[1] - report.firstDrag.target[1]) < 1e-6, 'Panning must stay on the ground plane');
    await page.click('[data-shot=overview]');
    await page.evaluate(() => new Promise(resolve => setTimeout(resolve, 3000)));
    report.beforeWheel = await state();
    await page.mouse.move(850, 420); await page.mouse.wheel({deltaY: -500}); await settle();
    report.firstWheel = await state();
    assert(report.firstWheel.distance < report.beforeWheel.distance * .9, 'First wheel must interrupt the tour and zoom');
    assert(delta(report.firstWheel.target, report.beforeWheel.target) > 30, 'Off-centre zoom must follow the pointer');
    assert(Math.abs(report.firstWheel.target[1] - report.beforeWheel.target[1]) < 1e-6);
    // Cross the city using only real pointer input, not direct camera assignment.
    await page.mouse.move(550, 375); await page.mouse.wheel({deltaY: 1800}); await settle();
    await drag(400, 375, 800, 375);
    await drag(400, 375, 800, 375);
    await page.mouse.wheel({deltaY: -1800}); await settle();
    await page.waitForFunction(() => cityDetailTiles.progress.complete && cityDetailTiles.loaded.length > 0);
    report.moved = await state();
    fs.writeFileSync(`${out}/result.json`, JSON.stringify(report, null, 2) + '\n');
    assert(delta(report.initial.target, report.moved.target) > 1800, 'Navigate beyond the initial campus neighbourhood');
    assert(report.moved.tiles.some(id => !report.initial.tiles.includes(id)), 'Load new detail tiles after panning');
    assert(report.initial.tiles.some(id => !report.moved.tiles.includes(id)), 'Release obsolete campus tiles');
    assert(report.moved.residentTiles <= 6); assert.deepEqual(report.moved.errors, []);
    await page.evaluate(() => {viewer.renderer.setPixelRatio(.6); qaRender.call(viewer.renderer, viewer.scene, viewer.camera);});
    await page.screenshot({path: `${out}/after-navigation.png`});
    assert.deepEqual(errors, []);
    fs.writeFileSync(`${out}/result.json`, JSON.stringify(report, null, 2) + '\n');
    console.log('PASS: first drag, first wheel, cursor zoom, ground pan and cross-city detail residency', JSON.stringify(report));
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
