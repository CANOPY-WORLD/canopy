// Display a declared scenario-day origin. Never infer UTC or a measurement date.
export function clockText(seconds){
  const s=Math.round(seconds),h=Math.floor(s/3600),m=Math.floor(s%3600/60);
  return [h,m,s%60].map(v=>String(v).padStart(2,'0')).join(':');
}
export function departureSeconds(value,origin,max){
  if(!/^\d{2}:\d{2}(:\d{2})?$/.test(value))return null;
  const [h,m,s=0]=value.split(':').map(Number);
  if(h>23||m>59||s>59)return null;
  const relative=h*3600+m*60+s-origin;
  return relative>=0&&relative<=max?relative:null;
}
