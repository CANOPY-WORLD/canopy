import * as THREE from 'three';
import {worldPerPixel} from './route-presentation.mjs';

// Local inspection annotations only. Their pixel size is not a physical dimension.
export function createActiveCrossingCue(heads,appearance){
 const options=appearance.active_highlight??{head_height_px:56,label_width_px:190,label_height_px:64};
 for(const key of ['head_height_px','label_width_px','label_height_px'])if(!Number.isFinite(options[key])||options[key]<=0)throw Error('Invalid active-crossing presentation: '+key);
 const group=new THREE.Group();group.name='health-active-crossing-cue';group.visible=false;
 const canvas=document.createElement('canvas');canvas.width=380;canvas.height=128;
 const context=canvas.getContext('2d'),texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
 const label=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,depthTest:false,depthWrite:false,toneMapped:false}));label.name='health-active-crossing-label';label.center.set(.5,0);label.renderOrder=96;group.add(label);
 const borderCanvas=document.createElement('canvas');borderCanvas.width=80;borderCanvas.height=144;
 const borderContext=borderCanvas.getContext('2d');borderContext.strokeStyle='white';borderContext.lineWidth=7;borderContext.beginPath();borderContext.roundRect(4,4,72,136,12);borderContext.stroke();
 const borderTexture=new THREE.CanvasTexture(borderCanvas);borderTexture.colorSpace=THREE.SRGBColorSpace;
 const frames=[];let selected=[],lastText='';
 function update(active){
  selected=active?heads.filter(h=>h.userData.crossingId===active.crossingId):[];
  for(const h of heads){const on=selected.includes(h);h.userData.activeCrossing=on;h.material.depthTest=!on;h.renderOrder=on?95:0;if(!on)h.scale.set(appearance.head_width_m,appearance.head_height_m,1);}
  group.visible=selected.length>0;group.userData.crossingId=group.visible?active.crossingId:null;
  frames.forEach(f=>f.visible=false);if(!group.visible)return;
  const green=selected[0].userData.state==='green',state=green?'WALK':'WAIT';
  const remaining=active.movement==='Waiting'?' · '+Math.ceil(active.waitRemaining)+' s':'';
  const text=state+remaining;group.userData.state=state;group.userData.label=text;
  if(text!==lastText){lastText=text;context.clearRect(0,0,380,128);context.fillStyle='#102832';context.strokeStyle=green?'#39ff80':'#ff6472';context.lineWidth=6;context.beginPath();context.roundRect(3,3,374,122,14);context.fill();context.stroke();context.textAlign='center';context.fillStyle='#ffffff';context.font='bold 20px system-ui';context.fillText('YOUR CROSSING',190,29);context.fillStyle=green?'#39ff80':'#ff8790';context.font='bold 42px system-ui';context.fillText(text,190,77);context.fillStyle='#d7e5e8';context.font='18px system-ui';context.fillText('Modelled signal',190,109);texture.needsUpdate=true;}
  selected.forEach((h,i)=>{if(!frames[i]){const frame=new THREE.Sprite(new THREE.SpriteMaterial({map:borderTexture,depthTest:false,depthWrite:false,toneMapped:false}));frame.center.set(.5,0);frame.renderOrder=94;frame.name='health-active-signal-frame';frames[i]=frame;group.add(frame);}frames[i].visible=true;frames[i].material.color.set(green?'#39ff80':'#ff6472');});
 }
 function resize(camera,height){
  if(!group.visible)return;const up=new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld,1);
  selected.forEach((h,i)=>{const u=worldPerPixel(camera,h.position,height),size=Math.max(appearance.head_height_m,options.head_height_px*u);h.scale.set(size*appearance.head_width_m/appearance.head_height_m,size,1);frames[i].position.copy(h.position).addScaledVector(up,-4*u);frames[i].scale.set(h.scale.x+8*u,size+8*u,1);});
  const h=selected[0],u=worldPerPixel(camera,h.position,height),narrow=height*(camera.aspect??1)<=650;
  // The mobile details panel occupies the upper half; put this annotation below
  // the walker there so the signal change remains readable outside the panel.
  label.center.set(.5,narrow?1:0);label.position.copy(h.position).addScaledVector(up,narrow?-(options.label_height_px+32)*u:h.scale.y+8*u);label.scale.set(options.label_width_px*u,options.label_height_px*u,1);
 }
 return {group,update,resize,dispose(){for(const frame of frames)frame.material.dispose();label.material.dispose();texture.dispose();borderTexture.dispose();group.removeFromParent();}};
}
