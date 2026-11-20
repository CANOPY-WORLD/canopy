// View-dependent residency of original GLBs; the existing overview fills gaps.
// No source file, mesh, coordinate or scientific sample is simplified here.
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {MeshoptDecoder} from 'three/addons/libs/meshopt_decoder.module.js';
import {drapeBuildings} from './corridor-terrain.js';
import {createAssetQueue, fetchAsset} from './asset-queue.mjs';

const VIEW_TILES = 6, MAX_TILES = 8; // Reserve two extra slots for recorded routes crossing more tiles.
export function createStreamedDetailTiles({scene, camera, focus, coarse, indexUrl,
  onChange = () => {}, onStatus = () => {}, radius = 1400, keepRadius = 1750, maxHeight = 3500}) {
  const group = new THREE.Group(); group.name = 'streamed_detail_geometry'; scene.add(group);
  const entries = new Map(), patched = new Map();
  const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  const rects = Array.from({length: MAX_TILES}, () => new THREE.Vector4());
  const uniforms = {canopyDetailRects: {value: rects}, canopyDetailHalf: {value: new Float32Array(MAX_TILES)}, canopyDetailCount: {value: 0}};
  const frustum = new THREE.Frustum(), projection = new THREE.Matrix4(), sphere = new THREE.Sphere();
  let tiles = [], enabled = true, disposed = false, lastCheck = -Infinity, requiredPoints = [], requiredTiles = null;
  const progress = {mode: 'streamed', loaded: 0, total: 0, complete: false, errors: [], residentTiles: 0,
    residentGeometryBytes: 0, currentViewBytes: 0, currentViewReceived: 0, preparing: 0, downloading: 0};
  function release(root) {
    const geometries = new Set(), materials = new Set(), textures = new Set();
    root.traverse(o => {
      if (o.geometry) geometries.add(o.geometry);
      for (const material of Array.isArray(o.material) ? o.material : o.material ? [o.material] : []) {
        materials.add(material); for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
      }
    });
    root.removeFromParent();
    for (const geometry of geometries) geometry.dispose();
    for (const material of materials) material.dispose();
    for (const texture of textures) { texture.dispose(); texture.source?.data?.close?.(); }
  }
  function geometryBytes(root) {
    const buffers = new Set();
    root.traverse(o => {if (o.geometry) {
      for (const attr of [...Object.values(o.geometry.attributes), o.geometry.index].filter(Boolean))
        buffers.add((attr.array ?? attr.data?.array).buffer);
    }});
    return [...buffers].reduce((n, buffer) => n + buffer.byteLength, 0);
  }
  function patchCoarse() {
    coarse.traverse(o => {
      if (!o.isMesh) return;
      for (const material of Array.isArray(o.material) ? o.material : [o.material]) {
        if (patched.has(material)) continue;
        const previous = material.onBeforeCompile, key = material.customProgramCacheKey;
        patched.set(material, {previous, key});
        material.onBeforeCompile = (shader, renderer) => {
          previous.call(material, shader, renderer); Object.assign(shader.uniforms, uniforms);
          shader.vertexShader = 'varying vec2 canopyDetailPosition;\n' + shader.vertexShader.replace('#include <project_vertex>',
            '#include <project_vertex>\ncanopyDetailPosition = (modelMatrix * vec4(transformed, 1.0)).xz;');
          shader.fragmentShader = `varying vec2 canopyDetailPosition;\nuniform vec4 canopyDetailRects[${MAX_TILES}];\nuniform float canopyDetailHalf[${MAX_TILES}];\nuniform int canopyDetailCount;\n` + shader.fragmentShader.replace('void main() {', `void main() {
            for (int i = 0; i < ${MAX_TILES}; i++) {
              if (i >= canopyDetailCount) break;
              vec2 d = canopyDetailPosition - canopyDetailRects[i].xy;
              vec2 q = vec2(dot(d, canopyDetailRects[i].zw), dot(d, vec2(-canopyDetailRects[i].w, canopyDetailRects[i].z)));
              if (abs(q.x) < canopyDetailHalf[i] && abs(q.y) < canopyDetailHalf[i]) discard;
            }`);
        };
        material.customProgramCacheKey = () => key.call(material) + '|canopy-streamed-detail-v1';
        material.needsUpdate = true;
      }
    });
  }
  function refresh() {
    const ready = [...entries.values()].filter(e => e.complete);
    ready.forEach((entry, i) => {
      const tile = entry.tile, angle = tile.rotation_rad ?? 0;
      rects[i].set(...tile.centre_xz, Math.cos(angle), Math.sin(angle));
      uniforms.canopyDetailHalf.value[i] = tile.half_m;
    });
    uniforms.canopyDetailCount.value = enabled ? ready.length : 0;
    coarse.visible = enabled; group.visible = enabled;
    const jobs = queue.snapshot();
    Object.assign(progress, {
      loaded: [...entries.values()].reduce((n, e) => n + e.loaded, 0),
      total: [...entries.values()].reduce((n, e) => n + e.files.length, 0),
      residentTiles: entries.size,
      residentGeometryBytes: [...entries.values()].reduce((n, e) => n + e.geometryBytes, 0),
      currentViewBytes: [...entries.values()].reduce((n, e) => n + e.files.reduce((s, f) => s + (f.bytes ?? 0), 0), 0),
      currentViewReceived: [...entries.values()].reduce((n, e) => n + e.received, 0) + jobs.reduce((n, j) => n + j.received, 0),
      downloading: jobs.filter(j => j.state === 'downloading').length,
      preparing: jobs.filter(j => j.state === 'preparing').length,
      errors: [...jobs.filter(j => j.state === 'failed').map(j => j.error), ...(progress.requiredTiles > MAX_TILES ? ['This route needs complete geometry mode.'] : []), ...(progress.requiredOutside ? ['This route extends beyond published building coverage.'] : [])],
      complete: tiles.length > 0 && !jobs.length,
    });
    onStatus(progress);
  }
  function evict(entry) {
    entries.delete(entry.tile.id);
    for (const file of entry.files) queue.cancel(file.key);
    release(entry.root);
  }
  const queue = createAssetQueue({
    load: fetchAsset,
    async prepare(bytes, item) {
      const gltf = await loader.parseAsync(bytes, new URL('./', item.url).href);
      try {
        drapeBuildings(gltf.scene);
        gltf.scene.updateWorldMatrix(true, true);
        gltf.scene.traverse(o => {o.matrixAutoUpdate = false; o.matrixWorldAutoUpdate = false;});
        return gltf.scene;
      } catch (error) { release(gltf.scene); throw error; }
    },
    commit(root, item) {
      const entry = entries.get(item.tileId);
      if (!entry || disposed) {release(root); return;}
      entry.root.add(root); entry.geometryBytes += geometryBytes(root);
      entry.loaded++; entry.received += item.bytes ?? 0;
      entry.complete = entry.loaded === entry.files.length;
      // Only replace the overview after the base mesh AND every landmark exist.
      entry.root.visible = entry.complete;
      if (entry.complete) onChange();
    },
    discard: release,
    onChange: () => {if (!disposed) refresh();},
  });
  function localDistance(tile, point) {
    const x = point.x - tile.centre_xz[0], z = point.z - tile.centre_xz[1], a = tile.rotation_rad ?? 0;
    return Math.hypot(Math.max(0, Math.abs(x * Math.cos(a) + z * Math.sin(a)) - tile.half_m),
      Math.max(0, Math.abs(-x * Math.sin(a) + z * Math.cos(a)) - tile.half_m));
  }
  function tileFor(point) {return tiles.find(tile => localDistance(tile, {x: point[0], z: point[2]}) === 0);}
  function update(now = performance.now()) {
    if (disposed || !tiles.length || now - lastCheck < 250) return;
    lastCheck = now; patchCoarse();
    const target = focus?.() ?? camera.position;
    camera.updateMatrixWorld(); frustum.setFromProjectionMatrix(projection.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse));
    if (!requiredTiles) {
      const matched = requiredPoints.map(tileFor);
      progress.requiredOutside = matched.filter(t => !t).length;
      requiredTiles = new Set(matched.filter(Boolean).map(t => t.id));
    }
    const required = requiredTiles;
    progress.requiredTiles = required.size;
    const high = camera.position.y - target.y > maxHeight;
    const ranked = tiles.map(tile => {
      const distance = localDistance(tile, target);
      sphere.center.set(tile.centre_xz[0], 100, tile.centre_xz[1]); sphere.radius = Math.hypot(tile.half_m, tile.half_m, 200);
      const visible = frustum.intersectsSphere(sphere);
      return {tile, distance, priority: (required.has(tile.id) ? -100000 : visible ? 0 : 10000) + distance,
        wanted: enabled && (required.has(tile.id) || (!high && visible && distance < (entries.has(tile.id) ? keepRadius : radius)))};
    }).filter(item => item.wanted).sort((a, b) => a.priority - b.priority).slice(0, Math.min(MAX_TILES, Math.max(VIEW_TILES, required.size)));
    const wanted = new Set(ranked.map(item => item.tile.id));
    let changed = false;
    for (const entry of [...entries.values()]) if (!wanted.has(entry.tile.id)) {evict(entry); changed = true;}
    for (const {tile, priority} of ranked) {
      let entry = entries.get(tile.id);
      if (!entry) {
        changed = true;
        const files = [{file: tile.file, bytes: tile.bytes}, ...(tile.landmarks ?? [])].filter(f => f.file)
          .map(file => ({key: `${tile.id}:${file.file}`, tileId: tile.id, url: new URL(file.file, indexUrl).href, bytes: file.bytes}));
        const root = new THREE.Group(); root.name = `detail:${tile.id}`; root.visible = false; group.add(root);
        entry = {tile, files, root, loaded: 0, received: 0, geometryBytes: 0, complete: !files.length}; entries.set(tile.id, entry);
        for (const file of files) queue.add(file.key, file, priority);
      } else for (const file of entry.files) {
        // Update only pending jobs; do not re-request committed files.
        const job = queue.snapshot().find(j => j.key === file.key);
        if (job) queue.add(file.key, file, priority);
      }
    }
    refresh();
    if (changed) onChange();
  }
  const controller = new AbortController();
  const readIndex = () => fetch(indexUrl, {signal: controller.signal}).then(r => {
    if (!r.ok) throw new Error(`Geometry index HTTP ${r.status}`); return r.json();
  }).then(index => {
    if (disposed) return 0;
    if (!Array.isArray(index.tiles) || index.tiles.some(t => !Array.isArray(t.centre_xz) || !Number.isFinite(t.half_m) || t.half_m <= 0))
      throw new Error('Invalid detail tile index');
    tiles = index.tiles; requiredTiles = null; update(); return tiles.length;
  }).catch(error => {
    if (!disposed) { progress.errors = [String(error)]; onStatus(progress); onChange(); }
    return 0;
  });
  const ready = readIndex();
  return {ready, update, group, progress,
    get loaded() {return [...entries.values()].filter(e => e.complete).map(e => e.tile.id);},
    get stats() {return {...queue.stats, ...progress, maxTiles: MAX_TILES, viewTiles: VIEW_TILES, jobs: queue.snapshot()};},
    hasPoints(points) {return points.length > 0 && points.every(p => {const tile = tileFor(p); return tile && entries.get(tile.id)?.complete;});},
    setRequiredPoints(points) {requiredPoints = points; requiredTiles = null; lastCheck = -Infinity;},
    setEnabled(on) {if (enabled === on) return; enabled = on; lastCheck = -Infinity; update(); refresh(); onChange();},
    retry() {if (!tiles.length) {progress.errors = []; onStatus(progress); readIndex();} else queue.retry();},
    dispose() {
      disposed = true; controller.abort(); queue.dispose();
      for (const entry of entries.values()) release(entry.root); entries.clear(); group.removeFromParent();
      for (const [material, {previous, key}] of patched) {material.onBeforeCompile = previous; material.customProgramCacheKey = key; material.needsUpdate = true;}
      coarse.visible = true;
    },
  };
}
