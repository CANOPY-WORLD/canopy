# Scenario contribution standard

[Component overview](README.md) · [All component standards](../model/docs/framework/contributing.md)

This checkout has one curated Scenario: `imperial_corridor_8km`, the London 8 km case. South Kensington and White City are places within its context, not additional shipped Scenario entries. Synthetic examples belong to `model/tests/fixtures/` and disposable test workspaces.

## Keep configuration declarative

`scenario.json` records identity, ENU spatial meaning, exact Asset references, pinned task requests and the shared Visualizer configuration. It cannot execute Blender, Python, JavaScript or arbitrary shell commands. Use Model Methods for geometry generation and physics; retain the resulting data as Assets.

Preserve the source origin, vertical datum and actual bounds. The 8 km case is a nominal study area; the imported coverage is approximately 8.2 km wide. Do not crop or relabel data merely to force an exact square. Geometry for terrain context and terrain-normalized physics retain distinct vertical meanings.

## Change the London case

1. Validate new data through the Asset interface and retain it with immutable references.
2. Update the Asset index without overwriting existing references. Keep `derived_from` exact and within this Scenario.
3. Add a task only when its Method/version, required inputs, parameters and execution settings are actually known. Importing a historical result does not create a reproducible task automatically.
4. Select supported Asset/layer pairs in `visualization`. Keep `template:standard`; use the city preset and explicitly choose time alignment.
5. Update the case README, migration information and generated Asset review catalog. Keep private file locations out of tracked metadata.

Historical full-domain London recipes are not yet migrated; `tasks` remains empty. The separately verified GLB crop → heightfield → solar chain does not establish full-domain rerun coverage.

## Public data

Host approved website data in a dedicated Scenario repository, under `snapshots/<snapshot_id>/`. In Canopy, `publication.json` records the repository, pinned revision, data website, exact snapshot base URL and manifest SHA-256. Keep an unchanged copy of that manifest at `data/manifest.json`; this directory contains no remote payloads. Publish and verify the data first, then update Canopy's reference. Never overwrite a published snapshot.

The distribution manifest declares every payload path, presentation route, byte size and SHA-256. It is separate from the V2 Asset registry and V1.1 scientific payload contract. Follow the [publication standard](../visualizer/docs/publishing.md). Canopy publishes the shared viewer, guide and public Scenario index; the viewer reads the selected Scenario's independently hosted data. Downloads must remain scoped to the selected Scenario. New routes use `scenes/<scenario_id>/`; only London's historical aliases remain for compatibility.

## Validate

```sh
canopy --root . validate imperial_corridor_8km
python model/tools/build_review_inventory.py --refresh-assets
python model/tools/check_repository.py
```

Payload validation requires local data. For a metadata-only check, use `canopy validate imperial_corridor_8km --metadata-only`; it still requires referenced Asset descriptors and manifests. The repository checker can check the curated configuration and review catalog without downloading the dataset. Do not add a new active Scenario as a side effect of adding a Model or widget.
