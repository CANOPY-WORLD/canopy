import assert from 'node:assert/strict';
import test from 'node:test';
import {decodeQuantized} from '../site/viewer/quantized-field.mjs';
test('legacy irradiance linear quantization and missing value are preserved',()=>{
 const decoded=decodeQuantized(new Uint8Array([0,1,254,255]).buffer,{scale:950/254,offset:0});
 assert.equal(decoded[0],0);assert.equal(decoded[2],950);assert(Number.isNaN(decoded[3]));
});
test('log pollution preserves zero, full peak, finite concentrations and missing values',()=>{
 const reference=1e-6,peak=80.40364837646484,scale=Math.log1p(peak/reference)/254;
 const decoded=decodeQuantized(new Uint8Array([0,1,127,254,255]).buffer,{scale,reference,transform:'log1p'});
 assert.equal(decoded[0],0);assert(decoded[1]>0);assert(decoded[2]>decoded[1]);assert(Math.abs(decoded[3]-peak)<1e-5);assert(Number.isNaN(decoded[4]));
 const values=[.000235, .01, .1,1,10,80];
 const codes=Uint8Array.from(values,v=>Math.round(Math.log1p(v/reference)/scale));
 const actual=decodeQuantized(codes.buffer,{scale,reference,transform:'log1p'});
 values.forEach((v,i)=>assert(Math.abs(actual[i]/v-1)<.037));
});
test('unknown encodings fail instead of silently changing physical units',()=>{
 assert.throws(()=>decodeQuantized(new ArrayBuffer(1),{scale:1,transform:'log10',reference:1}));
 assert.throws(()=>decodeQuantized(new ArrayBuffer(1),{scale:1,transform:'log1p',reference:0}));
});
