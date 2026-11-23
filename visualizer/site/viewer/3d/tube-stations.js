// London Tube · any built station, from the geometry-only station file that the scene's `underground.stations` declares.
//
// The file has the container and the fields of the platform source that tube-layer.js reads (window.PILOT_GZ: base64 of
// gzip of JSON; pilot.platforms, assets.shells, assets.links), plus roofs, static platforms and a station list with a
// camera pose per station. It carries no trains, passengers or timetable. It is part of the Scenario data, is fetched
// through the scene's routed URLs only when a station is first chosen, and is checked against the SHA-256 the scene
// declares before it is decoded; it is read as data and never executed.
// Station interiors, stairs, ways out and roofs are representative and assumed, not surveyed.
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {createCameraJourney} from './camera-journey.mjs';

const bytes = base64 => Uint8Array.from(atob(base64), c => c.charCodeAt(0));

export async function loadTubeStations({config, signal}) {
  const response = await fetch(config.source, {signal, credentials: 'omit'});
  if (!response.ok) throw Error(`Tube stations: HTTP ${response.status}`);
  if (!/^[0-9a-f]{64}$/.test(config.sha256 ?? '')) throw Error('Tube stations data has no declared checksum');
  const file = await response.arrayBuffer();
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', file)), b => b.toString(16).padStart(2, '0')).join('');
  if (digest !== config.sha256) throw Error('Tube stations checksum mismatch');
  const encoded = /window\.PILOT_GZ\s*=\s*["']([A-Za-z0-9+/=]+)["']/.exec(new TextDecoder().decode(file))?.[1];
  if (!encoded) throw Error('Unsupported Tube stations wrapper');
  const payload = await new Response(new Blob([bytes(encoded)]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
  signal?.throwIfAborted();
  const data = JSON.parse(new TextDecoder().decode(payload));
  const byId = new Map(data.stations.map(station => [station.id, station]));
  for (const [id] of config.list) if (!byId.has(id)) throw Error(`Tube station ${id} is not in the pinned data`);
  const P = data.pilot.platforms, S = data.pilot.static_platforms ?? [], A = data.assets, SH = A.shells;
  const loader = new GLTFLoader(), parse = async base64 => (await loader.parseAsync(bytes(base64).buffer, '')).scene;

  /** Build one station in the shared scene, hidden. The caller shows it and disposes it. */
  async function build(scene, id, buildSignal) {
    const station = byId.get(id); if (!station) throw Error('Tube station is unavailable');
    const group = new THREE.Group(); group.name = `London Tube · ${station.name} (representative station)`; group.visible = false;
    const frames = new Map();
    const place = async (record, key, models, openAir) => {
      // Same corridor ENU as the Canopy network export, converted once to east/up/negative-north.
      const local = new THREE.Group(), [east, north, up] = record.centre_enu;
      local.position.set(east, up, -north); local.rotation.y = record.shell_local_x_heading_rad; local.userData.openAir = openAir;
      for (const model of await Promise.all(models.filter(Boolean).map(parse))) local.add(model);
      group.add(local); frames.set(key, local);
    };
    await Promise.all([
      ...station.platforms.map(i => place(P[i], i, [SH.bodies[SH.body_of[i]], SH.parts[i], A.links[i], A.roofs?.[i]], P[i].template === 'open_cutting')),
      ...station.statics.map(k => place(S[k], `static ${k}`, [SH.bodies[SH.static_body_of[k]], SH.static_parts[k]], true)),
    ]);
    group.add(new THREE.HemisphereLight(0xffffff, 0x777b85, 2)); group.updateMatrixWorld(true);
    const frame = frames.get(station.view.frame ?? `static ${station.view.frame_static}`), world = p => frame.localToWorld(new THREE.Vector3(...p)).toArray();
    const position = world(station.view.position), target = world(station.view.target), centre = frame.position;
    // An open-air or elevated station is looked at from above; the city surface would cover or cut through it.
    const open = station.statics.length > 0 || station.platforms.some(i => P[i].template === 'open_cutting');
    const view = {entry: null, pose: {pos: new THREE.Vector3(...position), target: new THREE.Vector3(...target)},
      journey: createCameraJourney([
        {time: 2.8, position: [centre.x + 60, 100, centre.z + 100], target: [centre.x, 0, centre.z]},
        {time: 5, position, target},
      ], {safeApproach: true})};
    // Where the stored view is a whole-station overview (its frame is an open-air platform), the corners of the bounding
    // boxes of the open-air meshes, in scene coordinates: what that overview has to keep in view. Deep platforms of the
    // same station lie below and beside it and are not part of the fit.
    const corners = [], box = new THREE.Box3(), matrix = new THREE.Matrix4();
    if (frame.userData.openAir) for (const part of group.children) if (part.userData.openAir) part.traverse(o => {
      if (!o.isMesh) return;
      if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
      for (let n = 0, count = o.isInstancedMesh ? o.count : 1; n < count; n++) {
        if (o.isInstancedMesh) { o.getMatrixAt(n, matrix); matrix.premultiply(o.matrixWorld); } else matrix.copy(o.matrixWorld);
        box.copy(o.geometry.boundingBox);
        for (let k = 0; k < 8; k++) corners.push(new THREE.Vector3(k & 1 ? box.max.x : box.min.x, k & 2 ? box.max.y : box.min.y, k & 4 ? box.max.z : box.min.z).applyMatrix4(matrix));
      }
    });
    /**
     * Fit an open station's overview to the viewport. The stored pose is kept wherever its open-air part is in view
     * (the desktop composition); on a narrower viewport the camera moves back along the same line of sight until it is.
     * The camera then starts from further back on that line, so the station stays in the picture throughout.
     */
    const frameView = camera => {
      if (!corners.length || !camera) return;
      const to = new THREE.Vector3(...target), back = new THREE.Vector3(...position).sub(to), distance = back.length(), forward = back.clone().multiplyScalar(-1 / distance);
      const right = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 1, 0)).normalize(), up = new THREE.Vector3().crossVectors(right, forward);
      const tanY = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)), tanX = tanY * camera.aspect, q = new THREE.Vector3();
      let scale = 1;
      for (const corner of corners) { q.copy(corner).sub(to); const depth = q.dot(forward); scale = Math.max(scale, (Math.abs(q.dot(right)) / tanX - depth) / distance, (Math.abs(q.dot(up)) / tanY - depth) / distance); }
      if (scale > 1) scale *= 1.06;                                 // a small margin once the stored pose does not fit
      const at = k => to.clone().addScaledVector(back, k), fitted = at(scale);
      view.scale = scale; view.pose = {pos: fitted, target: to}; view.entry = {position: at(scale * 1.6).toArray(), target: to.toArray()};
      view.journey = createCameraJourney([{time: 2.6, position: fitted.toArray(), target: to.toArray()}]);
    };
    const resources = new Set();
    group.traverse(o => { if (o.geometry) resources.add(o.geometry); for (const m of o.material ? (Array.isArray(o.material) ? o.material : [o.material]) : []) { resources.add(m); for (const v of Object.values(m)) if (v?.isTexture) resources.add(v); } });
    const dispose = () => { group.removeFromParent(); for (const r of resources) r.dispose(); };
    if (buildSignal?.aborted) { dispose(); buildSignal.throwIfAborted(); }
    scene.add(group);
    return {group, station: {id: station.id, name: station.name, service: station.service, platforms: station.platforms.length + station.statics.length}, open,
      get journey() { return view.journey; }, get pose() { return view.pose; }, get entry() { return view.entry; }, get fitScale() { return view.scale ?? 1; },
      frameView, setVisible(on) { group.visible = on; }, dispose};
  }
  return {stations: data.stations.map(station => ({id: station.id, name: station.name, service: station.service})), info: data.wrapper, source: config.source, sha256: digest, build};
}
