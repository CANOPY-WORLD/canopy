// Display-only contact with the DEM; source lane elevations remain unchanged.
export function roadContactPolicy(network) {
 const excludedEdges=new Set(),excludedJunctions=new Set();
 network.edges.forEach((edge,i)=>{
  if(Number(edge.level)>0 || (edge.structure||[]).some(tag=>['bridge','tunnel','covered'].includes(tag))){
   excludedEdges.add(i);excludedJunctions.add(edge.from);excludedJunctions.add(edge.to);
  }
 });
 return {
  junction:junction=>!excludedJunctions.has(junction.id),
  lane:lane=>lane.edge!=null ? !excludedEdges.has(lane.edge) :
   !!network.junctions[lane.junction]&&!excludedJunctions.has(network.junctions[lane.junction].id)
 };
}

export function contactTriangles(a,b,sample,displayOffset) {
 // The shader adds displayOffset to every vertex, including the seam foot.
 const foot=p=>[p[0],p[1],sample(p[0],p[1])-displayOffset];
 const af=foot(a),bf=foot(b);
 if(Math.max(Math.abs(af[2]-a[2]),Math.abs(bf[2]-b[2]))<.01)return [];
 // Split at a cut/fill transition to avoid a self-intersecting quad.
 const da=af[2]-a[2],db=bf[2]-b[2];
 if(da*db<0){
  const t=da/(da-db),mid=a.map((v,i)=>v+(b[i]-v)*t);
  return [a,mid,af,mid,b,bf];
 }
 return [a,b,bf,a,bf,af];
}
