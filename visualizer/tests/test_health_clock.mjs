import test from 'node:test';
import assert from 'node:assert/strict';
import {clockText,departureSeconds} from '../src/visualization/healthy-route/health-clock.mjs';
test('scenario clock converts departure exactly without inventing UTC or wrapping days',()=>{
  assert.equal(departureSeconds('08:50',31800,46200),0);
  assert.equal(departureSeconds('09:00:30',31800,46200),630);
  assert.equal(clockText(31800+630),'09:00:30');
  for(const t of ['08:49:59','21:40:01','24:00','09:60','09:00:60','', '900'])assert.equal(departureSeconds(t,31800,46200),null);
});
