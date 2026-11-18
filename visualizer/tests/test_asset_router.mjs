import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {gzipSync} from 'node:zlib';
import vm from 'node:vm';

const source = await readFile(new URL('../site/asset-router.js', import.meta.url), 'utf8');

function worker(routes, files, cached = new Map()) {
  const listeners = {}, calls = [];
  const cache = {match: async key => cached.get(typeof key === 'string' ? key : key.url || key.href)?.clone(),
    put: async (key, value) => cached.set(typeof key === 'string' ? key : key.url || key.href, value)};
  const fetch = async request => {
    const url = typeof request === 'string' ? request : request.url || request.href;
    calls.push({url, request});
    if (url.endsWith('asset-sources.json')) return Response.json({schema_version:'1.0.0',resources:routes});
    return files.get(url)?.clone() || new Response('Not found', {status:404});
  };
  vm.runInNewContext(source, {URL, Response, DecompressionStream, Map, fetch,
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

test('external targets and parent-directory routes fail closed', async () => {
  for (const target of ['../secret','https://elsewhere.test/data','data/%2e%2e/private']) {
    const w = worker({'scenes/london/value.bin':target},new Map());
    await assert.rejects(w.get('/canopy/scenes/london/value.bin'), /Invalid public resource path/);
  }
});
