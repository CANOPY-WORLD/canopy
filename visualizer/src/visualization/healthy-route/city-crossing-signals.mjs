import * as THREE from 'three';
import {createWalkSignals} from './pedestrian-walk-signals.mjs';
import {createActiveCrossingCue} from './active-crossing-cue.mjs';
// Reuse the shared city's recorded vehicle-signal renderer and state reader.
import {createTrafficFacilities} from '../../../viewer/3d/traffic-facilities.js';

export function createCityCrossingSignals(recording,appearance={head_width_m:.3,head_height_m:.6,head_bottom_m:2.1,pole_diameter_m:.06}){
 for(const key of ['head_width_m','head_height_m','head_bottom_m','pole_diameter_m'])if(!Number.isFinite(appearance[key])||appearance[key]<=0)throw Error('Invalid pedestrian signal dimension: '+key);
 const crossings=recording.crossing_signals??[],group=new THREE.Group();group.name='health-crossing-signals';
 const offset=appearance.roadside_offset_m??0,setback=appearance.roadside_setback_m??0;
 if(!Number.isFinite(offset)||offset<0||!Number.isFinite(setback)||setback<0)throw Error('Invalid pedestrian roadside offset');
 // Presentation-only offset beside the mapped crossing, never a new route point.
 // Canonical orientation keeps placement independent of the walking direction.
 const data={pedestrian_programs:crossings,signals:crossings.flatMap(c=>{
  if(!c.heads.length)return [];
  const a=c.heads[0],b=c.heads.at(-1),routeDx=b[0]-a[0],routeDy=b[1]-a[1];let dx=routeDx,dy=routeDy;
  if(dx<0||(dx===0&&dy<0)){dx=-dx;dy=-dy;}
  const length=Math.hypot(dx,dy),east=length?-dy/length*offset:0,north=length?dx/length*offset:0;
  return c.heads.map((p,i)=>{const along=length?(i===0?-setback:setback)/length:0;return {id:c.id+':'+i,crossing_id:c.id,source_head:[...p],head:[p[0]+east+routeDx*along,p[1]+north+routeDy*along,p[2]]};});
 })};
 const pedestrian=createWalkSignals(data,{roundLamps:appearance.round_lamps===true});group.add(pedestrian.group);
 const byId=new Map(crossings.map(c=>[c.id,c]));
 // Apply the same whole-crossing admission margin even where vehicle coverage
 // is unavailable; an empty display window does not claim vehicle clearance.
 pedestrian.setTrafficGaps(Object.fromEntries(crossings.map(c=>[c.id,c.traffic_gap??{
  period_s:c.program.red_s+c.program.green_s+c.program.clearance_s,
  blocked_intervals_s:[],crossing_s:c.crossing_s,clearance_s:2}])));
 const poleHeight=appearance.head_bottom_m+appearance.head_height_m/2;
 const poleGeometry=new THREE.CylinderGeometry(appearance.pole_diameter_m/2,appearance.pole_diameter_m/2,poleHeight,8);
 const poleMaterial=new THREE.MeshStandardMaterial({color:0x333a3e,roughness:.8});
 for(let i=0;i<pedestrian.heads.length;i++){const h=pedestrian.heads[i],p=data.signals[i].head;h.position.set(p[0],p[2]+appearance.head_bottom_m,-p[1]);h.center.set(.5,0);h.scale.set(appearance.head_width_m,appearance.head_height_m,1);h.material.depthTest=true;h.renderOrder=0;h.material.toneMapped=false;h.material.map.colorSpace=THREE.SRGBColorSpace;h.userData.assumption='Modelled pedestrian gate, not recorded pedestrian signals; illustrative metre-scale housing';h.userData.trafficCovered=byId.get(h.userData.crossingId).traffic_covered;
  h.userData.sourceHeadENU=data.signals[i].source_head;h.userData.roadsideHeadENU=[...p];
  const pole=new THREE.Mesh(poleGeometry,poleMaterial);pole.name='pedestrian-signal-pole';pole.userData.signalId=data.signals[i].id;pole.position.set(p[0],p[2]+poleHeight/2,-p[1]);group.add(pole);
 }
 const nativeData=recording.native_vehicle_signals;
 const native=nativeData?.heads?.length?createTrafficFacilities({signals:nativeData,crossings:[]}):null;
 if(native)group.add(native.group);
 const clock=recording.crossing_summary?.traffic_clock;
 const cue=createActiveCrossingCue(pedestrian.heads,appearance);group.add(cue.group);
 return {group,pedestrian,update(time,active=null){const state=pedestrian.update(time);cue.update(active);if(native)native.setTime(clock.source_interval_s[0]+((time%clock.period_s)+clock.period_s)%clock.period_s);return state;},
  // Ordinary heads retain scene metres; only the current crossing gets a cue.
  resize(camera,height){cue.resize(camera,height);},
  dispose(){cue.dispose();pedestrian.dispose();poleGeometry.dispose();poleMaterial.dispose();native?.dispose();group.removeFromParent();}};
}
