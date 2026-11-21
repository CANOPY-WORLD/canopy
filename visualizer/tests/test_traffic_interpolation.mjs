import test from 'node:test';
import assert from 'node:assert/strict';
import {interpolateVehicle} from '../site/viewer/traffic-interpolation.mjs';
test('display interpolation preserves identities and shortest heading turn',()=>{
 const a={id:7,x:0,north:4,heading:179*Math.PI/180,height:2,pitch:0};
 const b={...a,x:10,north:8,heading:-179*Math.PI/180,height:4,pitch:.2};
 const v=interpolateVehicle(a,b,.5);assert.equal(v.x,5);assert.equal(v.north,6);assert.equal(v.height,3);assert(Math.abs(v.heading-Math.PI)<1e-8);assert.equal(v.id,7);
 assert.equal(interpolateVehicle(a,undefined,.5),a);assert.equal(interpolateVehicle(a,b,0),a);
});
