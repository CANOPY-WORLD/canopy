import test from 'node:test';
import assert from 'node:assert/strict';
import {unpackShadow} from '../site/viewer/3d/shadow-codec.mjs';
test('packed shadow preserves bit order, rows and padded widths',()=>{
 assert.deepEqual([...unpackShadow(new Uint8Array([0x81,0x7e]),8,2)],[1,0,0,0,0,0,0,1,0,1,1,1,1,1,1,0]);
 assert.deepEqual([...unpackShadow(new Uint8Array([0xa0,0x40]),3,2)],[1,0,1,0,1,0]);
 assert.throws(()=>unpackShadow(new Uint8Array(1),9,1));
});
