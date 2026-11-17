import * as THREE from 'three';
import {DataWidget} from './index.mjs';
import {assetURL,enuToWorld} from '../shared/time.mjs';

// Recorded roof cells carry geometry; the scalar payload remains one value per building.
export class BuildingHeat extends DataWidget {
  async load(context,layer,signal){
    const path=context.manifest.provenance.parameters.presentation.building_catalog;
    const response=await fetch(assetURL(context.baseURL,path),{signal});
    if(!response.ok)throw new Error('Building catalogue unavailable');
    this.catalog=await response.json();
    await super.load(context,layer,signal);
    if(this.catalog.buildings.length!==this.data.positions.length)throw new Error('Building count mismatch');
    this.group.remove(this.instances);this.instances.geometry.dispose();this.instances.material.dispose();
    const [dx,dy]=this.catalog.cell_size_m;
    this.roofs=[];this.labels=[];
    this.catalog.buildings.forEach((b,i)=>{
      const cells=b.roof_positions_enu_m;
      const roof=new THREE.InstancedMesh(new THREE.BoxGeometry(dx,.4,dy),new THREE.MeshBasicMaterial({color:0xffb545}),cells.length);
      cells.forEach((p,j)=>roof.setMatrixAt(j,new THREE.Matrix4().makeTranslation(...enuToWorld(p))));roof.instanceMatrix.needsUpdate=true;roof.computeBoundingSphere();roof.userData.buildingIndex=i;this.group.add(roof);this.roofs.push(roof);
      const canvas=document.createElement('canvas');canvas.width=512;canvas.height=96;
      const texture=new THREE.CanvasTexture(canvas);const label=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,depthTest:false,transparent:true}));
      label.position.set(...enuToWorld(this.data.positions[i]));label.position.y+=10;label.scale.set(90,17,1);label.renderOrder=5;label.userData.buildingIndex=i;this.group.add(label);this.labels.push({canvas,texture});
    });this.setTime(this.seconds);
  }
  setTime(seconds){
    super.setTime(seconds);if(!this.roofs||!this.available)return;
    this.roofs.forEach((roof,i)=>{
      const value=this.current[i],fraction=(value-this.range[0])/(this.range[1]-this.range[0]||1);
      roof.material.color.setHSL(.12-.09*fraction,.85,.55);
      const {canvas,texture}=this.labels[i],ctx=canvas.getContext('2d');ctx.clearRect(0,0,512,96);ctx.fillStyle='rgba(15,25,35,.9)';ctx.fillRect(0,0,512,96);ctx.fillStyle='#ffe0a0';ctx.font='25px sans-serif';ctx.fillText(this.catalog.buildings[i].name,12,34);ctx.font='24px sans-serif';ctx.fillText(`${value.toFixed(1)} ${this.layer.field.unit}${this.layer.field.unit==='MWh'?' / cycle':''} · assumed`,12,73);texture.needsUpdate=true;
    });
  }
  pick({raycaster}){
    if(!this.visible||!this.available)return null;
    const hit=raycaster.intersectObject(this.group,true)[0];if(!hit)return null;
    const i=hit.object.userData.buildingIndex;
    return {layer_id:this.layer.id,entity_id:this.catalog.buildings[i].id,name:this.catalog.buildings[i].name,value:this.current[i],unit:this.layer.field.unit,distance:hit.distance};
  }
  dispose(){this.instances?.geometry.dispose();this.instances?.material.dispose();super.dispose();}
}
