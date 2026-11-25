// Read saved events on their exact scenario clock; never predict a release.
export function activeCrossingAt(recording,time){
 const departure=recording.departure_s??0;
 const event=(recording.route_timeline??[]).find(e=>departure+e.start<=time&&time<departure+e.end);
 if(!event?.crossing_id||!['Waiting','Crossing'].includes(event.kind))return null;
 return {crossingId:event.crossing_id,movement:event.kind,
  waitRemaining:event.kind==='Waiting'?Math.max(0,departure+event.end-time):0};
}
