// London Tube on the regional data path, first selection without a network. The complete Scenario download stores the
// rail files, the station file and the code; nothing else is needed. Offline, a first selection opens the scheduled
// network, and stations are built from the stored station file. The pinned four-station source is never requested.
// Run against a built website whose London scene declares checksummed `underground.files`.
// Usage: node browser_tube_regional_offline.mjs http://127.0.0.1:8835/canopy/
import assert from 'node:assert/strict';
import fs from 'node:fs';
const {default: puppeteer} = await import(process.env.PUPPETEER_MODULE || 'puppeteer-core');
const base = new URL(process.argv[2] || 'http://127.0.0.1:8835/canopy/');
const out = process.env.QA_OUTPUT || 'cache/tube-regional-offline-review'; fs.mkdirSync(out, {recursive: true});
const browser = await puppeteer.launch({executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome', headless: true, protocolTimeout: 900000, args: ['--no-sandbox', '--use-angle=vulkan', '--enable-features=Vulkan', '--disable-vulkan-surface']});
const sleep = ms => new Promise(r => setTimeout(r, ms));
const receipt = {checks: [], errors: [], pinned_source_requests: 0};
const pass = name => { receipt.checks.push(name); console.log('ok', name); };
const RAIL = ['underground.json', 'underground_trains_am_peak.json'], CODE = ['viewer/3d/tube-regional.js', 'viewer/3d/tube-service.js', 'viewer/3d/tube-timetable.mjs', 'viewer/3d/tube-stations.js'];
try {
  const page = await browser.newPage(); await page.setViewport({width: 1280, height: 800}); page.setDefaultTimeout(180000);
  page.on('pageerror', e => receipt.errors.push(e.message));
  page.on('request', r => { if (/\/scene_data\.js$/.test(new URL(r.url()).pathname) && !r.url().includes('/context/underground/')) receipt.pinned_source_requests++; });
  const ready = () => page.waitForFunction(() => window.viewer && document.querySelector('#loading').classList.contains('hide'), {timeout: 900000});
  const click = shot => page.click(`[data-shot="${shot}"]`);
  const seek = value => page.$eval('#step', (e, v) => { e.value = v; e.dispatchEvent(new Event('input', {bubbles: true})); }, value);
  const until = (test, arg, timeout = 180000) => page.waitForFunction(test, {timeout}, arg);
  const state = () => page.evaluate(() => {
    const b = document.querySelector('[data-shot="londonTube"]'), step = document.querySelector('#step'), t = window.canopyTube, n = t?.service, menu = document.querySelector('#tube-view');
    return {online: navigator.onLine, button: b.textContent, busy: b.getAttribute('aria-busy'), active: document.querySelector('.shot.active')?.dataset.shot ?? null, loaded: Boolean(t), selection: t?.selection ?? null,
      menu: menu ? {shown: menu.getClientRects().length > 0, value: menu.value, options: menu.options.length} : null,
      strip: {name: step.getAttribute('aria-label'), min: +step.min, max: +step.max, text: step.getAttribute('aria-valuetext')},
      model: document.querySelector('#l-model').checked, trees: document.querySelector('#l-trees').checked, ground: document.querySelector('#l-ground').checked,
      tube: {time: document.querySelector('#tube-time').getClientRects().length > 0, rate: document.querySelector('#tube-rate').getClientRects().length > 0},
      station: t?.station?.name ?? null, alone: t?.alone ?? null,
      network: n ? {visible: n.group.visible, time: n.clock.time, playing: n.clock.playing, speed: n.clock.speed, trains: n.trains, cars: n.carInstances, omitted: n.omitted} : null};
  });
  const network = async on => {
    for (const target of browser.targets().filter(t => t.type() === 'service_worker')) {
      const session = await target.createCDPSession(); await session.send('Network.enable');
      await session.send('Network.emulateNetworkConditions', on ? {offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1} : {offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0});
    }
    await page.setOfflineMode(!on);
  };

  // ---- 1. Online: the landing page downloads and verifies the whole Scenario, then opens the overview. London Tube is not selected.
  await page.goto(base.href, {waitUntil: 'domcontentloaded'});
  await page.waitForFunction(() => location.pathname.endsWith('/viewer/3d/') || (document.getElementById('resume') && !document.getElementById('resume').hidden), {timeout: 1500000});
  assert(new URL(page.url()).pathname.endsWith('/viewer/3d/'), 'the complete download did not finish');
  await ready();
  const stored = await page.evaluate(async (baseURL, RAIL, CODE) => {
    const manifest = await (await fetch(new URL('download-manifest.json', baseURL), {cache: 'no-store'})).json();
    const cache = await caches.open('canopy-complete-' + manifest.version), root = new URL(baseURL).pathname;
    const keys = new Set((await cache.keys()).map(r => new URL(r.url).pathname.replace(root, ''))), listed = new Set(manifest.files.map(f => f.path));
    const S = window.viewer.SCENE, dir = `scenes/${S.id}/${S.underground?.dir}/`;
    return {version: manifest.version, files: manifest.files.length, cached: keys.size, declared: Boolean(S.underground?.files), stations: S.underground?.stations?.list?.length ?? 0,
      wanted: [...RAIL.map(f => dir + f), ...(S.underground?.stations ? [dir + S.underground.stations.file] : []), ...CODE].map(path => ({path, listed: listed.has(path), cached: keys.has(path)})),
      tube_loaded: Boolean(window.canopyTube)};
  }, base.href, RAIL, CODE);
  assert(stored.declared, 'the scene declares no checksummed underground files');
  assert.equal(stored.cached, stored.files, 'the complete download stored every listed file');
  for (const f of stored.wanted) assert(f.listed && f.cached, 'listed and stored: ' + f.path);
  assert(!stored.tube_loaded);
  pass('complete download stores the rail files, the station file and the code; London Tube not visited');

  // ---- 2. Offline (page and service worker), reload, first selection of London Tube.
  await network(false); await page.reload({waitUntil: 'domcontentloaded'}); await ready();
  assert.equal(await page.evaluate(async () => { try { return (await fetch('../../scenes/imperial_corridor_8km/scene.json', {cache: 'no-store'})).ok; } catch { return false; } }), false, 'the service worker is offline too');
  let s = await state(); assert(!s.online && s.button === 'London Tube' && !s.loaded);
  const shown = {model: s.model, trees: s.trees, ground: s.ground};
  // 2a. One read of the stored rail data fails: a clear retry, and the city stays usable.
  await page.evaluate(() => { const original = window.fetch.bind(window); let fail = true;
    window.fetch = async (...args) => { if (fail && /\/context\/underground\/underground/.test(String(args[0]?.url ?? args[0]))) { fail = false; throw new TypeError('Failed to fetch (injected)'); } return original(...args); }; });
  await click('londonTube'); await until(() => document.querySelector('[data-shot="londonTube"]').textContent === 'Tube unavailable · retry'); await sleep(400);
  s = await state(); assert(!s.loaded && s.busy === null && s.active === 'overview' && s.model === shown.model && s.trees === shown.trees, JSON.stringify(s));
  await click('traffic'); await sleep(1200); assert.equal((await state()).active, 'traffic'); await click('overview'); await sleep(1200); assert.equal((await state()).active, 'overview');
  pass('offline with unreadable rail data: a clear retry on the button; the city stays usable');
  // 2b. The retry, still offline: the network opens from the stored files.
  await click('londonTube');
  await until(() => window.canopyTube?.service?.group.visible || document.querySelector('[data-shot="londonTube"]').textContent === 'Tube unavailable · retry');
  assert(await page.evaluate(() => Boolean(window.canopyTube?.service?.group.visible)), 'offline, London Tube ended at "Tube unavailable · retry" although the rail files are stored');
  s = await state();
  assert(s.busy === null && s.active === 'londonTube' && s.button === 'London Tube' && s.selection === 'network' && s.menu.shown && s.menu.options === stored.stations + 1, JSON.stringify(s));
  assert.equal(s.strip.name, 'Tube timetable time'); assert.deepEqual([s.strip.min, s.strip.max], [28800, 32400]);
  assert(!s.model && !s.trees && s.network.playing && s.network.speed === 30 && s.network.trains > 0); assert(s.tube.time && s.tube.rate, 'service time and rate are visible offline too');
  await page.click('#play'); await seek(30144); await until(() => window.canopyTube.service.clock.time === 30144 && window.canopyTube.service.trains === 98);
  s = await state(); assert(!s.network.playing && s.network.cars === 588 && s.network.omitted === 0); assert.match(s.strip.text, /08:22:24/);
  pass('offline first selection opens the network from the stored files; 98 trains at 08:22:24');

  // ---- 3. Offline, stations from the stored station file.
  if (stored.stations) {
    const choose = async id => { await page.select('#tube-view', id); await until(id => window.canopyTube.selection === id && window.canopyTube.stationGroup?.visible && !document.querySelector('#tube-view').hasAttribute('aria-busy'), id); };
    await choose('940GZZLULAD'); s = await state(); assert(s.station === 'Ladbroke Grove' && s.alone && !s.network.visible && s.network.time === 30144 && !s.ground && !s.model, JSON.stringify(s));
    await seek(1e9); await until(() => !window.canopyTube.journey.playing);
    await choose('940GZZLUGPK'); s = await state(); assert(s.station === 'Green Park' && !s.alone && s.model === shown.model && s.ground === shown.ground && s.trees === shown.trees, JSON.stringify(s));
    await seek(1e9); await until(() => !window.canopyTube.journey.playing);
    await page.select('#tube-view', 'network'); await until(() => window.canopyTube.service.group.visible); assert.equal((await state()).network.time, 30144);
    pass('offline: two stations in succession from the stored station file; back to the network at the kept time');
  }

  // ---- 4. Leave and return, still offline: the city is restored, then the network opens again at the kept time.
  await click('overview'); await sleep(1200); s = await state();
  assert(!s.network.visible && s.model === shown.model && s.trees === shown.trees && s.ground === shown.ground && s.button === 'London Tube' && s.active === 'overview' && !s.menu.shown);
  await click('londonTube'); await until(() => window.canopyTube.service.group.visible);
  s = await state(); assert(s.network.time === 30144 && !s.network.playing && !s.model && s.selection === 'network');
  pass('overview and back while offline: layers restored, network reopened at the kept service time');

  // ---- 5. Online again: nothing changes; the pinned source is still not requested.
  await network(true); await until(() => navigator.onLine);
  await click('overview'); await sleep(800); await click('londonTube'); await until(() => window.canopyTube.service.group.visible);
  s = await state(); assert(s.network.time === 30144 && s.button === 'London Tube' && s.strip.name === 'Tube timetable time');
  assert.equal(receipt.pinned_source_requests, 0, 'the pinned four-station source was never requested');
  pass('online again: the same view; the pinned source was never requested');

  assert.deepEqual(receipt.errors, []);
  fs.writeFileSync(`${out}/verification.json`, JSON.stringify({passed: true, base: base.href, browser: await browser.version(), stored, ...receipt,
    scope: 'Complete download, offline reload, first selection of London Tube offline, stations offline, return online. State checks; not a rendering or frame-rate test.'}, null, 2));
  console.log('PASS Tube regional offline first entry');
} finally { await browser.close(); }
