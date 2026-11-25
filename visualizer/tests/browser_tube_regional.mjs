// London Tube on the regional data path: the scheduled network on its service clock and every declared station, from
// the Scenario's own data. Usage (same environment as browser_tube_network.mjs):
//   node browser_tube_regional.mjs http://127.0.0.1:8835/canopy/viewer/3d/?scene=imperial_corridor_8km
// The scene must declare `underground.files` with SHA-256 digests; with `underground.stations` the station menu is tested
// too. On a scene without them the test checks that the pinned four-station view is what opens, and stops ("absent").
// QA_SCREENSHOTS=1 writes pictures.
import assert from 'node:assert/strict';
import fs from 'node:fs';
const {default: puppeteer} = await import(process.env.PUPPETEER_MODULE || 'puppeteer-core');
const out = process.env.QA_OUTPUT || 'cache/tube-regional-review'; fs.mkdirSync(out, {recursive: true});
const browser = await puppeteer.launch({executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--use-angle=vulkan', '--enable-features=Vulkan', '--disable-vulkan-surface']});
const sleep = ms => new Promise(r => setTimeout(r, ms));
// Seven service seconds of the archived AM timetable under the original rule, and the exact peak (98 trains at 08:22:24).
const WITNESSES = [[28800, 90], [28910, 88], [29155, 88], [30144, 98], [30600, 92], [32399, 94], [32400, 95]];
const TRIP = 'VJ3d1a6e9226c7ba5b11495b68e13f2a06cddf2b31', CARS = {28800: [1184.692978, -1347.073755, -14.493861, -0.334171], 28910: [1806.666973, -1376.311209, -21.391511, 0.011515], 29155: [3181.897933, -423.238262, 0.97487, 0.231179]};
const receipt = {checks: [], errors: []};
const pass = name => { receipt.checks.push(name); console.log('ok', name); };
try {
  const page = await browser.newPage(); await page.setViewport({width: 1280, height: 800}); page.setDefaultTimeout(120000);
  page.on('pageerror', e => receipt.errors.push(e.message)); let pinnedSourceRequests = 0;
  page.on('request', r => { if (/\/scene_data\.js$/.test(new URL(r.url()).pathname) && !r.url().includes('/context/underground/')) pinnedSourceRequests++; });
  await page.goto(process.argv[2] || 'http://127.0.0.1:8835/canopy/viewer/3d/?scene=imperial_corridor_8km');
  await page.waitForFunction(() => window.viewer && document.querySelector('#loading').classList.contains('hide'), {timeout: 600000});
  // Requests for the Scenario's rail and station files can be failed once, corrupted once or delayed inside the page
  // (with a service worker in control they do not pass through request interception).
  await page.evaluate(() => {
    const original = window.fetch.bind(window); window.__rail = {mode: 'pass', seen: [], delayMs: 0, stationFail: false, stationDelayMs: 0, stations: 0};
    window.fetch = async (...args) => {
      const url = String(args[0]?.url ?? args[0]), R = window.__rail, signal = args[1]?.signal;
      if (/\/context\/underground\/underground_stations/.test(url)) { R.stations++; if (R.stationDelayMs) await new Promise(resolve => setTimeout(resolve, R.stationDelayMs)); if (R.stationFail) { R.stationFail = false; throw new TypeError('Failed to fetch (injected)'); } }
      else if (/\/context\/underground\/underground(_trains_am_peak)?\.json/.test(url)) {
        R.seen.push(url.split('/').pop());
        if (R.mode === 'fail-once') { R.mode = 'pass'; throw new TypeError('Failed to fetch (injected)'); }
        if (R.mode === 'corrupt-once' && url.endsWith('underground.json')) { R.mode = 'pass'; return new Response('{"lines":[],"tracks":[]}', {status: 200}); }
        if (R.delayMs) await new Promise((resolve, reject) => { const t = setTimeout(resolve, R.delayMs); signal?.addEventListener('abort', () => { clearTimeout(t); reject(signal.reason); }); });
      }
      return original(...args);
    };
  });
  const rail = v => page.evaluate(v => Object.assign(window.__rail, v), v);
  const click = shot => page.click(`[data-shot="${shot}"]`);
  const seek = value => page.$eval('#step', (e, v) => { e.value = v; e.dispatchEvent(new Event('input', {bubbles: true})); }, value);
  const until = (test, arg, timeout = 180000) => page.waitForFunction(test, {timeout}, arg);
  const state = () => page.evaluate(() => {
    const b = document.querySelector('[data-shot="londonTube"]'), step = document.querySelector('#step'), t = window.canopyTube, n = t?.service, menu = document.querySelector('#tube-view'), time = document.querySelector('#tube-time'), rate = document.querySelector('#tube-rate'), v = window.viewer;
    const shown = e => Boolean(e) && e.getClientRects().length > 0;
    return {button: b.textContent, busy: b.getAttribute('aria-busy'), active: document.querySelector('.shot.active')?.dataset.shot ?? null, regional: t?.regional ?? null, selection: t?.selection ?? null,
      menu: menu ? {shown: shown(menu), value: menu.value, options: menu.options.length, busy: menu.getAttribute('aria-busy'), invalid: menu.getAttribute('aria-invalid'), title: menu.title, name: menu.getAttribute('aria-label')} : null,
      strip: {name: step.getAttribute('aria-label'), min: +step.min, max: +step.max, text: step.getAttribute('aria-valuetext')}, play: document.querySelector('#play').getAttribute('aria-label'),
      rates: [...document.querySelector('#rate').options].map(o => o.textContent), rate: document.querySelector('#rate').value,
      tube: {time: {shown: shown(time), text: time.textContent, note: time.title, role: time.getAttribute('role'), name: time.getAttribute('aria-label')}, rate: {shown: shown(rate), value: rate.value, options: [...rate.options].map(o => o.textContent), name: rate.getAttribute('aria-label'), tabIndex: rate.tabIndex}},
      ground: document.querySelector('#l-ground').checked, model: document.querySelector('#l-model').checked, trees: document.querySelector('#l-trees').checked,
      network: n ? {visible: n.group.visible, time: n.clock.time, playing: n.clock.playing, speed: n.clock.speed, trains: n.trains, cars: n.carInstances, omitted: n.omitted, capacity: n.capacity.carInstances, label: n.label} : null,
      cutaway: t?.cutawayActive ?? false, station: t?.station ?? null, alone: t?.alone ?? null, stationVisible: Boolean(t?.stationGroup?.visible), journey: t ? {playing: t.journey.playing, time: t.journey.time, duration: t.journey.duration} : null,
      inScene: v.scene.children.filter(o => /\(representative station\)$/.test(o.name)).length, stationMeshes: (() => { let k = 0; t?.stationGroup?.traverse(o => { if (o.isMesh) k++; }); return k; })(),
      iframes: document.querySelectorAll('iframe').length, canvases: document.querySelectorAll('canvas').length};
  });
  const before = await page.evaluate(() => ({ground: document.querySelector('#l-ground').checked, model: document.querySelector('#l-model').checked, trees: document.querySelector('#l-trees').checked, declared: Boolean(window.viewer.SCENE.underground?.files), stations: window.viewer.SCENE.underground?.stations?.list?.length ?? 0, hasIhub: Boolean(document.querySelector('[data-shot="interior"]'))}));
  const city = s => s.ground === before.ground && s.model === before.model && s.trees === before.trees;
  let s;

  if (!before.declared) {
    // ---- No regional data: the pinned four-station view opens, exactly as upstream.
    await click('londonTube'); await until(() => window.canopyTube?.group.visible); s = await state();
    assert(s.regional === null && s.network === null && s.selection === 'network' && s.menu.options === 5 && !s.tube.time.shown && !s.tube.rate.shown && s.strip.name === 'Interior camera journey progress' && city(s), JSON.stringify(s));
    assert.equal(await page.evaluate(() => window.__rail.seen.length + window.__rail.stations), 0); assert.equal(pinnedSourceRequests, 1);
    pass('regional data absent: the pinned four-station view opens; no rail or station file is fetched');
    assert.deepEqual(receipt.errors, []);
    fs.writeFileSync(`${out}/verification.json`, JSON.stringify({passed: true, regional_data: 'absent (the scene declares no checksummed underground files)', ...receipt}, null, 2));
    console.log('PASS Tube regional (absent)');
  } else {
    // ---- 1. A rail file fails: the city stays, the button offers a retry. A corrupted file fails its checksum. Leaving a slow load cancels it.
    await rail({mode: 'fail-once'}); await click('londonTube'); await until(() => document.querySelector('[data-shot="londonTube"]').textContent === 'Tube unavailable · retry'); await sleep(300);
    s = await state(); assert(s.regional === null && s.busy === null && s.active !== 'londonTube' && city(s), JSON.stringify(s));
    await rail({mode: 'corrupt-once'}); await click('londonTube'); await until(() => document.querySelector('[data-shot="londonTube"]').textContent === 'Tube unavailable · retry'); await sleep(300);
    assert.equal((await state()).regional, null, 'a file with the wrong digest is not decoded');
    await rail({delayMs: 2500}); await click('londonTube'); await sleep(300); assert.equal((await state()).busy, 'true'); await click('overview'); await sleep(3500);
    s = await state(); assert(s.regional === null && s.active === 'overview' && s.button === 'London Tube' && s.busy === null && city(s), JSON.stringify(s)); await rail({delayMs: 0});
    pass('failed, corrupted and abandoned rail loads leave the city as it is; the button offers the retry');

    // ---- 2. London Tube from the Scenario's data: the scheduled network on the service clock. Nothing is fetched from the pinned source.
    await click('londonTube'); await until(() => window.canopyTube?.service?.group.visible);
    s = await state();
    assert(s.regional && s.selection === 'network' && s.active === 'londonTube' && s.button === 'London Tube' && s.iframes === 0, JSON.stringify(s)); assert.equal(pinnedSourceRequests, 0, 'the pinned source is not requested');
    assert.equal(await page.evaluate(() => window.canopyTube.service.group.parent === window.viewer.scene), true);
    assert(s.menu.shown && s.menu.value === 'network' && s.menu.options === before.stations + 1 && s.menu.name === 'Tube station or network overview');
    assert.equal(await page.$eval('#tube-view', e => e.options[0].textContent), 'Network overview · scheduled trains', 'the way back to the moving network is named in the menu');
    assert.equal(s.strip.name, 'Tube timetable time'); assert.deepEqual([s.strip.min, s.strip.max], [28800, 32400]);
    assert.deepEqual(s.rates, ['1×', '10×', '30×', '60×']); assert.equal(s.rate, '30'); assert.equal(s.network.playing, true); assert.equal(s.play, 'Pause');
    assert(s.ground === before.ground && !s.model && !s.trees, 'buildings and trees are hidden while the network is shown');
    assert(/Tube timetable 08:\d\d:\d\d · scheduled 2026-06-25, not live/.test(s.network.label)); assert.equal(s.strip.text, s.network.label);
    assert.equal(s.network.capacity, 6 * (15 + 19 + 9 + 20 + 5 + 10 + 8 + 16 + 6));
    pass('London Tube opens the scheduled network from the Scenario data; the strip is the service clock');

    // ---- 3. Service time and rate are visible in the strip, in this view only.
    assert(s.tube.time.shown && s.tube.rate.shown); assert.match(s.tube.time.text, /^08:\d\d:\d\d$/);
    assert.equal(s.tube.time.role, 'timer'); assert.equal(s.tube.time.name, 'Tube timetable time'); assert.equal(s.tube.time.note, 'Scheduled timetable of 2026-06-25, not live');
    assert.deepEqual(s.tube.rate.options, ['1×', '10×', '30×', '60×']); assert.equal(s.tube.rate.value, '30'); assert.equal(s.tube.rate.name, 'Tube timetable speed'); assert.equal(s.tube.rate.tabIndex, 0);
    assert(await page.evaluate(() => [...document.querySelectorAll('.timebar > *')].map(e => e.id).join() === 'play,step,tube-time,tube-rate'), 'inside the existing strip, nothing else added');
    await page.select('#tube-rate', '10'); s = await state(); assert.equal(s.network.speed, 10); assert.equal(s.rate, '10');
    await page.focus('#step'); await page.keyboard.press('Tab'); assert.equal(await page.evaluate(() => document.activeElement.id), 'tube-rate');
    if (process.platform !== 'darwin') { await page.keyboard.press('ArrowDown'); await until(() => window.canopyTube.service.clock.speed === 30); } else await page.select('#tube-rate', '30');   // arrow keys open the menu on macOS
    await page.select('#rate', '60'); await until(() => document.querySelector('#tube-rate').value === '60'); await page.select('#rate', '30'); await until(() => document.querySelector('#tube-rate').value === '30');
    pass('service time and rate selector are visible in the strip; the rate works by pointer and keyboard');

    // ---- 4. Pause, seek, the seven witnesses, the exact peak; the Play button is not rewritten while the service runs.
    await page.click('#play'); const held = (await state()).network.time; await sleep(400); s = await state();
    assert.equal(s.network.time, held); assert.equal(s.network.playing, false); assert.equal(s.play, 'Play');
    for (const [t, count] of WITNESSES) {
      await seek(t); s = await state(); assert.equal(s.network.time, t); assert.equal(s.network.trains, count, `trains at ${t}`); assert.equal(s.network.cars, count * 6); assert.equal(s.network.omitted, 0);
      const sample = await page.evaluate((t, id) => window.canopyTube.service.sample(t, id), t, TRIP); assert.equal(sample.count, count);
      if (CARS[t]) CARS[t].forEach((v, k) => assert(Math.abs(sample.firstCar[k] - v) < 1e-3, `example car at ${t}`)); else if (t > 29155) assert.equal(sample.firstCar, null);
    }
    const scan = await page.evaluate(() => { const n = window.canopyTube.service, was = n.clock.time; let most = 0, omitted = 0; for (let t = 28800; t <= 32400; t += 15) { n.seek(t); most = Math.max(most, n.carInstances); omitted += n.omitted; } n.seek(was); return {most, omitted, capacity: n.capacity.carInstances}; });
    assert.equal(scan.omitted, 0); assert(scan.most <= 588 && scan.most <= scan.capacity);
    await seek(30144); await until(() => document.querySelector('#tube-time').textContent === '08:22:24'); assert.match((await state()).strip.text, /08:22:24/);
    receipt.peak = await page.evaluate(() => window.canopyTube.service.peak.network); assert.deepEqual(receipt.peak, {trains: 98, first_t_s: 30144});
    if (process.env.QA_SCREENSHOTS === '1') { await page.evaluate(() => { window.__pauseDraw = false; }); await sleep(1500); await page.screenshot({path: `${out}/network.png`}); await page.evaluate(() => { if ('__skippedDraws' in window) window.__pauseDraw = true; }); }
    await seek(29000); await page.click('#play'); await until(() => window.canopyTube.service.clock.time > 29000 && window.canopyTube.service.clock.playing);
    const writes = await page.evaluate(() => new Promise(resolve => { let k = 0; const o = new MutationObserver(list => { k += list.length; });
      o.observe(document.querySelector('#play'), {childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ['aria-label']}); setTimeout(() => { o.disconnect(); resolve(k); }, 1200); }));
    assert.equal(writes, 0, 'no write to the Play button while the service runs');
    pass('pause, seek, seven witnesses and the 98-train peak; the Play button is not rewritten while the service runs');

    if (before.stations) {
      // ---- 5. The 53 choices resolve to source deep interiors or contextual network locations.
      const listed = await page.evaluate(() => [...document.querySelector('#tube-view').options].slice(1).map(o => o.value));
      const arrived = id => until(id => window.canopyTube.selection === id && !document.querySelector('#tube-view').hasAttribute('aria-busy'), id);
      const choose = async id => { await page.select('#tube-view', id); await arrived(id); };
      assert.deepEqual(await page.evaluate(() => [window.viewer.tubeStations, window.__rail.stations]), [null, 0]);
      await page.click('#play'); const kept = (await state()).network.time;
      await rail({stationFail: true}); await page.select('#tube-view', '940GZZLULAD'); await until(() => document.querySelector('#tube-view').getAttribute('aria-invalid') === 'true');
      s = await state(); assert(s.selection === 'network' && s.menu.value === 'network' && s.network.visible && s.network.time === kept);
      await rail({stationDelayMs: 1200}); await page.select('#tube-view', '940GZZLURVP'); await page.setViewport({width:390,height:844});
      await click('overview'); await click('londonTube'); await arrived('940GZZLURVP');
      await rail({stationDelayMs: 0}); s=await state(); assert(s.network.visible && s.ground && s.inScene===0 && s.stationMeshes===0 && !s.alone && s.strip.name==='Tube timetable time');
      const hold = async id => { await page.evaluate(id => { const catalog=window.viewer.tubeStations,build=catalog.build; window.__release=null;
        catalog.build=(...args)=>args[1]!==id?build(...args):new Promise((resolve,reject)=>{window.__release=()=>{catalog.build=build;build(...args).then(resolve,reject);};}); },id);
        await page.select('#tube-view',id);await until(()=>window.__release&&document.querySelector('#tube-view').hasAttribute('aria-busy')); };
      await hold('940GZZLUSKS'); await click('overview'); await click('londonTube');
      assert.equal((await state()).selection,'940GZZLURVP'); await page.evaluate(()=>window.__release()); await arrived('940GZZLUSKS');
      s=await state(); assert(s.stationVisible && city(s) && !s.alone && !s.network.visible,'mixed South Kensington enters its deep platform with city retained');
      // A newer selection wins over an older station build.
      await hold('940GZZLUBST'); await choose('940GZZLULAD'); await page.evaluate(()=>window.__release()); await sleep(250);
      assert.equal((await state()).selection,'940GZZLULAD'); assert.equal((await state()).inScene,0);
      await page.setViewport({width:1280,height:800});
      const built=[];
      for(const id of listed){ await choose(id); const q=await state();
        const interior=q.station.viewKind==='interior';
        assert(!q.alone && q.network.time===kept, id);assert.equal(q.cutaway,interior,id+' cutaway state');
        assert(interior ? q.stationVisible&&q.inScene===1&&q.stationMeshes>0&&city(q)&&!q.network.visible : q.network.visible&&q.inScene===0&&q.stationMeshes===0&&q.ground&&!q.model, id);
        assert.equal(q.strip.name,interior?'Interior camera journey progress':'Tube timetable time');
        assert.match(await page.$eval('#tube-view',e=>e.selectedOptions[0].textContent),interior?/platform interior/:/network location/);
        built.push({id,name:q.station.name,kind:q.station.viewKind,meshes:q.stationMeshes});
      }
      assert.equal(built.filter(x=>x.kind==='interior').length,23);assert.equal(built.filter(x=>x.kind==='network').length,30);
      receipt.station_views=built;
      const shot=async(id,name)=>{await choose(id);const q=await state();if(q.station.viewKind==='interior'){await seek(1e9);await until(()=>!window.canopyTube.journey.playing);}
        await page.evaluate(()=>{window.__pauseDraw=false});await sleep(2000);if(process.env.QA_SCREENSHOTS==='1')await page.screenshot({path:`${out}/${name}.png`});await page.evaluate(()=>{if('__skippedDraws'in window)window.__pauseDraw=true});};
      await shot('940GZZLUBST','mixed-interior'); await shot('940GZZLULAD','surface-context');
      const wide=await page.evaluate(()=>viewer.camera.position.distanceTo(canopyTube.pose.target));
      await page.setViewport({width:390,height:844});await sleep(2100);
      const narrow=await page.evaluate(()=>viewer.camera.position.distanceTo(canopyTube.pose.target));assert(narrow>wide,'surface location fits narrow view');
      await shot('940GZZLULAD','surface-context-390');await shot('940GZZLUSKS','interior-390');
      await page.setViewport({width:1280,height:800});
      await page.select('#tube-view','network');await until(()=>window.canopyTube.service.group.visible);assert.equal((await state()).network.time,kept);
      await page.click('#play');await until(()=>window.canopyTube.service.clock.playing);
      await choose('940GZZLUWCY');assert((await state()).network.playing,'surface location keeps the service clock running');
      assert.equal((await state()).rate,'30','surface selection retains the service rate controls');
      await page.select('#tube-view','network');
      assert.equal(await page.evaluate(()=>window.__rail.stations),2,'one successful station catalog fetch after retry');
      pass('53 choices: 23 deep interiors, 30 network locations without isolated meshes; mixed stations, cancellation, city restoration and narrow views');
    }

    // ---- 6. Other views give the city back and stop the service clock; returning resumes it at the kept time.
    const others = ['overview', 'traffic', ...(before.hasIhub ? ['interior'] : [])];
    for (const other of others) {
      assert.equal((await state()).network.playing, true);
      await click(other); await sleep(1200); s = await state();
      assert(s.active === other && !s.network.visible && !s.network.playing && !s.menu.shown && !s.tube.time.shown && city(s), `${other}: ${JSON.stringify(s.network)}`); assert.notEqual(s.strip.name, 'Tube timetable time');
      const t1 = s.network.time; await sleep(600); assert.equal((await state()).network.time, t1, `${other}: an inactive service clock does not advance`);
      await click('londonTube'); await until(() => window.canopyTube.service.group.visible && window.canopyTube.service.clock.playing); s = await state();
      assert(s.network.time >= t1 && s.network.time < t1 + 60 && !s.model && s.menu.shown && s.menu.value === 'network', `${other}: service time retained`);
    }
    await page.click('[data-field]'); await sleep(1500); s = await state(); assert(!s.network.visible && !s.network.playing && !s.menu.shown);
    await click('overview'); await sleep(800); assert(city(await state()), 'after a physics field the city is as before');
    receipt.round_trips = others; pass(`round trips with ${others.join(', ')} and a physics field`);

    // ---- 7. The end of the hour stops the clock; Play restarts from 08:00. Reduced motion never starts it.
    await click('londonTube'); await until(() => window.canopyTube.service.group.visible); if ((await state()).network.playing) await page.click('#play');
    await seek(32390); await page.select('#tube-rate', '60'); await page.click('#play'); await until(() => window.canopyTube.service.clock.time === 32400 && !window.canopyTube.service.clock.playing);
    s = await state(); assert.equal(s.play, 'Play'); assert.equal(s.network.trains, 95);
    await page.click('#play'); await until(() => window.canopyTube.service.clock.playing && window.canopyTube.service.clock.time < 30000); await page.select('#tube-rate', '30');
    await click('overview'); await sleep(500); await page.emulateMediaFeatures([{name: 'prefers-reduced-motion', value: 'reduce'}]); await page.evaluate(() => { window.canopyTube.service.clock.playing = false; });
    await page.evaluate(() => { window.__resumeProbe = true; }); await click('londonTube'); await until(() => window.canopyTube.service.group.visible); await sleep(300);
    assert.equal((await state()).network.playing, false, 'reduced motion: the service does not start by itself');
    await page.emulateMediaFeatures([{name: 'prefers-reduced-motion', value: 'no-preference'}]);
    pass('the service stops at 09:00 and restarts from 08:00 on Play; reduced motion leaves it paused');

    // ---- 8. One renderer, notes only in the hidden details host, narrow layouts.
    s = await state(); assert.equal(s.iframes, 0);
    const notes = await page.evaluate(() => [...document.querySelectorAll('#viewer-details p')].filter(p => /^Tube network:/.test(p.textContent)).map(p => p.textContent));
    assert.equal(notes.length, 1); assert(/assumed depths/.test(notes[0]) && /not live/.test(notes[0]) && /within a second/.test(notes[0]) && /not surveyed/.test(notes[0]));
    await page.setViewport({width: 390, height: 844}); await sleep(600); await page.$eval('#tube-view', e => e.scrollIntoView({block: 'nearest', inline: 'nearest'}));
    const narrow = await page.evaluate(() => { const box = e => { const r = e.getBoundingClientRect(); return {left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height}; };
      return {page: [document.documentElement.scrollWidth, innerWidth, innerHeight], bar: box(document.querySelector('.timebar')), items: ['play', 'step', 'tube-time', 'tube-rate'].map(id => ({id, ...box(document.getElementById(id))})), menu: box(document.getElementById('tube-view')), value: document.querySelector('#step').getAttribute('aria-valuetext')}; });
    receipt.strip_390 = narrow;
    assert(narrow.page[0] <= narrow.page[1], 'no sideways scrolling'); assert(narrow.bar.left >= 0 && narrow.bar.right <= narrow.page[1] && narrow.bar.bottom <= narrow.page[2]);
    narrow.items.forEach((item, k) => { assert(item.width > 0 && item.left >= narrow.bar.left && item.right <= narrow.bar.right + 0.5, item.id); if (k) assert(item.left >= narrow.items[k - 1].right - 0.5, `${item.id} does not overlap ${narrow.items[k - 1].id}`); });
    assert(narrow.items[1].width >= 100, 'the slider stays usable'); assert(narrow.items[0].height >= 40 && narrow.items[3].height >= 40, 'touch-sized Play and rate'); assert.match(narrow.value, /^Tube timetable \d\d:\d\d:\d\d/);
    assert(narrow.menu.left >= 0 && narrow.menu.right <= narrow.page[1] && narrow.menu.width > 60, 'the station menu can be brought into view');
    if (process.env.QA_SCREENSHOTS === '1') { await page.evaluate(() => { window.__pauseDraw = false; }); await sleep(1500); await page.screenshot({path: `${out}/network-390.png`}); await page.evaluate(() => { if ('__skippedDraws' in window) window.__pauseDraw = true; }); }
    await page.setViewport({width: 1280, height: 800});
    pass('single scene, notes only in the hidden details host, 390 px layout');

    assert.deepEqual(receipt.errors, []); assert.equal(pinnedSourceRequests, 0, 'the pinned source was never requested on the regional path');
    fs.writeFileSync(`${out}/verification.json`, JSON.stringify({passed: true, regional_data: 'present', stations_declared: before.stations, pinned_source_requests: pinnedSourceRequests, ...receipt}, null, 2));
    console.log('PASS Tube regional');
  }
} finally { await browser.close(); }
