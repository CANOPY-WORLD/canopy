import * as THREE from 'three';
import {LineSegments2} from 'three/addons/lines/LineSegments2.js';
import {LineSegmentsGeometry} from 'three/addons/lines/LineSegmentsGeometry.js';
import {LineMaterial} from 'three/addons/lines/LineMaterial.js';

// Widths and marker sizes are presentation cues, not road/person dimensions.
export function createRouteStroke(){
  const group=new THREE.Group();group.name='health-highlighted-route';
  const lines=[[10,'#102832',70],[6,'#ff729c',71]].map(([width,color,order])=>{
    const line=new LineSegments2(new LineSegmentsGeometry(),new LineMaterial({color,linewidth:width,depthTest:false,depthWrite:false,toneMapped:false}));
    line.renderOrder=order;line.frustumCulled=false;group.add(line);return line;
  });
  return {group,setRows(rows,lift){const positions=[];
    for(let i=1;i<rows.length;i++){const a=rows[i-1],b=rows[i];if(!b.gap_before&&a.scene_m?.every(Number.isFinite)&&b.scene_m?.every(Number.isFinite)&&a.scene_m.some((v,k)=>v!==b.scene_m[k]))for(const p of [a.scene_m,b.scene_m])positions.push(p[0],p[1]+lift,p[2]);}
    for(const line of lines){line.geometry.dispose();line.geometry=new LineSegmentsGeometry();if(positions.length)line.geometry.setPositions(positions);line.visible=positions.length>0;}
  }};
}
export function worldPerPixel(camera,position,height){
  if(camera.isOrthographicCamera)return (camera.top-camera.bottom)/camera.zoom/Math.max(height,1);
  const depth=-position.clone().applyMatrix4(camera.matrixWorldInverse).z;
  return 2*Math.max(depth,.1)*Math.tan(camera.fov*Math.PI/360)/camera.zoom/Math.max(height,1);
}
export function createEndpointPin(text,color){
  const canvas=document.createElement('canvas');canvas.width=320;canvas.height=160;const c=canvas.getContext('2d');
  const isStart=text==='START',left=isStart?4:68,anchor=isStart?320:0,stem=isStart?240:80;
  c.fillStyle='#102832';c.strokeStyle=color;c.lineWidth=8;c.beginPath();c.roundRect(left,4,248,96,22);c.fill();c.stroke();
  c.fillStyle=color;c.beginPath();c.moveTo(stem-8,102);c.lineTo(stem+8,102);c.lineTo(anchor,160);c.closePath();c.fill();
  c.font='bold 48px system-ui';c.fillStyle='white';c.textAlign='center';c.textBaseline='middle';c.fillText(text,left+124,53);
  const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
  const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,depthTest:false,depthWrite:false,toneMapped:false}));
  sprite.name='health-endpoint-'+text.toLowerCase();sprite.center.set(anchor/320,0);sprite.renderOrder=110;
  return {object:sprite,update(camera,height){const unit=worldPerPixel(camera,sprite.position,height);sprite.scale.set(110*unit,55*unit,1);}};
}
export function followWalker(camera,controls,position,frame=false){
  const target=position.clone();target.y+=2;
  if(frame)camera.position.copy(target).add(new THREE.Vector3(65,95,85));
  else camera.position.add(target.clone().sub(controls.target));
  controls.target.copy(target);controls.update();
}
