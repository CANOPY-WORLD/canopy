import test from 'node:test';
import assert from 'node:assert/strict';
import {createCameraJourney,sampleJourney} from '../site/viewer/3d/camera-journey.mjs';
const frames=[{time:2,position:[4,2,0],target:[0,2,0]},{time:5,position:[4,2,3],target:[0,2,3]}];
test('journey begins at current pose and joins segments continuously',()=>{
 const j=createCameraJourney(frames);assert.deepEqual(j.start([10,20,30],[1,2,3]).position,[10,20,30]);
 const all=[{time:0,position:[10,20,30],target:[1,2,3]},...frames];
 assert.deepEqual(sampleJourney(all,2).position,frames[0].position);
 for(const t of [2-1e-6,2+1e-6])assert(Math.hypot(...sampleJourney(all,t).position.map((v,i)=>v-frames[0].position[i]))<1e-5);
});
test('pause, seek, end, replay and reduced motion use a bounded presentation clock',()=>{
 const j=createCameraJourney(frames);j.start([0,0,0],[1,0,0]);j.tick(1);j.toggle();j.tick(1);assert.equal(j.time,1);
 j.seek(99);assert.equal(j.time,5);assert.equal(j.playing,false);j.toggle();assert.equal(j.time,0);assert.equal(j.playing,true);
 j.start([0,0,0],[1,0,0],true);assert.equal(j.time,5);assert.equal(j.playing,false);assert.deepEqual(j.pose.position,frames[1].position);
});
test('reject invalid camera paths',()=>{for(const f of [[],[{...frames[0],time:0}],[frames[1],frames[0]],[{...frames[0],position:[NaN,0,0]}]])assert.throws(()=>createCameraJourney(f));});

test('distant interior entry rises over the city and rejoins the authored route',()=>{
 const frames=[{time:1.5,position:[1000,40,1000],target:[1000,32,980]},{time:4,position:[1000,34,980],target:[990,34,980]}];
 const j=createCameraJourney(frames,{safeApproach:true});
 assert.deepEqual(j.start([0,-20,0],[10,-20,0]).position,[0,-20,0]);
 assert.equal(j.duration,5.7);j.seek(1.6);assert(j.pose.position[1]>100);
 j.seek(3.2);assert.deepEqual(j.pose.position,frames[0].position);
 j.seek(j.duration);assert.deepEqual(j.pose.position,frames[1].position);
 j.start([1000,50,1020],[1000,40,980]);assert.equal(j.duration,4);
 j.start([0,10000,0],[0,0,0],true);assert.equal(j.playing,false);assert.deepEqual(j.pose.position,frames[1].position);
});
