import test from 'node:test';
import assert from 'node:assert/strict';
import {createAssetQueue, fetchAsset} from '../site/viewer/3d/asset-queue.mjs';
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const wait = async predicate => {for (let i=0;i<400;i++) {if(predicate()) return; await sleep(5);} throw Error('Queue did not settle');};
const bytes = () => new ArrayBuffer(4);

test('priorities, four occupied slots and serialized preparation bound the backlog', async () => {
  const starts=[], done=[]; let preparing=0, peak=0;
  const q=createAssetQueue({load:async item=>{starts.push(item.id);return bytes();},
    prepare:async (buffer,item)=>{peak=Math.max(peak,++preparing);await sleep(5);preparing--;return item.id;},
    commit:value=>done.push(value)});
  try {
    for(let i=8;i>0;i--)q.add(String(i),{id:i},i);
    await wait(()=>done.length===8);
    assert.deepEqual(starts,[1,2,3,4,5,6,7,8]);assert.equal(peak,1);assert.equal(q.stats.peakActive,4);
    assert.equal(q.snapshot().length,0);
  } finally {q.dispose();}
});

test('cancelling a stale fetch aborts it and makes room for new demand',async()=>{
  let aborted=false;const done=[];
  const q=createAssetQueue({concurrency:1,load:(item,signal)=>item.old?new Promise((resolve,reject)=>{
    signal.addEventListener('abort',()=>{aborted=true;reject(signal.reason);});
  }):Promise.resolve(bytes()),prepare:async(b,item)=>item.id,commit:id=>done.push(id)});
  try{
    q.add('old',{old:true,id:1});await wait(()=>q.stats.requests===1);
    q.add('new',{id:2});q.cancel('old');await wait(()=>done.length===1);
    assert(aborted);assert.deepEqual(done,[2]);assert.equal(q.stats.retries,0);
  }finally{q.dispose();}
});

test('a parse completed after cancellation is disposed and never committed',async()=>{
  let finish,started=false;const discarded=[],done=[];
  const q=createAssetQueue({load:async()=>bytes(),prepare:()=>{started=true;return new Promise(r=>finish=r);},
    commit:r=>done.push(r),discard:r=>discarded.push(r)});
  try{
    q.add('stale',{});await wait(()=>started);q.cancel('stale');finish('mesh');
    await wait(()=>discarded.length===1);assert.deepEqual(done,[]);assert.deepEqual(discarded,['mesh']);
  }finally{q.dispose();}
});

test('failures retry twice, stop, and allow an explicit retry',async()=>{
  let fail=true,done=0;
  const q=createAssetQueue({retryDelay:()=>1,load:async()=>{if(fail)throw Error('temporary');return bytes();},
    prepare:async b=>b,commit:()=>done++});
  try{
    q.add('one',{});await wait(()=>q.snapshot()[0]?.state==='failed');
    assert.equal(q.stats.requests,3);assert.equal(q.stats.retries,2);
    fail=false;q.retry();await wait(()=>done===1);assert.equal(q.stats.requests,4);
  }finally{q.dispose();}
});

test('dispose also aborts downloads waiting on preparation without committing results',async()=>{
  let finish,started=false;const discarded=[],done=[];
  const q=createAssetQueue({load:async()=>bytes(),prepare:()=>{started=true;return new Promise(r=>finish=r);},
    commit:r=>done.push(r),discard:r=>discarded.push(r)});
  q.add('one',{});q.add('two',{});await wait(()=>started);q.dispose();finish('first');
  await wait(()=>discarded.length===1);await sleep(10);assert.deepEqual(done,[]);assert.equal(q.snapshot().length,0);
});

test('streamed fetch reports actual bytes and rejects truncated or oversized files',async()=>{
  const original=globalThis.fetch;
  try{
    const controller=new AbortController(), progress=[];
    globalThis.fetch=async()=>new Response(new Uint8Array([1,2,3,4]));
    assert.deepEqual([...new Uint8Array(await fetchAsset({url:'https://test.invalid/a',bytes:4},controller.signal,n=>progress.push(n)))],[1,2,3,4]);
    assert.equal(progress.at(-1),4);
    await assert.rejects(fetchAsset({url:'https://test.invalid/a',bytes:5},controller.signal),/shorter/);
    await assert.rejects(fetchAsset({url:'https://test.invalid/a',bytes:3},controller.signal),/exceeds/);
  }finally{globalThis.fetch=original;}
});
