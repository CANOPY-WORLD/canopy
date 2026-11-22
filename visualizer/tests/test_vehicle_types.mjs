import test from 'node:test';
import assert from 'node:assert/strict';
import {vehicleDimensions,vehicleCenter,VEHICLE_TYPES} from '../site/viewer/vehicle-types.mjs';
test('recorded vehicle dimensions override illustrative types',()=>{
 assert.equal(Object.keys(VEHICLE_TYPES).length,6);
 assert.equal(vehicleDimensions('motorcycle').width,.8);
 assert.equal(vehicleDimensions('bus',{bus:{length:12,width:2.5,height:3}}).length,12);
 assert.throws(()=>vehicleDimensions('unknown'));
 assert.throws(()=>vehicleDimensions('car',{car:{length:-1,width:2,height:1}}));
});
test('front bumper reference is converted to body center without changing source coordinates',()=>{
 assert.deepEqual(vehicleCenter(10,20,0,10,'front_bumper'),[5,20]);
 const p=vehicleCenter(10,20,Math.PI/2,10,'front_bumper');assert(Math.abs(p[0]-10)<1e-10);assert.equal(p[1],15);
 assert.deepEqual(vehicleCenter(10,20,0,10),[10,20]);
 assert(Math.abs(vehicleCenter(10,20,0,10,'front_bumper',Math.PI/3)[0]-7.5)<1e-10);
 assert.throws(()=>vehicleCenter(0,0,0,4,'unknown'));
});
import {readFile} from 'node:fs/promises';
test('rendered types fit declared dimensions and bumper-anchored placement',async()=>{
 const three=new URL('../site/vendor/three/build/three.module.js',import.meta.url).href;
 const utils=(await readFile(new URL('../site/vendor/three/examples/jsm/utils/BufferGeometryUtils.js',import.meta.url),'utf8')).replace("from 'three'",`from '${three}'`);
 const utilURL='data:text/javascript;base64,'+Buffer.from(utils).toString('base64');
 const types=new URL('../site/viewer/vehicle-types.mjs',import.meta.url).href;
 const code=(await readFile(new URL('../site/viewer/3d/corridor-vehicles.js',import.meta.url),'utf8')).replace("from 'three'",`from '${three}'`).replace("from 'three/addons/utils/BufferGeometryUtils.js'",`from '${utilURL}'`).replace("from '../vehicle-types.mjs'",`from '${types}'`);
 const {createCorridorVehicles}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
 const vehicles=createCorridorVehicles(2,{position_reference:'front_bumper'});vehicles.begin();
 for(const kind of Object.keys(VEHICLE_TYPES))vehicles.set(1,kind,100,200,0,0,0);
 vehicles.finish();assert.equal(vehicles.group.count,6);
 for(const mesh of vehicles.group.children){const kind=mesh.name.split(' ')[0],d=VEHICLE_TYPES[kind];mesh.geometry.computeBoundingBox();const b=mesh.geometry.boundingBox;assert(b.min.x>=-d.length/2-1e-5&&b.max.x<=d.length/2+1e-5);assert(b.min.z>=-d.width/2-1e-5&&b.max.z<=d.width/2+1e-5);assert(b.min.y>=-1e-5&&b.max.y<=d.height+1e-5);assert(Math.abs(mesh.instanceMatrix.array[12]-(100-d.length/2))<1e-5)}
 vehicles.begin();vehicles.finish();assert.equal(vehicles.group.count,0);for(const mesh of vehicles.group.children)assert.equal(mesh.count,0);
});
