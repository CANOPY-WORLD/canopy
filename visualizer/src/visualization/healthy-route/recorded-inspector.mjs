import * as THREE from 'three';
import {assetURL,enuToWorld} from '../shared/time.mjs';

export function validateRecording(data){
  if(data?.format!=='canopy.health-recording.v1'||!Array.isArray(data.samples)||!data.samples.length)throw Error('Unsupported health recording');
  let previous=-Infinity;
  for(const row of data.samples){
    if(!Number.isFinite(row.seconds)||row.seconds<=previous||!Array.isArray(row.position)||row.position.length!==3||!row.position.every(Number.isFinite))throw Error('Invalid recorded health trajectory');
    for(const key of ['pollution','temperature','sunlight','thermal_proxy','breathing','distance','wait'])if(row[key]!==null&&!Number.isFinite(row[key]))throw Error('Invalid recorded metric');
    if(row.health!==null&&(!Number.isFinite(row.health?.score)||!['pollution','temperature','breathing'].every(k=>Number.isFinite(row.health?.contributions?.[k]))))throw Error('Invalid recorded score');
    previous=row.seconds;
  }
  return data;
}
export function recordingAt(data,t){
  if(t<data.samples[0].seconds||t>data.samples.at(-1).seconds)return null;
  let lo=0,hi=data.samples.length;
  while(lo+1<hi){const mid=(lo+hi)>>1;if(data.samples[mid].seconds<=t)lo=mid;else hi=mid;}
  return data.samples[lo];
}
export async function loadRecordedInspector({run,host,scene,camera,controls,signal,invalidate}){
  const artifact=run.manifest.artifacts?.find(a=>a.id==='health_recording');if(!artifact)return null;
  const response=await fetch(assetURL(run.url,artifact.asset),{signal});if(!response.ok)throw Error('Recorded health inspection unavailable');
  const bytes=await response.arrayBuffer();
  const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
  if(hash!==artifact.sha256)throw Error('Health recording checksum mismatch');
  const data=validateRecording(JSON.parse(new TextDecoder().decode(bytes)));
  const section=document.createElement('section');section.id='health-inspection';
  const heading=document.createElement('h2');heading.textContent='Recorded health journey';section.append(heading);
  const note=document.createElement('p');note.textContent='Experimental personal replay · not clinical advice or a validated city placement.';section.append(note);
  const assumptions=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Clock and model assumptions';assumptions.append(summary);section.append(assumptions);
  for(const text of [data.limits,data.clock,data.sampling]){const p=document.createElement('p');p.textContent=text;assumptions.append(p);}
  const follow=document.createElement('button');follow.textContent='Follow walker';follow.setAttribute('aria-pressed','false');section.append(follow);
  const visible=document.createElement('button');visible.textContent='Hide route';section.append(visible);
  const status=document.createElement('p');status.id='health-status';section.append(status);
  const values=document.createElement('dl');section.append(values);host.prepend(section);
  const group=new THREE.Group();scene.add(group);
  const geometry=new THREE.BufferGeometry().setFromPoints(data.samples.map(r=>new THREE.Vector3(...enuToWorld(r.position))));
  const line=new THREE.Line(geometry,new THREE.LineBasicMaterial({color:0xff66af}));group.add(line);
  const person=new THREE.Mesh(new THREE.CapsuleGeometry(.35,1.1,4,8),new THREE.MeshStandardMaterial({color:0xffbd62}));group.add(person);
  let following=false,last=null;follow.onclick=()=>{following=!following;follow.setAttribute('aria-pressed',String(following));last=null;invalidate();};
  visible.onclick=()=>{group.visible=!group.visible;visible.textContent=group.visible?'Hide route':'Show route';invalidate();};
  const metrics=[['pollution','Tracer-derived PM2.5','µg/m³'],['temperature','Air temperature','°C'],['sunlight','Sunlight','W/m²'],['thermal_proxy','Heuristic thermal proxy','°C'],['breathing','Predicted breathing','breaths/min'],['distance','Distance','m'],['wait','Crossing wait','s']];
  const displays=new Map();for(const [key,label,unit] of [...metrics,['score','Experimental health score','/100'],['pollution_points','Pollution deduction','points'],['temperature_points','Thermal deduction','points'],['breathing_points','Breathing deduction','points']]){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.dataset.metric=key;values.append(dt,dd);displays.set(key,{dd,unit});}
  const reference=document.createElement('p');section.append(reference);
  const plots=document.createElement('details'),plotSummary=document.createElement('summary');plotSummary.textContent='Recorded journey plots';plots.append(plotSummary);section.append(plots);
  // Recorded-only plots: gaps start a new path; no interpolation or replacement by zero.
  for(const [key,label,unit] of metrics){const canvas=document.createElement('canvas');canvas.width=520;canvas.height=130;canvas.style.maxWidth='100%';canvas.dataset.healthPlot=key;plots.append(canvas);const ctx=canvas.getContext('2d');let low=Infinity,high=-Infinity;for(const row of data.samples)if(Number.isFinite(row[key])){low=Math.min(low,row[key]);high=Math.max(high,row[key]);}ctx.fillStyle='#e2e8f0';ctx.font='13px sans-serif';ctx.fillText(`${label} (${unit})`,8,18);ctx.strokeStyle='#ff66af';ctx.beginPath();let drawing=false;for(const row of data.samples){if(!Number.isFinite(row[key])){drawing=false;continue;}const x=8+504*(row.seconds-data.samples[0].seconds)/(data.samples.at(-1).seconds-data.samples[0].seconds||1),y=108-70*(row[key]-low)/(high-low||1);if(drawing)ctx.lineTo(x,y);else ctx.moveTo(x,y);drawing=true;}ctx.stroke();}
  return {get state(){return {visible:group.visible,available:person.visible,following,position:person.position.toArray(),camera:camera.position.toArray()};},setTime(t){const row=recordingAt(data,t);person.visible=Boolean(row);status.textContent=row?`${row.status} · ${(t/60).toFixed(2)} min · ${data.travel_mode}`:'Recorded values unavailable';
    for(const [key,{dd,unit}] of displays){const value=key==='score'?row?.health?.score:key.endsWith('_points')?row?.health?.contributions?.[key.replace('_points','')]:row?.[key];dd.textContent=Number.isFinite(value)?`${value.toFixed(2)} ${unit}`:'Unavailable';}
    reference.textContent=row?.reference?`Personal recorded reference: ${row.reference.lower.toFixed(2)}–${row.reference.upper.toFixed(2)} breaths/min; not a clinical normal range.`:'Personal reference unavailable';
    if(row){const p=new THREE.Vector3(...enuToWorld(row.position));person.position.copy(p);person.position.y+=.9;if(following){if(last)camera.position.add(p.clone().sub(last));else camera.position.copy(p).add(new THREE.Vector3(12,10,12));controls.target.copy(p);controls.update();}last=p;}
  },dispose(){geometry.dispose();line.material.dispose();person.geometry.dispose();person.material.dispose();group.removeFromParent();section.remove();}};
}
