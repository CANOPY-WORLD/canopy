import test from 'node:test';
import assert from 'node:assert/strict';
import {sampleRecording,chartPath,boundedPlaybackTime} from '../src/visualization/healthy-route/recorded-health-state.mjs';
const rows=[{world_seconds:10,seconds:0,scene_m:[1,2,3],enu_m:[1,-3,0],pmx:0,temperature:null,sunlight:10},{world_seconds:20,seconds:10,scene_m:[3,4,5],enu_m:[3,-5,0],pmx:2,temperature:20,sunlight:null}];
test('range serialization still reaches a fractional recorded final sample',()=>{
 for(const start of [0,14437]){const end=start+10.486710917333625;
  assert.equal(boundedPlaybackTime(Number(end.toPrecision(15)),start,end),end);
  assert.equal(boundedPlaybackTime(end-.0001,start,end),end-.0001);
 }
});
test('recorded seek uses exact source coordinates and keeps missing fields unavailable',()=>{
 const r=sampleRecording(rows,15);assert.deepEqual(r.scene_m,[2,3,4]);assert.equal(r.pmx,1);assert.equal(r.temperature,null);assert.equal(r.sunlight,null);
 assert.equal(sampleRecording(rows,9),null);assert.equal(sampleRecording(rows,21),null);assert.equal(sampleRecording(rows,20),rows[1]);
});
test('a declared trajectory gap is not interpolated or connected on charts',()=>{
 const r=structuredClone(rows);r[1].gap_before=true;assert.equal(sampleRecording(r,15).scene_m,null);assert.equal((chartPath(r,'pmx',100,50).match(/M/g)||[]).length,2);
 assert.equal(chartPath(rows,'temperature',100,50).includes('L'),false);
});
test('physiology never anticipates the next five-minute prediction',()=>{
 const r=[{...rows[0],world_seconds:299,seconds:299,breathing:16,health_score:99},{...rows[1],world_seconds:300,seconds:300,breathing:18,health_score:97}];
 assert.equal(sampleRecording(r,299.9).breathing,16);assert.equal(sampleRecording(r,299.9).health_score,99);
 assert.equal(sampleRecording(r,300).breathing,18);assert.match(chartPath(r,'breathing',100,50,true),/H100\.000V/);
});
test('estimated sunlight and its provenance stay separate from missing native sunlight',()=>{
 const a={...rows[0],sunlight:null,sunlight_estimate:100,input_estimates:{sunlight:{method:'inverse_distance_weighted_estimate',distance_m:12}}};
 const b={...rows[1],sunlight:null,sunlight_estimate:200};const s=sampleRecording([a,b],15);
 assert.equal(s.sunlight,null);assert.equal(s.sunlight_estimate,100);assert.equal(s.input_estimates.sunlight.distance_m,12);
 assert.match(chartPath([a,b],'sunlight_estimate',100,50,true),/H100/);
});
