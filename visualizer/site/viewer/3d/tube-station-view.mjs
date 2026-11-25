// Choose only views supported by the archived platform metadata. No depth is invented.
export function stationView(station, platforms, statics) {
  const deep = station.platforms.filter(i => platforms[i].template === 'deep');
  const frame = deep.includes(station.view.frame) ? station.view.frame : deep[0];
  const record = frame !== undefined ? platforms[frame] : platforms[station.platforms[0]] ?? statics[station.statics[0]];
  if (!record?.centre_enu?.every(Number.isFinite)) throw Error('Tube station has no usable source position');
  return {kind: deep.length ? 'interior' : 'network', frame, deep, centre: record.centre_enu,
    label: `${station.name} · ${deep.length ? 'platform interior' : 'network location'}`};
}
