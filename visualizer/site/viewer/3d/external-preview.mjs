// Declared compatibility previews, not scientific Assets or shared-clock layers.
export const SCENE_PREVIEWS = Object.freeze({
  imperial_corridor_8km: [{
    id: 'londonTube', label: 'London Tube', after: 'interior',
    url: 'https://srst-by722.github.io/london-tube-walk-preview/',
  }],
});

/** Cross-origin previews own their controls; removal stops their renderer and clock. */
export function createExternalPreview(tabs) {
  const host = document.createElement('section');
  host.id = 'external-preview'; host.hidden = true;
  document.body.append(host);
  let selected = null, timer;
  const position = () => host.style.top = `${Math.ceil(tabs.getBoundingClientRect().bottom + 8)}px`;
  const observer = new ResizeObserver(position); observer.observe(tabs);
  window.addEventListener('resize', position);
  function hide() {
    clearTimeout(timer); selected = null; host.replaceChildren(); host.hidden = true;
    document.body.classList.remove('external-preview-active');
  }
  function show(config) {
    if (selected === config.id) return;
    const url = new URL(config.url);
    if (url.protocol !== 'https:' || url.username || url.password) throw new Error('Preview requires a public HTTPS URL');
    hide(); selected = config.id; host.hidden = false;
    document.body.classList.add('external-preview-active'); position();
    const frame = document.createElement('iframe');
    frame.title = `${config.label} interactive preview`;
    frame.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox');
    frame.referrerPolicy = 'no-referrer';
    const status = document.createElement('div'); status.className = 'preview-status';
    const message = document.createElement('span'); message.setAttribute('role', 'status');
    message.textContent = 'Loading preview… ';
    const link = document.createElement('a'); link.href = url.href; link.target = '_blank';
    link.rel = 'noopener noreferrer'; link.textContent = 'Open preview separately';
    status.append(message, link);
    const failed = () => { message.textContent = 'If the preview is unavailable, '; status.hidden = false; };
    frame.addEventListener('load', () => { clearTimeout(timer); status.hidden = true; });
    frame.addEventListener('error', failed);
    timer = setTimeout(failed, 30000);
    frame.src = url.href; host.append(frame, status);
    // Keep a recovery link available even when a cross-origin error page fires load.
    const recovery = link.cloneNode(true); recovery.className = 'preview-recovery'; host.append(recovery);
  }
  return { show, hide, dispose() { hide(); observer.disconnect(); window.removeEventListener('resize', position); host.remove(); } };
}
