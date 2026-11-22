import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {createCameraJourney} from './camera-journey.mjs';

function bytes(base64) { return Uint8Array.from(atob(base64), c => c.charCodeAt(0)); }

/** Read the pinned data wrapper as data, never execute the external viewer. */
export async function createTubeLayer({scene, config, signal}) {
  const response = await fetch(config.source, {signal, credentials:'omit'});
  if (!response.ok) throw Error(`Tube geometry: HTTP ${response.status}`);
  const text = await response.text();
  const encoded = /window\.PILOT_GZ\s*=\s*["']([A-Za-z0-9+/=]+)["']/.exec(text)?.[1];
  if (!encoded) throw Error('Unsupported Tube data wrapper');
  const payload = await new Response(new Blob([bytes(encoded)]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',payload)), b=>b.toString(16).padStart(2,'0')).join('');
  if (digest !== config.sha256) throw Error('Tube source checksum mismatch');
  signal?.throwIfAborted();
  const data = JSON.parse(new TextDecoder().decode(payload));
  const index = data.pilot.platforms.findIndex(p=>p.id===config.platform);
  if (index < 0) throw Error('Tube platform is unavailable');
  const platform = data.pilot.platforms[index], shells = data.assets.shells;
  const loader = new GLTFLoader();
  const load = async b64 => (await loader.parseAsync(bytes(b64).buffer,'')).scene;
  const [body,parts,link] = await Promise.all([
    load(shells.bodies[shells.body_of[index]]),load(shells.parts[index]),
    data.assets.links[index] ? load(data.assets.links[index]) : null,
  ]);
  const group = new THREE.Group(); group.name = 'London Tube · representative South Kensington platform';
  const local = new THREE.Group(); local.add(body,parts); if(link)local.add(link);
  // Same corridor ENU as the original Canopy network export. Convert exactly once.
  const [east,north,up] = platform.centre_enu;
  local.position.set(east,up,-north); local.rotation.y = platform.shell_local_x_heading_rad;
  group.add(local); group.visible = false;
  const light = new THREE.HemisphereLight(0xffffff,0x777b85,2); group.add(light);
  local.updateMatrixWorld(true);
  const world = p => local.localToWorld(new THREE.Vector3(...p)).toArray();
  // A short look target keeps drag-to-look inside the platform instead of orbiting
  // around a point thirty metres away and swinging through the tunnel wall.
  const position = world([30,2.35,-3.1]), target = world([28,2.3266666667,-3.1]);
  const journey = createCameraJourney([
    {time:2.8,position:[east+60,100,-north+100],target:[east,0,-north]},
    {time:5,position,target},
  ], {safeApproach:true});
  const resources = new Set();
  group.traverse(o=>{if(o.geometry)resources.add(o.geometry);for(const m of o.material?(Array.isArray(o.material)?o.material:[o.material]):[]){resources.add(m);for(const v of Object.values(m))if(v?.isTexture)resources.add(v);}});
  const dispose=()=>{group.removeFromParent();for(const r of resources)r.dispose();};
  if(signal?.aborted){dispose();signal.throwIfAborted();}
  scene.add(group);
  return {group,journey,platform,source:config.source,sha256:digest,
    pose:{pos:new THREE.Vector3(...position),target:new THREE.Vector3(...target)},
    setVisible(on){group.visible=on;},dispose};
}
