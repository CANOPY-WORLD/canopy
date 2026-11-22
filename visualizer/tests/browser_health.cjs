// Exercise recorded health results through the shared scientific Viewer.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const puppeteer = require(process.env.PUPPETEER_MODULE || 'puppeteer-core');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
  const base = process.argv[2] || 'http://127.0.0.1:8772';
  const browser = await puppeteer.launch({executablePath: process.env.CHROME_PATH, headless: true,
    args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']});
  try {
    const page = await browser.newPage(), errors = [], viewports = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('requestfailed', r => errors.push(r.url()));
    page.on('response', r => { if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`); });
    const time = () => page.$eval('#time', e => Number(e.value));
    const seek = value => page.$eval('#time', (e, t) => { e.value = t; e.dispatchEvent(new Event('input', {bubbles: true})); }, value);
    const snapshot = () => page.evaluate(() => {
      const w = id => window.urbanViewer.widgets.find(w => w.layer.id === id);
      return {breathing: w('breathing').current[0], position: w('trajectory').current[0],
        matrixPosition: Array.from(w('trajectory').instances.instanceMatrix.array.slice(12, 15)),
        allAvailable: window.urbanViewer.widgets.every(w => w.available),
        selected: [...document.querySelectorAll('.layer input[type=checkbox]')].map(e => e.checked)};
    });
    for (const viewport of [{width: 1440, height: 1000}, {width: 390, height: 844}]) {
      await page.setViewport(viewport);
      await page.goto(base + '/src/visualization/viewer/?scenario=health_example', {waitUntil: 'networkidle0'});
      await page.waitForFunction(() => window.urbanViewer && document.querySelector('#status').textContent.includes('8 / 8 layers ready'));
      await page.waitForFunction(() => document.documentElement.scrollWidth <= innerWidth);
      assert.equal((await page.$$('.layer input[type=checkbox]')).length, 8);
      assert.equal((await page.$$('canvas.series')).length, 7);
      const recorded = await page.evaluate(() => {
        const w = id => window.urbanViewer.widgets.find(w => w.layer.id === id);
        return {breathing: w('breathing').data.values.map(v => v[0]), positions: w('trajectory').data.positions.map(p => p[0])};
      });
      await seek(300);
      const first = await snapshot();
      assert.equal(first.breathing, recorded.breathing[1]);
      assert.deepEqual(first.position, recorded.positions[1]);
      await seek(1950); // Halfway between samples 6 and 7; breathing holds sample 6.
      const middle = await snapshot();
      const interpolated = recorded.positions[6].map((v, i) => (v + recorded.positions[7][i]) / 2);
      assert.equal(middle.breathing, recorded.breathing[6]);
      assert.notEqual(middle.breathing, first.breathing);
      assert.deepEqual(middle.position, interpolated);
      assert.deepEqual(middle.matrixPosition, [interpolated[0], interpolated[2], -interpolated[1]].map(v => v || 0));
      await page.click('canvas.series[title=breathing]');
      const picked = JSON.parse(await page.$eval('#selection', e => e.textContent));
      assert.equal(picked.values[0], recorded.breathing[6]);
      assert.equal(picked.unit, 'breaths/min');

      await page.click('#play');
      await page.waitForFunction(start => Number(document.querySelector('#time').value) > start + .1, {}, 1950);
      await page.click('#play');
      const paused = await time(), pausedResult = await snapshot();
      await delay(500);
      assert.equal(await time(), paused, 'Pause must hold the clock');
      assert.deepEqual(await snapshot(), pausedResult, 'Pause must hold displayed results');

      for (const id of ['breathing', 'trajectory']) {
        const toggle = async () => {
          const checkbox = await page.evaluateHandle(id => [...document.querySelectorAll('.layer label')]
            .find(e => e.title.endsWith(` / ${id}`)).querySelector('input'), id);
          await checkbox.asElement().click();
          await checkbox.dispose();
        };
        const visible = () => page.evaluate(id => {
          const w = window.urbanViewer.widgets.find(w => w.layer.id === id);
          return {visible: w.visible, rendered: w.group.visible, chartHidden: w.chart?.hidden ?? null};
        }, id);
        await toggle();
        assert.deepEqual(await visible(), {visible: false, rendered: false, chartHidden: id === 'breathing' ? true : null});
        await toggle();
        assert.deepEqual(await visible(), {visible: true, rendered: true, chartHidden: id === 'breathing' ? false : null});
      }
      await seek(3599.8);
      await page.click('#play');
      await page.waitForFunction(() => Number(document.querySelector('#time').value) === 3600 && document.querySelector('#play').textContent === 'Play');
      const final = await snapshot();
      assert.equal(final.breathing, recorded.breathing.at(-1));
      assert.deepEqual(final.position, recorded.positions.at(-1));
      assert.equal(final.allAvailable, true);
      assert.deepEqual(final.selected, Array(8).fill(true));
      await delay(250);
      assert.equal(await time(), 3600, 'Final sample must hold');
      await page.click('#play');
      await page.waitForFunction(() => Number(document.querySelector('#time').value) > 0 && Number(document.querySelector('#time').value) < 300);
      await page.click('#play');
      assert.equal((await snapshot()).breathing, recorded.breathing[0], 'Restart must use first sample');
      assert((await snapshot()).position[0] < recorded.positions[1][0]);
      fs.mkdirSync('cache/qa', {recursive: true});
      await page.screenshot({path: `cache/qa/health-local-viewer-${viewport.width}.png`});
      viewports.push(viewport.width);
    }
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({passed: true, layers: 8, charts: 7, viewports,
      checks: ['seek-result', 'interpolated-trajectory', 'render-matrix', 'pick', 'advance', 'pause', 'visibility', 'final-sample', 'restart'], errors}));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
