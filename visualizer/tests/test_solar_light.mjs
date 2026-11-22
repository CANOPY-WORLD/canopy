import test from 'node:test';
import assert from 'node:assert/strict';
import {solarLight} from '../site/viewer/3d/solar-light.mjs';
test('night has no directional sun and sun remains below the horizon',()=>{
  for(const alt of [-20,-1,0]) assert.equal(solarLight(alt,180).intensity,0);
  assert.ok(solarLight(-10,180).position[1]<0);
});
test('east dawn and west dusk preserve ENU to rendering coordinates',()=>{
  assert.ok(solarLight(10,90).position[0]>0);
  assert.ok(solarLight(10,270).position[0]<0);
  assert.ok(solarLight(60,180).position[2]>0);
  assert.ok(solarLight(60,180).intensity>solarLight(10,180).intensity);
});
