// Opening Health loads recorded results only. Calculate is an explicit local request.
export async function installCityHealth(viewer,{enter,invalidate}){
 const response=await fetch('/api/health/status');
 if(!response.ok)throw Error('Local Health service unavailable');
 const state=await response.json();
 if(state.mode!=='current-city-recording')throw Error('A pinned current-city recording is required');
 const {installCityRecording}=await import('./city-recording.mjs');
 return installCityRecording(viewer,{enter,invalidate,selectRoutes:state.select_routes});
}
