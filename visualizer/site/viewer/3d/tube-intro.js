// Presentation-only camera sequence around the source preview's public pilot API.
(() => {
  let cancelled = false, started = false;
  const reveal = () => {
    document.documentElement.setAttribute('data-canopy-intro-ready', '');
    const origin = document.querySelector('meta[name="canopy-parent-origin"]')?.content;
    if (origin) requestAnimationFrame(() => parent.postMessage({type: 'canopy-preview-ready'}, origin));
  };
  // Preserve the source's clock and handlers, but use Canopy's two-control footer.
  const style = document.createElement('style');
  style.textContent = `
    .bar{box-sizing:border-box;left:50%;right:auto;bottom:max(16px,env(safe-area-inset-bottom));transform:translateX(-50%);width:min(760px,calc(100% - 28px));max-height:none;overflow:visible;display:flex;flex-wrap:nowrap;align-items:center;gap:10px;padding:8px 12px;background:rgba(18,21,26,.82);backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,.12);border-radius:10px;color:#e8e8e4}
    .bar #play{box-sizing:border-box;font:12px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#e8e8e4;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.18);border-radius:6px;padding:4px 0;width:40px;min-height:40px;flex:0 0 auto;cursor:pointer}
    .bar #time{flex:1;width:100%;min-width:0;min-height:40px;margin:0}
    .bar :focus-visible{outline:2px solid #7ac9b2;outline-offset:3px}
    #canopy-playback-options{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
  `;
  document.head.append(style);
  const bar = document.querySelector('.bar'), play = document.getElementById('play'), time = document.getElementById('time');
  const options = document.createElement('div'); options.id = 'canopy-playback-options';
  for (const node of [...bar.children]) if (node !== play && node !== time) options.append(node);
  document.getElementById('controls').append(options);
  bar.setAttribute('role', 'group'); bar.setAttribute('aria-label', 'Playback');
  time.setAttribute('aria-label', 'Recorded playback progress');
  const syncPlay = () => {
    const text = play.textContent.trim();
    if (text !== 'Pause' && text !== 'Play') return;
    play.setAttribute('aria-label', text); play.textContent = text === 'Pause' ? '❚❚' : '▶';
  };
  new MutationObserver(syncPlay).observe(play, {childList:true,characterData:true,subtree:true}); syncPlay();
  const clock = document.getElementById('clock');
  const syncClock = () => time.setAttribute('aria-valuetext', clock.textContent);
  new MutationObserver(syncClock).observe(clock,{childList:true,characterData:true,subtree:true}); syncClock();
  const fallback = setTimeout(reveal, 45000);
  const stop = () => { cancelled = true; reveal(); clearTimeout(fallback); document.documentElement.dataset.canopyIntro = 'manual'; };
  for (const event of ['pointerdown', 'wheel', 'keydown']) window.addEventListener(event, stop, {once: true, passive: true});
  function ready() {
    if (!window.__ready || !window.pilot) { requestAnimationFrame(ready); return; }
    // Run after the source page's own first-platform initialization.
    requestAnimationFrame(() => requestAnimationFrame(start));
  }
  function start() {
    if (started || cancelled) return;
    started = true;
    const p = window.pilot;
    const index = p.platforms.findIndex(item => item.id === '940GZZLUSKS_eastbound');
    if (index < 0) return;
    p.setPlatform(index);
    document.getElementById('next').click();
    p.view('p' + index);
    const close = p.cameraPose();
    p.view('overview'); p.setNet(true);
    const wide = p.cameraPose();
    reveal(); clearTimeout(fallback);
    // Hide the large source controls while retaining its Show controls button.
    const controls = document.getElementById('controls');
    if (controls && !controls.hidden) document.getElementById('toggle').click();
    const T = p.debug.THREE;
    const pose = (eye, target) => p.look(new T.Vector3(...eye), new T.Vector3(...target));
    const state = { phase: 'overview', wide, close, station: p.platforms[index].id };
    window.canopyTubeIntro = state;
    document.documentElement.dataset.canopyIntro = 'overview';
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) { state.phase = 'overview-static'; return; }
    const began = performance.now() + 800; // Allow the city-to-network crossfade to finish.
    const tick = now => {
      if (cancelled) { state.phase = 'manual'; return; }
      const elapsed = (now - began) / 1000;
      if (elapsed < 3) { requestAnimationFrame(tick); return; }
      if (state.phase === 'overview') {
        p.view('p' + index); // Apply the source's appropriate station visibility.
        pose(wide.eye, wide.target);
        state.phase = 'zoom'; document.documentElement.dataset.canopyIntro = 'zoom';
      }
      const t = Math.min(1, (elapsed - 3) / 7);
      const eased = t * t * (3 - 2 * t);
      // Exponential distance gives the station approach time at pedestrian scale.
      const target = wide.target.map((v,i) => v + (close.target[i] - v) * eased);
      const a = new T.Vector3(...wide.eye).sub(new T.Vector3(...wide.target));
      const b = new T.Vector3(...close.eye).sub(new T.Vector3(...close.target));
      const distance = Math.exp(Math.log(a.length()) * (1-eased) + Math.log(b.length()) * eased);
      const offset = a.normalize().lerp(b.normalize(), eased).normalize().multiplyScalar(distance);
      pose(target.map((v,i) => v + offset.getComponent(i)), target);
      if (t < 1) requestAnimationFrame(tick);
      else { state.phase = 'station'; document.documentElement.dataset.canopyIntro = 'station'; }
    };
    requestAnimationFrame(tick);
  }
  ready();
})();
