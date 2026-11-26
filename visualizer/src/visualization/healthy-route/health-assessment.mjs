import {sampleRecording} from './recorded-health-state.mjs';

// A read-only summary of the recorded evaluation, never a new health calculation.
export function createHealthAssessment() {
  const host=document.createElement('section');
  host.id='health-assessment';host.hidden=true;
  host.setAttribute('aria-label','Recorded health assessment');
  host.innerHTML=`<h3>Route health assessment</h3><div class="health-metrics">
    <div><span>Experimental score</span><strong data-score>—</strong><small>/ 100</small></div>
    <div><span>Predicted breathing</span><strong data-breathing>—</strong><small>breaths/min</small></div>
    <div><span>PM2.5 proxy</span><strong data-pollution>—</strong><small>µg/m³ · estimated</small></div>
    </div><div class="health-trend-label"><span>Score over this walk · 0–100</span><span data-time></span></div>
    <svg viewBox="0 0 260 48" role="img" aria-label="Recorded health score over the route, from 0 to 100"><path data-trend fill="none" stroke="#80e6c1" stroke-width="2"/><line data-cursor y1="0" y2="48" stroke="#f7eee0" stroke-width="1"/></svg>
    <p data-contributions></p><p class="health-qualification">Saved model estimates; heuristic score. Evaluates this route, not health-optimized routing.</p><p data-input-kind class="health-qualification"></p>`;
  const el=name=>host.querySelector('[data-'+name+']');
  let previous=null,previousEnd=null;
  const text=(name,value)=>{if(el(name).textContent!==value)el(name).textContent=value;};
  const number=v=>Number.isFinite(v)?v.toFixed(1):'Unavailable';
  return {host,update(health){
    const result=health?.result;
    if(!result?.samples?.length)return;
    const start=health.start,end=health.end,duration=end-start;
    if(previous!==result||previousEnd!==end){
      previous=result;previousEnd=end;let d='',pen=false;
      for(const r of result.samples){
        if(r.world_seconds<start||r.world_seconds>end)continue;
        if(!Number.isFinite(r.health_score)){pen=false;continue;}
        if(r.gap_before)pen=false;
        const x=(r.world_seconds-start)/Math.max(duration,1e-9)*260;
        const y=48-r.health_score/100*48;
        d+=pen?`H${x.toFixed(3)}V${y.toFixed(3)}`:`M${x.toFixed(3)},${y.toFixed(3)}`;pen=true;
      }
      el('trend').setAttribute('d',d);
      text('input-kind',result.physiology_input_kind==='synthetic'?'Synthetic physiology inputs · not a personal health assessment.':'Recorded physiology inputs · not a clinical assessment.');
    }
    const s=sampleRecording(result.samples,health.time);
    text('score',number(s?.health_score));text('breathing',number(s?.breathing));text('pollution',number(s?.pollution_proxy));
    const c=s?.contributions;
    text('contributions',c?`Score deductions · pollution ${number(c.pollution)} · thermal ${number(c.temperature)} · breathing ${number(c.breathing)}`:'Score contributions unavailable.');
    text('time',`${Math.max(0,health.time-start).toFixed(0)} / ${duration.toFixed(0)} s`);
    const x=Math.max(0,Math.min(1,(health.time-start)/Math.max(duration,1e-9)))*260;
    el('cursor').setAttribute('x1',x);el('cursor').setAttribute('x2',x);
  }};
}
