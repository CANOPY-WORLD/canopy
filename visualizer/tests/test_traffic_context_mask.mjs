import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import * as THREE from '../site/vendor/three/build/three.module.js';

const three=new URL('../site/vendor/three/build/three.module.js',import.meta.url).href;
const code=(await readFile(new URL('../site/viewer/3d/traffic-context-mask.js',import.meta.url),'utf8')).replace("from 'three'",`from '${three}'`);
const {createTrafficContextMask}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));

test('traffic context clipping preserves live signal materials, shader hooks and geometry',()=>{
  const region=createTrafficContextMask({center:[100,-200],radius:350});
  const material=new THREE.MeshStandardMaterial();
  material.onBeforeCompile=shader=>{shader.uniforms.existing={value:7};};
  const mesh=new THREE.InstancedMesh(new THREE.BoxGeometry(),material,2);
  const geometry=mesh.geometry,matrices=mesh.instanceMatrix.array.slice();
  region.add(mesh,'outside');
  const compile=material.onBeforeCompile;region.add(mesh,'outside');
  assert.equal(material.onBeforeCompile,compile);
  assert.equal(mesh.material,material); // Recorded lamp updates keep the same reference.
  material.emissiveIntensity=2.5;assert.equal(mesh.material.emissiveIntensity,2.5);
  const shader={uniforms:{},vertexShader:'#include <project_vertex>',fragmentShader:'#include <clipping_planes_fragment>'};
  material.onBeforeCompile(shader);
  assert.equal(shader.uniforms.existing.value,7);
  assert.deepEqual(shader.uniforms.trafficContextRegion.value.toArray(),[100,200,350]);
  assert.equal(shader.uniforms.trafficContextActive.value,0);
  region.setActive(true);assert.equal(shader.uniforms.trafficContextActive.value,1);
  region.setActive(false);assert.equal(shader.uniforms.trafficContextActive.value,0);
  assert.match(shader.vertexShader,/instanceMatrix\*trafficPoint/);
  assert.match(shader.fragmentShader,/< trafficContextRegion.z/);
  assert.equal(mesh.geometry,geometry);assert.deepEqual(mesh.instanceMatrix.array,matrices);
});

test('native road paint uses the complementary boundary',()=>{
  const region=createTrafficContextMask({center:[0,0],radius:350});
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(),new THREE.MeshBasicMaterial());
  region.add(mesh,'inside');
  const shader={uniforms:{},vertexShader:'#include <project_vertex>',fragmentShader:'#include <clipping_planes_fragment>'};
  mesh.material.onBeforeCompile(shader);
  assert.match(shader.fragmentShader,/>= trafficContextRegion.z/);
});
