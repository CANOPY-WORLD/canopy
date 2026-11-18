import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {gzipSync} from 'node:zlib';
import vm from 'node:vm';

const source = await readFile(new URL('../site/asset-router.js', import.meta.url), 'utf8');

function worker(routes, files, cached = new Map(), roots = null) {
  const listeners = {}, calls = [];
  const cache = {match: async key => cached.get(typeof key === 'string' ? key : key.url || key.href)?.clone(),
    put: async (key, value) => cached.set(typeof key === 'string' ? key : key.url || key.href, value)};
  const fetch = async (request, options) => {
    const url = typeof request === 'string' ? request : request.url || request.href;
    calls.push({url, request, options});
    if (url.endsWith('asset-sources.json')) return Response.json({schema_version:roots?'2.0.0':'1.0.0',resources:routes,remote_bases:roots});
    const value = files.get(url);
    return (Array.isArray(value) ? value.shift() : value)?.clone() || new Response('Not found', {status:404});
  };
  vm.runInNewContext(source, {URL, Response, Headers, DecompressionStream, Map, fetch,
    setTimeout: fn => setTimeout(fn, 0), clearTimeout,
    self:{location:{href:'https://example.test/canopy/asset-router.js'},
      addEventListener:(type, fn) => listeners[type] = fn},
    caches:{open:async () => cache}});
  return {calls, async get(path, options) {
    let promise;
    listeners.fetch({request:new Request('https://example.test'+path, options),respondWith:value => promise = value});
    return promise;
  }};
}

test('packed Scenario geometry is decoded under the project subpath', async () => {
  const url = 'https://example.test/canopy/scenario/london/data/buildings.glb.gz';
  const w = worker({'scenes/london/buildings.glb.gz':'scenario/london/data/buildings.glb.gz'},
    new Map([[url, new Response(gzipSync('glTF fixture'))]]));
  const result = await w.get('/canopy/scenes/london/buildings.glb');
  assert.equal(await result.text(), 'glTF fixture');
  assert.equal(result.headers.get('Content-Type'), 'model/gltf-binary');
  assert.equal(w.calls.at(-1).url, url);
});

test('undeclared API and raw GLB requests retain URL, query and Range headers', async () => {
  const url = 'https://example.test/canopy/project/london/assets/mesh.glb?version=2';
  const w = worker({}, new Map([[url,new Response('raw')]]));
  const result = await w.get('/canopy/project/london/assets/mesh.glb?version=2', {headers:{Range:'bytes=0-3'}});
  assert.equal(await result.text(), 'raw');
  assert.equal(w.calls.at(-1).request.headers.get('Range'), 'bytes=0-3');
});

test('a directly declared GLB is served without adding a gzip suffix', async () => {
  const url = 'https://example.test/canopy/scenario/london/data/mesh.glb';
  const w = worker({'scenes/london/mesh.glb':'scenario/london/data/mesh.glb'}, new Map([[url,new Response('glTF')]]));
  assert.equal(await (await w.get('/canopy/scenes/london/mesh.glb')).text(), 'glTF');
});

test('directory navigation resolves the cached index page', async () => {
  const cache = new Map([
    ['https://example.test/canopy/__active',new Response('canopy-complete-fixture')],
    ['https://example.test/canopy/viewer/3d/index.html',new Response('cached viewer')]
  ]);
  const w = worker({},new Map(),cache);
  assert.equal(await (await w.get('/canopy/viewer/3d/?scene=london')).text(), 'cached viewer');
});

test('undeclared external targets and parent-directory routes fail closed', async () => {
  for (const target of ['../secret','https://elsewhere.test/data','data/%2e%2e/private']) {
    const w = worker({'scenes/london/value.bin':target},new Map());
    await assert.rejects(w.get('/canopy/scenes/london/value.bin'), /Invalid public resource path|Undeclared remote data target/);
  }
});

test('packed geometry can come from an explicitly declared Scenario data website', async () => {
  const root = 'https://data.test/london/snapshots/v1/';
  const w = worker({'scenes/london/buildings.glb.gz':root+'buildings.glb.gz'},
    new Map([[root+'buildings.glb.gz',new Response(gzipSync('glTF remote fixture'))]]),new Map(),[root]);
  assert.equal(await (await w.get('/canopy/scenes/london/buildings.glb')).text(), 'glTF remote fixture');
  assert.equal(w.calls.at(-1).url, root+'buildings.glb.gz');
  assert.equal(w.calls.at(-1).options.credentials, 'omit');
  assert.equal(w.calls.at(-1).options.mode, 'cors');
});

test('remote reads retain Range but do not forward application credentials', async () => {
  const root = 'https://data.test/london/snapshots/v1/';
  const w = worker({'scenes/london/field.bin':root+'field.bin'},
    new Map([[root+'field.bin',new Response('part',{status:206})]]),new Map(),[root]);
  const response = await w.get('/canopy/scenes/london/field.bin',
    {headers:{Range:'bytes=4-7',Authorization:'Bearer private','X-Private':'private'}});
  assert.equal(response.status,206);
  const {headers,credentials,redirect} = w.calls.at(-1).options;
  assert.equal(headers.get('Range'),'bytes=4-7');
  assert.equal(headers.get('Authorization'),null);
  assert.equal(headers.get('X-Private'),null);
  assert.equal(credentials,'omit'); assert.equal(redirect,'error');
});

test('remote targets are bounded by the exact snapshot and use clean HTTPS URLs', async () => {
  const root = 'https://data.test/london/snapshots/v1/';
  for(const target of ['https://data.test/london/snapshots/v2/value.bin',
    'https://data.test/london/snapshots/v1/../secret',root+'%2e%2e/secret',root+'value.bin?token=secret',
    'https://user:secret@data.test/london/snapshots/v1/value.bin','http://data.test/london/snapshots/v1/value.bin']) {
    const w = worker({'scenes/london/value.bin':target},new Map(),new Map(),[root]);
    await assert.rejects(w.get('/canopy/scenes/london/value.bin'));
  }
});

test('an offline verified resource is read from its logical URL without contacting the data host', async () => {
  const root = 'https://data.test/london/snapshots/v1/';
  const cache = new Map([
    ['https://example.test/canopy/__active',new Response('canopy-complete-fixture')],
    ['https://example.test/canopy/scenes/london/field.bin',new Response('cached field')]
  ]);
  const w = worker({'scenes/london/field.bin':root+'field.bin'},new Map(),cache,[root]);
  assert.equal(await (await w.get('/canopy/scenes/london/field.bin')).text(),'cached field');
  assert.equal(w.calls.filter(c=>c.url.startsWith(root)).length,0);
});

test('a transient Pages 503 is retried before returning a resource', async () => {
  const url = 'https://example.test/canopy/scenario/london/data/field.bin';
  const w = worker({'scenes/london/field.bin':'scenario/london/data/field.bin'},
    new Map([[url, [new Response('Unavailable',{status:503}),new Response('field')]]]));
  assert.equal(await (await w.get('/canopy/scenes/london/field.bin')).text(), 'field');
  assert.equal(w.calls.filter(call => call.url === url).length, 2);
});

test('persistent gateway failures stop after four attempts', async () => {
  const url = 'https://example.test/canopy/scenario/london/data/field.bin';
  const w = worker({'scenes/london/field.bin':'scenario/london/data/field.bin'},
    new Map([[url, new Response('Unavailable',{status:503})]]));
  assert.equal((await w.get('/canopy/scenes/london/field.bin')).status, 503);
  assert.equal(w.calls.filter(call => call.url === url).length, 4);
});
