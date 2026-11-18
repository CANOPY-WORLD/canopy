// Exercise the complete Pages artifact from a project subpath, with no Python API.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const puppeteer = require(process.env.PUPPETEER_MODULE || 'puppeteer-core');
(async () => {
  const base = new URL(process.argv[2] || 'http://127.0.0.1:8769/canopy/');
  const browser = await puppeteer.launch({executablePath: process.env.CHROME_PATH || '/opt/google/chrome/chrome',
    headless: true, args: ['--no-sandbox', '--enable-unsafe-swiftshader']});
  const errors = [], external = new Set();
  const watch = page => {
    page.on('pageerror', e => {errors.push(e.message); console.error('Page error:', e.message);});
    page.on('request', r => {const u = new URL(r.url()); if (/^https?:/.test(u.protocol) && u.origin !== base.origin) external.add(u.origin);});
    page.on('response', r => {if (r.status() >= 400 && !r.url().endsWith('/favicon.ico')) errors.push(`${r.status()} ${r.url()}`);});
  };
  try {
    const page = await browser.newPage(); watch(page);
    await page.setViewport({width: 1440, height: 1000});
    await page.goto(new URL('viewer/3d/?scene=imperial_corridor_8km&pose=campus&fields=0&shot=overview&hold=1&lite=0', base).href, {waitUntil:'domcontentloaded'});
    await page.waitForFunction(() => window.viewer?.model.children.length > 0 && document.getElementById('loading').classList.contains('hide'), {timeout: 120000});
    const direct = await page.evaluate(() => ({scene: viewer.SCENE.id, children: viewer.model.children.length,
      controller: !!navigator.serviceWorker.controller, error: document.getElementById('viewer-error-message').textContent}));
    assert.equal(direct.scene, 'imperial_corridor_8km'); assert(direct.controller); assert(direct.children > 0); assert.equal(direct.error, '');
    console.log('Direct entry and full GLB geometry loaded');
    const frames = await page.evaluate(async () => {
      const {Npy} = await import('../npy.js');
      const results = [];
      for (const [name, record] of Object.entries(viewer.SCENE.protocol_display.npy_transport)) {
        const file = new Npy(name);
        const shape = record.meta.shape;
        // Read the first and final stored sample through the actual compressed reader.
        for (const i of [...new Set([0, shape[0] - 1])]) {
          const data = await file.read(i);
          if (data.length !== record.meta.block) throw Error('Wrong decoded sample size: ' + name);
        }
        results.push({name, shape});
      }
      return results;
    });
    console.log(`Decoded first/final samples for ${frames.length} field resources`);
    fs.mkdirSync('cache/qa/pages', {recursive:true});
    await page.waitForFunction(() => window.viewer?.renderer.info.render.calls > 0);
    await new Promise(resolve => setTimeout(resolve, 1500));
    await page.screenshot({path:'cache/qa/pages/london-desktop.png'});
    await page.goto(base.href, {waitUntil:'domcontentloaded'});
    await page.waitForFunction(() => location.pathname.endsWith('/viewer/3d/') ||
      (document.getElementById('resume') && !document.getElementById('resume').hidden), {timeout: 240000});
    assert(new URL(page.url()).pathname.endsWith('/viewer/3d/'), await page.$eval('#pct', e => e.textContent).catch(() => 'Download failed'));
    await page.waitForFunction(() => window.viewer?.model.children.length > 0 && document.getElementById('loading').classList.contains('hide'), {timeout: 120000});
    const cache = await page.evaluate(async baseURL => {
      const manifest = await (await fetch(new URL('download-manifest.json',baseURL), {cache:'no-store'})).json();
      const stored = await caches.open('canopy-complete-'+manifest.version);
      return {expected:manifest.files.length, actual:(await stored.keys()).length, bytes:manifest.bytes};
    }, base.href);
    assert.equal(cache.actual, cache.expected);
    console.log('All publication files verified and cached', JSON.stringify(cache));
    await page.setOfflineMode(true);
    await page.reload({waitUntil:'domcontentloaded'});
    await page.waitForFunction(() => window.viewer?.model.children.length > 0 && document.getElementById('loading').classList.contains('hide'), {timeout: 120000});
    assert.equal(await page.evaluate(() => viewer.SCENE.id), 'imperial_corridor_8km');
    await page.setOfflineMode(false);
    assert.deepEqual([...external], []); assert.deepEqual(errors, []);
    fs.writeFileSync('cache/qa/pages/result.json', JSON.stringify({passed:true, base:base.href, direct, frames, cache, offline:true, errors, external:[...external]},null,2));
    console.log(JSON.stringify({passed:true, resources:frames.length, cache, offline:true, errors, external:[...external]},null,2));
  } finally {await browser.close();}
})().catch(error => {console.error(error);process.exit(1);});
