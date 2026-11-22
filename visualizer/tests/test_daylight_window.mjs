import test from 'node:test';
import assert from 'node:assert/strict';
import {daylightWindow} from '../site/viewer/daylight-window.mjs';
test('daylight window skips both nights without renumbering source frames',()=>{
 assert.deepEqual(daylightWindow([-10,0,1,50,1,0,-10],7),{start:3,end:5});
 assert.deepEqual(daylightWindow([-10,0,1,50,1,0,-10],7,true),{start:1,end:7});
});
test('polar night and missing solar metadata keep original bounds',()=>{
 for(const values of [undefined,[-1,-2],[],[NaN,1]])assert.deepEqual(daylightWindow(values,2),{start:1,end:2});
});
