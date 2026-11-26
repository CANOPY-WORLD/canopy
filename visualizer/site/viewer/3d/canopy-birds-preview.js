import {createBirdLayer} from '../../agents/auspex/birds.js'; // Auspex bird model, animation and feather shading
export async function installBirdPreview(viewer,invalidate) {
 const panel=document.createElement('section');
 panel.style.cssText='position:fixed;z-index:1000;left:18px;top:180px;width:310px;padding:18px;background:#102832ed;color:white;border:1px solid #7ba99c;border-radius:14px;font:13px system-ui;box-shadow:0 8px 30px #0006';
 panel.innerHTML='<b>CANOPY · Bird simulation</b><p data-status>Loading local simulation results…</p>';
 (document.getElementById('viewer-details') ?? document.body).append(panel);
 try {
 const base=new URL('../../assets/birds/',import.meta.url).href;
 const fetchOK=async p=>{const r=await fetch(base+p);if(!r.ok)throw Error(`${p}: HTTP ${r.status}`);return r;};
 const manifest=await (await fetchOK('bird_replay.json')).json();
 const [raw,st]=await Promise.all([manifest.display_float32_file??'bird_replay.i16','bird_states.u8'].map(async p=>{
  const response=await fetchOK(p+'.gz');
  return new Response(response.body.pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
 }));
 const count=manifest.frames*manifest.birds*6,e=manifest.encoding;
 if(raw.byteLength!==count*(manifest.display_float32_file?4:2)||st.byteLength!==manifest.frames*manifest.birds)throw Error('Replay size mismatch');
 const buffer=manifest.display_float32_file?new Float32Array(raw):new Float32Array(count);
 if(!manifest.display_float32_file){const q=new Int16Array(raw);for(let k=0;k<q.length;k+=6){for(let j=0;j<3;j++)buffer[k+j]=q[k+j]*e.position_scale_m+e.offset_m[j];buffer[k+3]=q[k+3]*e.angle_scale_rad;buffer[k+4]=q[k+4]*e.speed_scale_mps;buffer[k+5]=q[k+5]*e.angle_scale_rad;}}
 const affect=manifest.affect_file?new Uint8Array(await new Response((await fetchOK(manifest.affect_file+'.gz')).body.pipeThrough(new DecompressionStream('gzip'))).arrayBuffer()):null;
 const layer=await createBirdLayer({scene:viewer.scene,manifest,buffer,states:new Uint8Array(st),affect});
 layer.setMarkers(false);
 if(layer.stats.placeholder_model){layer.setVisible(false);throw Error(layer.stats.model_error);}
 panel.innerHTML=`<b>CANOPY · Bird simulation</b><p>${manifest.birds.toLocaleString()} birds · ${manifest.flocks.length} flocks<br>${manifest.frames.toLocaleString()} recorded frames</p><div style="display:flex;gap:8px"><button data-play>Play</button><select data-rate aria-label="Bird playback speed"><option value="1" selected>1×</option><option value="10">10×</option><option value="30">30×</option><option value="60">60×</option></select><select data-flock aria-label="Focus flock">${manifest.flocks.map((f,i)=>`<option value="${i}">Flock ${i+1}</option>`).join('')}</select><button data-focus>Locate</button></div><select data-moment aria-label="Bird activity" style="width:100%;margin-top:12px"></select><input data-time aria-label="Bird simulation time" type="range" min="0" max="${manifest.last_frame_t_s}" step="1.5" style="width:100%;margin-top:14px"><div data-clock></div><p style="font-size:11px;opacity:.85">Experimental flock behaviour on CANOPY terrain. Not species-calibrated. Column-based collision model.</p><label><input type="checkbox" data-visible checked> Show birds</label> <label><input type="checkbox" data-markers> Markers</label>`;
 const el=name=>panel.querySelector(`[data-${name}]`);
 let active=true;
 let t=0,playing=false,old=performance.now(),frame=0;
 function seek(value){t=Math.min(manifest.last_frame_t_s,Math.max(0,Number(value)));const s=layer.update(t);frame=s.frame;el('time').value=t;el('clock').textContent=`Simulation ${t.toFixed(1)} / ${manifest.last_frame_t_s.toFixed(0)} s · Frame ${frame+1}`;invalidate();}
 // CAMERA: follow one bird closely; every FOLLOW_S seconds move on to a bird of the next flock (wall clock, not replay time)
 const FOLLOW_S=20, FOLLOW_BACK=6, FOLLOW_UP=2.5, statesAll=new Uint8Array(st);
 let follow=-1, followSince=0, lastTarget=null;
 function pickBird(flockIndex){
  const f=manifest.flocks[flockIndex],all=Array.from({length:f.birds},(_,i)=>f.first_bird+i);
  const flying=all.filter(i=>[1,2,3].includes(statesAll[frame*manifest.birds+i]));
  const pool=flying.length?flying:all;
  return pool[Math.floor(pool.length/2)];
 }
 function aboveGround(){ // keep the follow camera above the draped terrain (it can sink into slopes behind a foraging bird)
  const c=viewer.camera.position,terrain=window.corridorTerrain;
  if(terrain?.enabled)c.y=Math.max(c.y,terrain.sample(c.x,c.z)+3);
 }
 function focus(){
  el('flock').value=el('flock').value||'0';
  follow=pickBird(Number(el('flock').value));followSince=performance.now();lastTarget=null;
  layer.update(t);const b=layer.getState(follow);if(!b)return;
  const damping=viewer.controls.enableDamping;viewer.controls.enableDamping=false;
  viewer.controls.target.set(b.x,b.y,b.z);
  viewer.camera.position.set(b.x-Math.sin(b.headingRadians)*FOLLOW_BACK,b.y+FOLLOW_UP,b.z-Math.cos(b.headingRadians)*FOLLOW_BACK);
  aboveGround();viewer.controls.update();viewer.controls.enableDamping=damping;lastTarget=viewer.controls.target.clone();invalidate();
 }
 function followTick(now){
  if(follow<0||!active)return;
  if(now-followSince>FOLLOW_S*1000){el('flock').value=String((Number(el('flock').value)+1)%manifest.flocks.length);moments();focus();return;}
  const b=layer.getState(follow);if(!b||!lastTarget)return;
  const dx=b.x-lastTarget.x,dy=b.y-lastTarget.y,dz=b.z-lastTarget.z;   // carry the camera with the bird, keeping the user's orbit
  viewer.controls.target.set(b.x,b.y,b.z);viewer.camera.position.x+=dx;viewer.camera.position.y+=dy;viewer.camera.position.z+=dz;
  aboveGround();lastTarget.set(b.x,b.y,b.z);viewer.controls.update();
 }
 function moments(){const f=manifest.flocks[Number(el('flock').value)];el('moment').innerHTML='<option value="">Jump to recorded activity…</option>'+f.moments.map(m=>`<option value="${m.mid_s}">${m.label}</option>`).join('');}
 el('flock').onchange=()=>{moments();focus();};el('moment').onchange=()=>{if(el('moment').value!==''){seek(el('moment').value);focus();}};
 el('play').onclick=()=>{playing=!playing;el('play').textContent=playing?'Pause':'Play';};
 el('time').oninput=()=>seek(el('time').value);el('focus').onclick=focus;
 el('visible').onchange=()=>{layer.setVisible(el('visible').checked);invalidate();};el('markers').onchange=()=>{layer.setMarkers(el('markers').checked);invalidate();};
 function tick(now){layer.setVisible(active && el('visible').checked && window.corridorTerrain?.enabled!==false);const dt=Math.min(.1,(now-old)/1000);old=now;if(active&&playing&&!document.hidden)seek((t+dt*Number(el('rate').value))%manifest.last_frame_t_s);else if(layer.group.visible){layer.update(t);invalidate();}if(layer.group.visible){followTick(now);invalidate();}requestAnimationFrame(tick);}requestAnimationFrame(tick);
 window.canopyBirds={manifest,layer,seek,focus,setActive(v){active=v;if(!v)follow=-1;panel.hidden=!v;layer.setVisible(v&&el('visible').checked);invalidate();},toggle(){el('play').click();},setRate(v){el('rate').value=v;},get rate(){return Number(el('rate').value)},get time(){return t},get playing(){return playing}};
 moments();const moment=manifest.flocks[0].moments.find(m=>m.label==='Murmuration') ?? manifest.flocks[0].moments.find(m=>m.label==='Leaving the roost');seek(moment?.mid_s??0);return window.canopyBirds;
 }catch(err){panel.querySelector('[data-status]')?.replaceChildren(document.createTextNode('Bird replay failed: '+err.message));console.error(err);}
}
