import test from 'node:test';
import assert from 'node:assert/strict';
import {interpolateVehicle} from '../site/viewer/traffic-interpolation.mjs';
test('display interpolation preserves identities and shortest heading turn',()=>{
 const a={id:7,x:0,north:4,heading:179*Math.PI/180,height:2,pitch:0};
 const b={...a,x:10,north:8,heading:-179*Math.PI/180,height:4,pitch:.2};
 const v=interpolateVehicle(a,b,.5);assert.equal(v.x,5);assert.equal(v.north,6);assert.equal(v.height,3);assert(Math.abs(v.heading-Math.PI)<1e-8);assert.equal(v.id,7);
 assert.equal(interpolateVehicle(a,undefined,.5),a);assert.equal(interpolateVehicle(a,b,0),a);
});

const sample=(x,heading=0)=>({id:1,x,north:0,height:0,pitch:0,heading});
test('speed is continuous at saved samples without overshooting stops',()=>{
 const p=sample(0),a=sample(2),b=sample(8),c=sample(10),d=sample(10),eps=1e-5;
 const left=(b.x-interpolateVehicle(a,b,1-eps,p,c).x)/eps;
 const right=(interpolateVehicle(b,c,eps,a,d).x-b.x)/eps;
 assert(Math.abs(left-right)<1e-3);
 for(let i=0;i<=100;i++){
  const t=i/100,v=interpolateVehicle(b,c,t,a,d);
  assert(v.x>=8&&v.x<=10);
  assert.equal(interpolateVehicle(c,d,t,b,d).x,10);
 }
 assert.equal(interpolateVehicle(a,b,1,p,c),b);
});
test('turn velocity crosses angle wrap continuously and missing identities stay absent',()=>{
 const p=sample(0,170*Math.PI/180),a=sample(1,179*Math.PI/180),b=sample(2,-179*Math.PI/180),c=sample(3,-170*Math.PI/180);
 const mid=interpolateVehicle(a,b,.5,p,c);assert(Math.abs(mid.heading-Math.PI)<1e-8);
 assert.equal(interpolateVehicle(a,{...b,id:2},.5,p,c),a);
 assert.deepEqual(interpolateVehicle(a,b,.5,{...p,id:2},{...c,id:2}),interpolateVehicle(a,b,.5));
 assert.deepEqual(a,sample(1,179*Math.PI/180));
});
