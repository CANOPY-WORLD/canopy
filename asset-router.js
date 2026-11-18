/* Scenario-owned data; all URLs are relative to this Canopy Pages deployment. */
const base = new URL('./', self.location.href);
const CONTROL = 'canopy-cache-control';
const activeKey = new URL('__active', base).href;
let sources;

function resourceURL(path) {
  if (typeof path !== 'string' || !path || path.startsWith('/') || /[\\%?#:]/.test(path) ||
      path.split('/').some(part => !part || part === '.' || part === '..')) {
    throw Error('Invalid public resource path');
  }
  const url = new URL(path, base);
  if (url.origin !== base.origin || !url.pathname.startsWith(base.pathname)) throw Error('Public resource escapes Canopy');
  return url;
}

async function activeCache() {
  const selected = await (await caches.open(CONTROL)).match(activeKey);
  return selected ? caches.open(await selected.text()) : null;
}

async function readSources() {
  const url = new URL('asset-sources.json', base);
  let response;
  try {
    response = await fetch(url, { cache: 'no-cache' });
    if (!response.ok) throw Error('Public resource index unavailable');
  } catch (error) {
    response = await (await activeCache())?.match(url);
    if (!response) throw error;
  }
  const data = await response.json();
  if (data.schema_version !== '1.0.0' || !data.resources || typeof data.resources !== 'object')
    throw Error('Unsupported public resource index');
  const map = new Map();
  for (const [path, target] of Object.entries(data.resources)) {
    resourceURL(path);
    map.set(path, resourceURL(target));
  }
  return map;
}

function getSources() {
  return sources ||= readSources().catch(error => { sources = undefined; throw error; });
}

self.addEventListener('install', event => event.waitUntil(getSources().then(() => self.skipWaiting())));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('message', event => {
  if (event.data?.type !== 'activate-cache' || !event.data.name?.startsWith('canopy-complete-')) return;
  event.waitUntil((async () => {
    await (await caches.open(CONTROL)).put(activeKey, new Response(event.data.name));
    event.ports[0]?.postMessage({ ok: true });
  })());
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (url.origin !== base.origin || !url.pathname.startsWith(base.pathname) || event.request.method !== 'GET') return;
  event.respondWith((async () => {
    const requestedPath = url.pathname.slice(base.pathname.length);
    const path = !requestedPath || requestedPath.endsWith('/') ? requestedPath + 'index.html' : requestedPath;
    const map = await getSources();
    const geometry = path.endsWith('.glb') && !map.has(path) && map.has(path + '.gz');
    const resourcePath = geometry ? path + '.gz' : path;
    const logicalURL = new URL(resourcePath, base);
    const network = async () => {
      const target = map.get(resourcePath);
      if (!target) return fetch(event.request);
      return fetch(target, { headers: geometry ? undefined : event.request.headers,
        cache: event.request.cache, credentials: 'same-origin', signal: event.request.signal });
    };
    if (event.request.cache === 'no-store' && !geometry) return network();
    const cache = await activeCache();
    const cached = () => cache?.match(logicalURL, { ignoreSearch: true });
    if (geometry) {
      const response = await cached() || await network();
      if (!response.ok) return response;
      return new Response(response.body.pipeThrough(new DecompressionStream('gzip')),
        { headers: { 'Content-Type': 'model/gltf-binary' } });
    }
    if (['', 'index.html', 'download-manifest.json', 'preload.js', 'asset-sources.json'].includes(path)) {
      try { const response = await network(); return response.ok ? response : await cached() || response; }
      catch (error) { const response = await cached(); if (response) return response; throw error; }
    }
    return await cached() || network();
  })());
});
