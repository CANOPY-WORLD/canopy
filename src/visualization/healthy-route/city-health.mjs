// Recorded playback is shared; only explicit loopback sessions can calculate routes.
export async function installCityHealth(viewer,{enter,invalidate,publication=null,resolve}){
 const {installCityRecording}=await import('./city-recording.mjs');
 if(publication){
  return installCityRecording(viewer,{enter,invalidate,compact:true,
   recordingURL:resolve(publication.recording),presentationURL:resolve(publication.presentation)});
 }
 const response=await fetch('/api/health/status');
 if(!response.ok)throw Error('Local Health service unavailable');
 const state=await response.json();
 if(state.mode!=='current-city-recording')throw Error('A pinned current-city recording is required');
 return installCityRecording(viewer,{enter,invalidate,selectRoutes:state.select_routes});
}
