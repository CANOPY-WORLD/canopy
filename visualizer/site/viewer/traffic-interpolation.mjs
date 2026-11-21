// Display interpolation only: no extrapolation and no invented vehicle identities.
export function interpolateVehicle(a, b, alpha) {
  if (!b || alpha <= 0) return a;
  const t = Math.max(0, Math.min(1, alpha));
  const delta = Math.atan2(Math.sin(b.heading-a.heading), Math.cos(b.heading-a.heading));
  return {...a, x:a.x+(b.x-a.x)*t, north:a.north+(b.north-a.north)*t,
    heading:a.heading+delta*t, height:a.height+(b.height-a.height)*t,
    pitch:a.pitch+(b.pitch-a.pitch)*t};
}
