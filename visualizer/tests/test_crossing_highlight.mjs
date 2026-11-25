import test from 'node:test';
import assert from 'node:assert/strict';
import {activeCrossingAt} from '../src/visualization/healthy-route/crossing-highlight-state.mjs';
const recording={departure_s:14400,route_timeline:[{kind:'Waiting',crossing_id:'a',start:0,end:17},{kind:'Crossing',crossing_id:'a',start:17,end:30},{kind:'Walking',start:30,end:40},{kind:'Waiting',crossing_id:'b',start:40,end:45}]};
test('highlight follows saved wait and crossing boundaries on the scenario clock',()=>{
 assert.equal(activeCrossingAt(recording,14399),null);
 assert.deepEqual(activeCrossingAt(recording,14416.5),{crossingId:'a',movement:'Waiting',waitRemaining:.5});
 assert.deepEqual(activeCrossingAt(recording,14417),{crossingId:'a',movement:'Crossing',waitRemaining:0});
 assert.equal(activeCrossingAt(recording,14430),null);
 assert.equal(activeCrossingAt(recording,14440).crossingId,'b');
 assert.equal(activeCrossingAt(recording,14445),null);
 assert.equal(activeCrossingAt(recording,14401).waitRemaining,16);
 assert.equal(activeCrossingAt({...recording,route_timeline:[]},14401),null);
 const edge=92.78283656552131;
 const fractional={departure_s:14400,route_timeline:[{kind:'Crossing',crossing_id:'a',start:84,end:edge},{kind:'Walking',start:edge,end:104}]};
 assert.equal(activeCrossingAt(fractional,14400+edge),null);
});
