import test from 'node:test';
import assert from 'node:assert/strict';
import {FrameCache} from '../site/viewer/frame-cache.mjs';

test('frame budget is byte bounded and follows least recent use', async () => {
  const cache = new FrameCache(12);
  const load = () => new Uint8Array(6);
  await cache.get('solar', 0, load);
  await cache.get('solar', 1, load);
  await cache.get('solar', 0, () => {throw Error('cached');});
  await cache.get('solar', 2, load);
  let reloaded = false;
  await cache.get('solar', 1, () => {reloaded=true;return load();});
  assert(reloaded);
  assert.equal(cache.info().bytes,12);
  await cache.get('solar',3,()=>new Uint8Array(20));
  assert.equal(cache.info().bytes,12,'oversize frames may be displayed but are not retained');
});

test('switching a widget releases old frames and prevents stale loads repopulating it', async () => {
  const cache = new FrameCache(32);
  cache.retainSources(['solar']);
  await cache.get('solar',0,()=>new Uint8Array(8));
  let resolve;
  const loading=cache.get('solar',1,()=>new Promise(r=>{resolve=r;}));
  await Promise.resolve();
  cache.retainSources(['poll']);
  assert.equal(cache.info().bytes,0);
  resolve(new Uint8Array(8));
  assert.equal((await loading).byteLength,8,'the original caller still receives its result');
  assert.equal(cache.info().bytes,0);
  await cache.get('poll',0,()=>new Uint8Array(8));
  cache.retainSources(['poll']);
  assert.equal(cache.info().bytes,8,'repeated selection preserves the active working set');
});

test('duplicate requests share work; failed prefetches can retry', async () => {
  const cache = new FrameCache(32);let calls=0;
  const load=()=>{calls++;return new Uint8Array(8);};
  const [a,b]=await Promise.all([cache.get('wind',0,load),cache.get('wind',0,load)]);
  assert.equal(a,b);assert.equal(calls,1);
  await assert.rejects(cache.get('wind',1,()=>Promise.reject(Error('offline'))),/offline/);
  await cache.get('wind',1,load);
  assert.equal(calls,2);assert.equal(cache.info().pending,0);
});
