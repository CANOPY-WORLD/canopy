// Presentation-only camera sequence around the source preview's public pilot API.
(() => {
  let cancelled = false, started = false;
  const reveal = () => document.documentElement.setAttribute('data-canopy-intro-ready', '');
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
    const began = performance.now();
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
