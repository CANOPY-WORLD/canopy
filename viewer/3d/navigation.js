import * as THREE from 'three';

// Presentation-only camera control. Indoor queries use retained geometry, not city-wide rays.
export function createNavigation({camera, controls, canvas, indoorRoot, groundHeight, invalidate, onEnter}) {
  const keys = new Set(), direction = new THREE.Vector3(), right = new THREE.Vector3();
  const ray = new THREE.Raycaster(), up = new THREE.Vector3(0, 1, 0);
  let active = false, manual = false, dragging = false, near = camera.near;
  const panel = document.createElement('div');
  panel.className = 'navigation-control';
  const button = document.createElement('button');
  button.type = 'button'; button.textContent = 'Explore · WASD';
  button.setAttribute('aria-pressed', 'false');
  const help = document.createElement('span'); help.id = 'navigation-help'; help.hidden = true;
  help.textContent = 'WASD move · drag to look · Q/E down/up · Shift faster · Esc exit';
  button.setAttribute('aria-describedby', help.id); panel.append(button, help); document.body.append(panel);
  const editable = target => target?.closest?.('input,textarea,select,button,a,[contenteditable="true"],[role="textbox"]');
  function clear() { keys.clear(); dragging = false; }
  function setActive(value) {
    active = value; clear();
    if (active) {
      manual = true; onEnter(); near = camera.near; camera.near = .1;
      // Flush pending orbit damping before taking ownership of the camera.
      const damping = controls.enableDamping; controls.enableDamping = false; controls.update(); controls.enableDamping = damping;
      controls.enabled = false;
    } else { camera.near = near; controls.enabled = true; }
    camera.updateProjectionMatrix();
    button.setAttribute('aria-pressed', String(active)); button.textContent = active ? 'Exit exploration' : 'Explore · WASD';
    help.textContent = indoorRoot() ? 'WASD move · drag to look · same-floor movement · Esc exit' : 'WASD move · drag to look · Q/E down/up · Shift faster · Esc exit';
    help.hidden = !active; canvas.style.cursor = active ? 'grab' : ''; invalidate();
  }
  button.addEventListener('click', () => { setActive(!active); button.blur(); });
  window.addEventListener('keydown', e => {
    if (!active || editable(e.target)) return;
    if (e.code === 'Escape') { setActive(false); return; }
    if (['KeyW','KeyA','KeyS','KeyD','KeyQ','KeyE','ShiftLeft','ShiftRight'].includes(e.code)) { e.preventDefault(); keys.add(e.code); }
  });
  window.addEventListener('keyup', e => keys.delete(e.code));
  window.addEventListener('blur', clear);
  document.addEventListener('visibilitychange', clear);
  document.addEventListener('focusin', e => { if (editable(e.target)) clear(); });
  canvas.addEventListener('pointerdown', e => {
    if (!active || e.button !== 0) return;
    dragging = true; canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener('pointermove', e => {
    if (!active || !dragging) return;
    const angles = new THREE.Euler().setFromQuaternion(camera.quaternion, 'YXZ');
    angles.y -= e.movementX * .003; angles.x = THREE.MathUtils.clamp(angles.x - e.movementY * .003, -1.5, 1.5);
    camera.quaternion.setFromEuler(angles); camera.getWorldDirection(direction);
    controls.target.copy(camera.position).addScaledVector(direction, 10); invalidate();
  });
  canvas.addEventListener('pointerup', clear);
  canvas.addEventListener('pointercancel', clear);
  canvas.addEventListener('lostpointercapture', () => { dragging = false; });
  function blocked(delta, root) {
    if (!root) return false;
    const length = delta.length(); if (!length) return false;
    root.updateWorldMatrix(true, true);
    ray.far = length + .3; direction.copy(delta).normalize();
    // Sweep across the body's width at head, torso and foot height. Both mesh faces
    // block movement; exported one-sided walls must also block from inside a room.
    right.crossVectors(direction, up).normalize();
    const meshes = []; root.traverseVisible(o => { if (o.isMesh) meshes.push(o); });
    const sides = new Map();
    for (const mesh of meshes) for (const m of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
      if (m && !sides.has(m)) { sides.set(m, m.side); m.side = THREE.DoubleSide; }
    }
    try {
      for (const height of [0, -.7, -1.4]) for (const offset of [-.25, 0, .25]) {
        ray.set(camera.position.clone().addScaledVector(up, height).addScaledVector(right, offset), direction);
        if (ray.intersectObjects(meshes, false).length) return true;
      }
      return false;
    } finally { for (const [m, side] of sides) m.side = side; }
  }
  function tick(dt) {
    if (!active) return;
    controls.enabled = false;
    if (!keys.size) return;
    const root = indoorRoot();
    camera.getWorldDirection(direction); direction.y = 0; direction.normalize();
    right.crossVectors(direction, up).normalize();
    const delta = direction.clone().multiplyScalar(Number(keys.has('KeyW')) - Number(keys.has('KeyS')))
      .addScaledVector(right, Number(keys.has('KeyD')) - Number(keys.has('KeyA')));
    if (!root) delta.y = Number(keys.has('KeyE')) - Number(keys.has('KeyQ'));
    const height = groundHeight(camera.position);
    const speed = root ? 1.6 : Number.isFinite(height) ? THREE.MathUtils.clamp(Math.abs(camera.position.y - height) * .35, 12, 250) : 3;
    delta.normalize().multiplyScalar(speed * Math.min(dt, .05) * (!root && (keys.has('ShiftLeft') || keys.has('ShiftRight')) ? 3 : 1));
    if (!root) delta.y = Math.max(delta.y, groundHeight(camera.position.clone().add(delta)) + 1.6 - camera.position.y);
    if (!blocked(delta, root)) { camera.position.add(delta); controls.target.add(delta); invalidate(); }
  }
  return {tick, setActive, get active() { return active; }, get manual() { return manual; }, reset() { if (active) setActive(false); manual = false; }};
}
