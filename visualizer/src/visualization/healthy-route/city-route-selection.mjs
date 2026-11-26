import * as THREE from 'three';
import {connectedEndpoints} from './walking-endpoints.mjs';
import {createEndpointPin} from './route-presentation.mjs';
import {clockText,departureSeconds} from './health-clock.mjs';

// Local request controls: selecting points never starts computation. The server
// pins the Method, fields and inference policy; the browser selects nodes/time.
export async function installCityRouteSelection(viewer,{panel,invalidate,onPending,onResult,onRestore}){
  const response=await fetch('/api/pedestrian/meta');
  if(!response.ok)throw Error('Walking endpoints could not be loaded');
  const meta=await response.json(),entries=Object.entries(meta.nodes);
  const extended=meta.time_coverage?.mode==='health_replay';
  const coverage=meta.time_coverage?.horizon_s??600;
  const coverageText=extended?`Health coverage: ${((coverage-meta.departure_s)/3600).toFixed(1)} h. Pollution and temperature repeat their source sequences for Health only; sunlight and breathing keep advancing.`:`Health coverage: ${((coverage-meta.departure_s)/60).toFixed(0)} min of native city fields.`;
  const {scene,camera,controls,renderer}=viewer;
  let [origin,goal]=meta.example,active=false,pick=null,busy=false,down=null;
  const clock=meta.departure_clock;
  let departure=meta.departure_s;
  const box=document.createElement('section');box.id='cr-route-selection';
  box.innerHTML=`<p><b>Choose your walk</b></p><div><button id="cr-start">Select START</button> <button id="cr-end">Select END</button> <button id="cr-swap" aria-label="Swap start and end">⇄</button></div><p id="cr-endpoints"></p><p><button id="cr-calculate">Calculate route</button> <button id="cr-restore">Saved preview</button></p><p id="cr-time-coverage">${coverageText}</p><p id="cr-route-status" role="status" aria-live="polite">Select START or END, then click a highlighted walking point on the map.</p><details><summary>Route assumptions</summary><p>Shortest mapped walking distance; ${meta.speed_m_s.toFixed(2)} m/s while moving. ${extended?'Extended scenario inputs, not additional measurements or a forecast.':''} ${meta.crossing_policy==='modelled_with_current_traffic'?'Includes modelled pedestrian waits and newer recorded vehicle-gap estimates where available; short traffic replay and placement assumptions are labelled.':'No signal waits.'} No health optimization or verified safe crossing clearance. A research simulation, not navigation advice.</p></details>`;
  panel.querySelector('header').after(box);
  const $=name=>box.querySelector('#cr-'+name);
  const timeRow=document.createElement('p');
  timeRow.innerHTML='<label for="cr-departure"><b>Start time</b></label> <input id="cr-departure" type="time" step="1" required><br><small id="cr-departure-hint"></small>';
  $('endpoints').after(timeRow);
  if(!clock)throw Error('The local server needs restarting to enable the declared start-time clock.');
  $('departure').min=clockText(clock.origin_seconds);$('departure').max=clockText(clock.origin_seconds+clock.max_departure_s);
  $('departure').value=clockText(clock.origin_seconds+departure);
  $('departure').onchange=()=>{departure=departureSeconds($('departure').value,clock.origin_seconds,clock.max_departure_s);onPending();setPick(null);flags();$('route-status').textContent=departure===null?'Choose a start time within the available Health coverage.':'Start time changed. Click Calculate route to update exposure, breathing and health scores.';};
  const style=document.createElement('style');style.textContent='#cr-route-selection{border-bottom:1px solid #6b948d;padding-bottom:10px;margin-bottom:10px}#cr-route-selection button{margin:2px 0}#cr-route-selection button[aria-pressed="true"]{background:#46776c;outline:2px solid #9ef5d1}#cr-route-selection button:disabled{opacity:.5}#cr-endpoints,#cr-route-status,#cr-time-coverage{font-size:12px}';document.head.append(style);
  const overlay=new THREE.Group();overlay.name='current-city-walking-selection';overlay.visible=false;scene.add(overlay);
  const positions=[];for(const road of meta.roads)for(let i=1;i<road.length;i++)for(const p of [road[i-1],road[i]])positions.push(p[0],p[2]+.3,-p[1]);
  const paths=new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position',new THREE.Float32BufferAttribute(positions,3)),new THREE.LineBasicMaterial({color:'#77dbc8',transparent:true,opacity:.8}));overlay.add(paths);
  const nodeColors=new Float32Array(entries.length*3),reachable=new THREE.Color('#a4f4df'),unavailable=new THREE.Color('#64706d');
  const nodes=new THREE.Points(new THREE.BufferGeometry().setFromPoints(entries.map(([,p])=>new THREE.Vector3(p[0],p[2]+.6,-p[1]))).setAttribute('color',new THREE.Float32BufferAttribute(nodeColors,3)),new THREE.PointsMaterial({vertexColors:true,size:5,sizeAttenuation:false,depthTest:false}));overlay.add(nodes);
  nodes.name='walking-endpoint-availability';
  const markers=new THREE.Group();markers.name='current-city-selected-endpoints';markers.visible=false;scene.add(markers);
  const pins=[createEndpointPin('START','#5ef1b1'),createEndpointPin('END','#d296ff')];
  const [start,finish]=pins.map(p=>p.object);markers.add(start,finish);
  const resizePins=()=>{camera.updateMatrixWorld();for(const pin of pins)pin.update(camera,renderer.domElement.clientHeight);invalidate();};
  controls.addEventListener('change',resizePins);window.addEventListener('resize',resizePins);
  const connected=()=>origin!==goal&&connectedEndpoints(meta.node_components,origin,goal);
  function flags(){for(const [marker,id] of [[start,origin],[finish,goal]]){const p=meta.nodes[id];marker.position.set(p[0],p[2]+2,-p[1]);}
    const label=id=>{const p=meta.nodes[id];return `${p[0].toFixed(1)} E, ${p[1].toFixed(1)} N`;};
    $('endpoints').textContent=`Mint START: ${label(origin)} → Purple END: ${label(goal)}`;
    $('endpoints').dataset.origin=origin;$('endpoints').dataset.goal=goal;
    for(const key of ['start','end','swap','restore','departure'])$(key).disabled=busy;
    $('departure-hint').textContent=`Scenario clock, not live time. Arrive by ${clockText(clock.origin_seconds+coverage)}; ${departure===null?'invalid start time':((coverage-departure)/60).toFixed(0)+' min remaining'}. Sunlight and breathing advance; pollution/temperature use the labelled Health replay.`;
    $('calculate').disabled=busy||!connected()||departure===null;$('calculate').textContent=busy?'Calculating…':'Calculate route';resizePins();}
  function setPick(value){pick=value;overlay.visible=active&&Boolean(pick);renderer.domElement.style.cursor=pick?'crosshair':'';
    const colors=nodes.geometry.getAttribute('color');for(let i=0;i<entries.length;i++){const valid=pick!=='end'||connectedEndpoints(meta.node_components,origin,entries[i][0]);const c=valid?reachable:unavailable;colors.setXYZ(i,c.r,c.g,c.b);}colors.needsUpdate=true;
    for(const key of ['start','end'])$(key).setAttribute('aria-pressed',String(pick===key));invalidate();}
  for(const key of ['start','end'])$(key).onclick=()=>{setPick(pick===key?null:key);$('route-status').textContent=pick?`Click a mint walking point for ${key==='start'?'START':'END'}. ${key==='end'?'Grey points have no mapped connection to START. ':''}Drag to move the map, or press Escape to cancel.`:'Selection cancelled.';};
  $('swap').onclick=()=>{[origin,goal]=[goal,origin];onPending();setPick(null);flags();$('route-status').textContent='Endpoints swapped. Click Calculate route.';};
  $('restore').onclick=()=>{[origin,goal]=meta.example;departure=meta.departure_s;$('departure').value=clockText(clock.origin_seconds+departure);setPick(null);flags();onRestore();$('route-status').textContent='Saved preview restored. Choose endpoints to calculate a different walk.';};
  function selectAt(event){
    if(!active||!pick||busy||!down||Math.hypot(event.clientX-down.x,event.clientY-down.y)>5)return;
    event.preventDefault();event.stopImmediatePropagation();
    const rect=renderer.domElement.getBoundingClientRect(),v=new THREE.Vector3();
    let best=null,distance=20,depth=Infinity;
    // Pick the actual native-height point shown in the shared camera. This also
    // respects elevated paths instead of projecting every click onto flat Z=0.
    camera.updateMatrixWorld();
    for(const [id,p] of entries){v.set(p[0],p[2]+.6,-p[1]).project(camera);if(v.z< -1||v.z>1)continue;
      const d=Math.hypot(rect.left+(v.x+1)*rect.width/2-event.clientX,rect.top+(1-v.y)*rect.height/2-event.clientY);
      if(d<distance||(d===distance&&v.z<depth)){best=id;distance=d;depth=v.z;}}
    if(!best){$('route-status').textContent='Click closer to a highlighted walking point. Zoom in if needed.';return;}
    if((pick==='end'&&best===origin)||(pick==='start'&&best===goal)){$('route-status').textContent='START and END must be different.';return;}
    if(pick==='end'&&!connectedEndpoints(meta.node_components,origin,best)){$('route-status').textContent='That path has no mapped connection to START. Choose another END or change START.';return;}
    if(pick==='start')origin=best;else goal=best;
    onPending();setPick(connected()?null:'end');flags();
    $('route-status').textContent=connected()?'Endpoint selected. Click Calculate route to generate its breathing and health scores.':'START selected. Choose END on the same connected walking network.';
  }
  renderer.domElement.addEventListener('pointerdown',e=>{down={x:e.clientX,y:e.clientY};});
  renderer.domElement.addEventListener('click',selectAt,true);
  document.addEventListener('keydown',e=>{if(active&&e.key==='Escape')setPick(null);});
  $('calculate').onclick=async()=>{
    if(busy||!connected()||departure===null)return;busy=true;setPick(null);onPending();flags();
    $('route-status').textContent='Calculating the walk and conditional physiology on this computer…';
    try{const response=await fetch('/api/health/walk',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({origin,goal,departure_s:departure})});
      const data=await response.json();if(!response.ok)throw Error(data.error||`Calculation failed (${response.status})`);
      onResult(data);$('route-status').textContent=`Ready: ${data.route_selection.distance_m.toFixed(0)} m · ${(data.route_duration_s/60).toFixed(1)} min${data.crossing_summary?' · '+data.crossing_summary.wait_s.toFixed(1)+' s crossing waits':''}. Use the bottom controls to play your walk.`;
    }catch(error){$('route-status').textContent=error.message+'. Choose different endpoints and retry, or restore the saved preview.';}
    finally{busy=false;flags();}
  };
  flags();
  return {clockOrigin:clock.origin_seconds,setActive(on){active=on;markers.visible=on;if(!on)setPick(null);resizePins();}};
}
