// Verify the generated review inventory, accessible controls and responsive layout.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const puppeteer = require(process.env.PUPPETEER_MODULE || 'puppeteer-core');

(async () => {
  const base = process.argv[2] || 'http://127.0.0.1:8769/guide/';
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH || '/opt/google/chrome/chrome',
    headless: true, args: ['--no-sandbox'],
  });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('response', r => { if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`); });
    await page.setViewport({width: 1440, height: 1000});
    await page.goto(base, {waitUntil: 'networkidle0'});
    await page.waitForSelector('#inventory-status.ready');
    const data = await page.evaluate(async () => (await fetch('inventory.json')).json());
    const methods = data.models.reduce((n, g) => n + g.methods.length, 0);
    assert.equal((await page.$$('details.method')).length, methods);
    assert.equal(data.scenario.id, 'imperial_corridor_8km');
    fs.mkdirSync('cache/qa/london-guide', {recursive: true});
    await page.screenshot({path: 'cache/qa/london-guide/desktop.png', fullPage: true});
    await page.click('details.method summary');
    assert.equal(await page.$eval('details.method', e => e.open), true);
    await page.click('.method-actions [data-copy]');
    await page.waitForFunction(() => document.querySelector('#copy-status').textContent.length > 0);
    await page.type('#method-search', 'finite_difference_numpy');
    assert.equal((await page.$$('details.method')).length, 1);
    await page.$eval('#method-search', e => { e.value = 'no-such-method'; e.dispatchEvent(new Event('input')); });
    assert.equal((await page.$$('details.method')).length, 0);
    assert.match(await page.$eval('#method-result', e => e.textContent), /No Methods match/);
    await page.$eval('#method-search', e => { e.value = ''; e.dispatchEvent(new Event('input')); });
    await page.focus('#tab-model');
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.$eval('#tab-asset', e => e.getAttribute('aria-selected')), 'true');
    assert.equal((await page.$$('#asset-rows tr')).length, data.assets.length);
    for (const kind of ['geometry', 'physics', 'all']) {
      await page.click(`[data-filter=${kind}]`);
      assert.equal((await page.$$('#asset-rows tr')).length,
        data.assets.filter(a => kind === 'all' || a.kind === kind).length);
    }
    await page.screenshot({path: 'cache/qa/london-guide/assets-desktop.png'});
    await page.focus('#tab-asset');
    await page.keyboard.press('End');
    assert.equal(await page.$eval('#tab-visualizer', e => e.getAttribute('aria-selected')), 'true');
    assert.equal((await page.$$('.viewer-row')).length, 5);
    for (const value of ['model', 'asset', 'visualizer', 'scenario']) {
      await page.select('#change-type', value);
      assert.equal((await page.$$('.contribution-steps li')).length, 4);
      assert.match(await page.$eval('.contribution-links a', e => e.href), new RegExp(`/${value}/CONTRIBUTING.md$`));
    }
    await page.setViewport({width: 390, height: 844});
    for (const name of ['model', 'asset', 'visualizer']) {
      await page.click(`#tab-${name}`);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Overflow in ${name}`);
    }
    await page.click('#tab-model');
    await page.evaluate(() => window.scrollTo({top: 0, behavior: 'instant'}));
    await page.screenshot({path: 'cache/qa/london-guide/mobile.png', fullPage: true});
    assert(await page.evaluate(() => [...document.querySelectorAll('a[href^="#"]')].every(a =>
      a.hash === '' || a.hash === '#' || document.getElementById(a.hash.slice(1)))));
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({passed:true, methods, assets:data.assets.length, viewports:[1440,390], errors}, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
