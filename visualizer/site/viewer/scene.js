/* Scene selection. Every scene lives in scenes/<id>/ with a scene.json that describes its grid, model, masks and field
   layers (see scenes/README.md); scenes/index.json lists them. ?scene=<id> picks one, otherwise the index's default. */
export const ROOT = new URL('../', import.meta.url).href; // repository root (viewer/../)

export async function loadScene() {
  const params = new URLSearchParams(location.search);
  if (params.has('presentation')) {
    const { loadPublishedScene } = await import('./scene-public.js');
    return loadPublishedScene(params, new URL(ROOT));
  }
  if (params.has('run')) {
    const { loadRunScene } = await import('./scene-run.js');
    return loadRunScene(params, new URL(ROOT));
  }

  const index = await (await fetch(ROOT + 'scenes/index.json', { cache: 'no-cache' })).json();
  const qs = new URLSearchParams(location.search);
  const id = qs.get('scene') || index.default;
  if (!index.scenes.some((s) => s.id === id)) {
    throw new Error(`Unknown Scenario: ${id}. Open the Scenario catalog to choose an available case.`);
  }
  const entry = index.scenes.find((scene) => scene.id === id);
  const base = entry.base_url ? new URL(entry.base_url, ROOT).href : ROOT + 'scenes/' + id + '/';
  if (new URL(base).origin !== new URL(ROOT).origin)
    throw new Error('Local scene assets must be same-origin');
  const r = await fetch(base + 'scene.json', { cache: 'no-cache' });
  if (!r.ok) throw new Error(`scene ${id}: ${base}scene.json is missing (HTTP ${r.status})`);
  const scene = await r.json();
  if (entry.website_profile) {
    if (entry.website_profile !== `scenario/${id}/website.json`) throw new Error('Invalid website profile path');
    const response = await fetch(new URL(entry.website_profile, ROOT), { cache: 'no-cache' });
    if (!response.ok) throw new Error(`Website profile unavailable (HTTP ${response.status})`);
    const profile = await response.json();
    if (profile.schema_version !== '1.0.0' || profile.kind !== 'canopy.website-profile' ||
        profile.scenario_id !== id || !profile.features || typeof profile.features !== 'object' || Array.isArray(profile.features) ||
        Object.entries(profile.features).some(([name, feature]) =>
          !['birds', 'traffic'].includes(name) || typeof feature?.enabled !== 'boolean'))
      throw new Error('Invalid website profile');
    scene.website_features = Object.fromEntries(Object.entries(profile.features).map(([name, feature]) => [name, feature.enabled]));
    if (scene.website_features.traffic === false) {
      scene.traffic = null;
      if (scene.corridor_context) scene.corridor_context.traffic_enabled = false;
    }
  }
  scene.id = id;
  scene.base = base;
  scene.physics = new URL(scene.physics_dir ?? 'physics/', base).href;
  scene.index = index;
  scene.url = (rel) => new URL(rel, base).href;
  return scene;
}

/** URL of this page for another scene (keeps ?lite / ?tile style flags, drops view state). */
export function sceneLink(id) {
  const qs = new URLSearchParams(location.search);
  for (const k of [...qs.keys()]) if (!['lite', 'tile', 'expansion'].includes(k)) qs.delete(k);
  qs.set('scene', id);
  return location.pathname + '?' + qs.toString();
}
