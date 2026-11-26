// Recorded coordinates are prepared upstream. The Viewer never guesses a datum.
export function boundedPlaybackTime(t,start,end){
  // HTML range values may serialize fewer digits than a recorded fractional end.
  const tolerance=64*Number.EPSILON*Math.max(1,Math.abs(start),Math.abs(end));
  if(Math.abs(t-end)<=tolerance)return end;
  if(Math.abs(t-start)<=tolerance)return start;
  return Math.max(start,Math.min(end,t));
}
export function sampleRecording(rows,t){
  if(!rows.length||!Number.isFinite(t)||t<rows[0].world_seconds||t>rows.at(-1).world_seconds)return null;
  let hi=rows.findIndex(r=>r.world_seconds>=t);const b=rows[hi];
  if(b.world_seconds===t)return b;
  const a=rows[hi-1],f=(t-a.world_seconds)/(b.world_seconds-a.world_seconds);
  const out={world_seconds:t,seconds:a.seconds+(b.seconds-a.seconds)*f};
  for(const k of ['pmx','temperature','sunlight'])out[k]=Number.isFinite(a[k])&&Number.isFinite(b[k])?a[k]+(b[k]-a[k])*f:null;
  // Physiology is recorded at discrete model boundaries; never anticipate the
  // next prediction or recompute physical scores at the Viewer boundary.
  for(const k of ['pollution_proxy','temperature_estimate','sunlight_estimate','thermal_proxy','breathing','latent_sd','health_score','model_updates','breathing_reference','contributions','input_estimates','phase','movement_state','crossing_id','wait_remaining_s'])out[k]=a[k]??null;
  for(const k of ['scene_m','enu_m'])out[k]=!b.gap_before&&a[k]?.every(Number.isFinite)&&b[k]?.every(Number.isFinite)?a[k].map((v,i)=>v+(b[k][i]-v)*f):null;
  return out;
}
export function chartPath(rows,key,width,height,step=false){
  const valid=rows.filter(r=>Number.isFinite(r[key]));if(!valid.length)return '';
  const low=Math.min(...valid.map(r=>r[key])),high=Math.max(...valid.map(r=>r[key]));
  const start=rows[0].seconds,end=rows.at(-1).seconds;let path='',pen=false;
  for(const r of rows){if(!Number.isFinite(r[key])||r.gap_before){pen=false;if(!Number.isFinite(r[key]))continue;}
    const x=(r.seconds-start)/Math.max(end-start,1e-9)*width,y=height-(r[key]-low)/Math.max(high-low,1)*height;
    path+=pen&&step?'H'+x.toFixed(3)+'V'+y.toFixed(3):(pen?'L':'M')+x.toFixed(3)+','+y.toFixed(3);pen=true;
  }return path;
}
