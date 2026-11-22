import test from 'node:test';
import assert from 'node:assert/strict';
import {validateNativeTraffic,nativeTrafficSamples} from '../site/viewer/native-traffic-samples.mjs';
const car=(id,x,z=3,heading=0)=>[id,'car',x,20,z,heading,.1,10];
const data=()=>({schema:'experimental-offline-sumo-review-1',coordinate_frame:'ENU',position_reference:'front_bumper',vehicle_types:{car:{length:4.5,width:1.8,height:1.5}},frames:[{time:680,vehicles:[car('a',0),car('gone',4)]},{time:680.1,vehicles:[car('a',1,5),car('new',6)]}]});
test('preserves absolute time and native elevation; no ghost arrivals/departures',()=>{
 const {frames}=validateNativeTraffic(data());const sample=nativeTrafficSamples(frames,.5);
 assert.equal(sample.vehicles.length,1);assert.equal(sample.time,680.05);assert.equal(sample.vehicles[0][2],.5);assert.equal(sample.vehicles[0][4],4);
 assert.deepEqual(nativeTrafficSamples(frames,1).vehicles,[...frames[1].vehicles.values()]);
});
test('rejects missing samples and unsupported frames; headings wrap shortest way',()=>{
 const d=data();d.frames[1].time=680.2;assert.throws(()=>validateNativeTraffic(d),/Missing/);
 d.frames[1].time=680.1;d.frames[0].vehicles[0][5]=Math.PI-.1;d.frames[1].vehicles[0][5]=-Math.PI+.1;
 assert(Math.abs(nativeTrafficSamples(validateNativeTraffic(d).frames,.5).vehicles[0][5]-Math.PI)<1e-9);
 d.coordinate_frame='unknown';assert.throws(()=>validateNativeTraffic(d),/Unsupported/);
});
