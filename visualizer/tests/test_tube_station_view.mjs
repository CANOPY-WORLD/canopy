import {test} from 'node:test';
import assert from 'node:assert/strict';
import {stationView} from '../site/viewer/3d/tube-station-view.mjs';
const platforms=[{template:'open_cutting',centre_enu:[1,2,-3]},{template:'deep',centre_enu:[4,5,-20]}];
test('mixed station uses its source deep platform rather than an open saved frame',()=>{
 const result=stationView({name:'Mixed',platforms:[0,1],statics:[],view:{frame:0}},platforms,[]);
 assert.equal(result.kind,'deep');assert.equal(result.frame,1);assert.deepEqual(result.centre,[4,5,-20]);
});
test('surface and static-only stations select exported platforms at their source coordinates',()=>{
 for(const [station,statics,centre] of [[{name:'Surface',platforms:[0],statics:[],view:{frame:0}},[],[1,2,-3]],[{name:'Static',platforms:[],statics:[0],view:{frame_static:0}},[{centre_enu:[7,8,2]}],[7,8,2]]]){
 const result=stationView(station,platforms,statics);assert.equal(result.kind,'open');assert.deepEqual(result.centre,centre);assert.match(result.label,/platform/);
 }
});
