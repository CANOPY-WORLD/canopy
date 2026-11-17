// Axis-aligned, uniformly sampled plane in ENU; values stay at original nodes.
export function sliceLayout(positions) {
  if(!Array.isArray(positions)||positions.length<4||positions.some(p=>!Array.isArray(p)||p.length!==3||p.some(v=>!Number.isFinite(v))))throw Error('Invalid slice positions');
  const axes=[0,1,2].map(k=>[...new Set(positions.map(p=>p[k]))].sort((a,b)=>a-b));
  const active=axes.map((a,k)=>a.length>1?k:-1).filter(k=>k>=0);
  if(active.length!==2)throw Error('Slice must be axis-aligned and planar');
  const spacing=active.map(k=>{const a=axes[k],d=a[1]-a[0];if(a.some((v,i)=>i&&Math.abs(v-a[i-1]-d)>Math.max(1e-5,d*1e-5)))throw Error('Nonuniform slice');return d;});
  if(new Set(positions.map(p=>p.join(','))).size!==positions.length)throw Error('Duplicate slice positions');
  return {active,spacing};
}
