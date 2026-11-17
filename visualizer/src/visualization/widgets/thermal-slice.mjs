import * as THREE from 'three';
import {DataWidget} from './index.mjs';
import {enuToWorld} from '../shared/time.mjs';
import {sliceLayout} from '../shared/thermal-slice-layout.mjs';

// Presentation adapter for ordinary JSON scalar_field data; no PDE computation.
export class ThermalSlice extends DataWidget {
  initialize(context,layer,data) {
    const {active,spacing}=sliceLayout(data.positions);
    super.initialize(context,layer,data);
    const vertices=[];
    for(const signs of [[-1,-1],[1,-1],[1,1],[-1,1]]){
      const p=[0,0,0];active.forEach((axis,i)=>p[axis]=signs[i]*spacing[i]/2);vertices.push(...enuToWorld(p));
    }
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geometry.setIndex([0,1,2,0,2,3]);geometry.computeVertexNormals();
    this.instances.geometry.dispose();this.instances.geometry=geometry;
    this.instances.material.dispose();this.instances.material=new THREE.MeshBasicMaterial({side:THREE.DoubleSide});
    this.instances.computeBoundingSphere();
  }
}
