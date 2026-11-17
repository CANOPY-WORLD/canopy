# Canopy data and organization protocol 2.0

This protocol specifies the new Canopy interfaces. Scenario / Asset / Model are the three core concepts; Running and Visualization are separate shared services. The V2 envelope reuses the validated v1.1 layer encoding. V2 JSON must not be passed off as a v1 manifest.

## Ownership and directories

```text
src/canopy/
  scenario/          # Scenario identity, asset index and configuration
  assets/            # Resolve, validate and import scenario-owned assets
  models/            # Shared interfaces, trusted registry and Physics4D adapters
    specs/<model>/<method>.json
  running/           # Lifecycle, logs, cancellation, reproduction and retention
  visualization/     # Fixed template configuration and read-only service
src/urban_flow/       # Imported Physics4D numerical code, preserving import paths
src/urban_geometry/   # Imported geometry tools
src/traffic/         # Imported traffic tools
src/visualization/{viewer,widgets,shared,vendor}/
project/<scenario>/scenario.json
<data_root>/project/<scenario>/assets/bundles/<run_id>/
  manifest.json      # v1.1 binary payload description
  geometry.asset.json / physics.asset.json
  *.glb / *.npy / *.json / provenance/
<cache_root>/<scenario>/<model>/<run_id>/
  request.json / run.json / events.jsonl / diagnostics.json / payload/
```

A bundle may contain geometry and physics, indexed as two separate Assets. Its payload is copied once, without duplicating large arrays. Asset references such as `asset_id@1` resolve only within the current Scenario. All file paths are constrained to the scenario root: absolute paths, URLs, `..` and escaping symlinks are prohibited. Cross-scenario asset references are not supported.

Registered assets cannot be overwritten. New computations generate new IDs; `derived_from` pins input asset versions. File SHA-256 checksums must match the manifest. Preserve original provenance; do not replace an unknown historical solver version with the current adapter version.

## Scenario

`scenario.json` must pass `schemas/scenario-v2.schema.json`: identity, title, spatial definition, asset index, task recipes and Visualization configuration. JSON is declarative data; opening it does not execute Python, Blender or JavaScript.

Coordinates use ENU in metres, with time in seconds. Real scenes must declare their geographic origin and vertical datum; synthetic examples use `georeferenced:false`. Assets may have smaller bounds but must share the same origin and geographic meaning. Data in other coordinate systems require an explicit transformation first.

`tasks` stores complete, versioned requests, executed with `canopy run request.json`; loading a scenario does not run its tasks. Display configuration uses `template:standard` and an engineering/city/laboratory preset with trusted presentation settings. Layers explicitly select asset + layer; camera coordinates use the scenario frame. There is no `latest` reference or selection based on directory modification times.

## Geometry

The default display encoding is self-contained glTF 2.0 GLB, Y-up `(east, up, -north)`. The shared viewer handles this conversion consistently; physical vectors remain ENU. Three.js is the rendering implementation, and Blender scripts are generation sources. Neither is the scenario storage format.

Computational geometry and display geometry serve different purposes. The heightfield and rasterize_glb methods produce GLB, float32 height, uint8 solid, heightfield.json and an entity mapping. Heights are metres relative to origin_m[2], rows point north, columns point east, and samples are at cell_center. The synthetic GLB is a heightfield surface, with no claim of a closed volume mesh. rasterize_glb preserves the original GLB and explicitly handles node transforms, sampling coverage and fill assumptions. Other geometry tools must export their computational representations explicitly; a display-only GLB cannot directly feed a Method that requires a heightfield.

## Physics result

Results use scalar_field/vector_field/trajectories/time_series categories, with encoding independent of the solver. NPY uses little-endian C-order; dtype/shape/axes/origin/spacing/sample_location/unit must all be explicit. Current display layers use YX/CYX/TYX/TCYX. Full 3D wind fields are retained separately as TCZYX arrays with volume.json, temperature as TZYX, and steady concentration as ZYX. The viewer displays explicitly selected horizontal slices; arbitrary 3D slicing is not implemented.

Missing or solid data require an explicit mask; zero must not stand in for an observation. Times must increase strictly, with no data displayed outside the recorded range. Linear trajectory interpolation connects only entities present in both adjacent frames. Absolute alignment across runs requires an epoch; relative alignment must be explicitly selected.

Geometry relationships have two parts: `derived_from` identifies the geometry version used, and layer encoding identifies the actual sampling domain. Solver grid indexes are not GLB vertex indexes. Unstructured meshes, Zarr and dynamic meshes are future extensions; readers and writers must reject unsupported representations.

## Running

All registered methods use the same lifecycle. validate is read-only; prepare writes to cache; execute computes; export writes a self-contained v1.1 payload. After validation, the framework copies it into scenario-owned storage and registers the assets. Failed or cancelled runs must not register partial results. `--no-retain` keeps trial output in cache, which can subsequently be retained with `import-run`.

States are preparing/running/exporting/complete/failed/cancelled. Numerical quality is recorded separately in diagnostics. Methods must raise convergence or quality failures; process exit code 0 does not establish physical validity. Each successful result retains its request, environment, source snapshot, input checksums, numerical diagnostics and execution log.

## Compatibility

Original Physics4D exports still use v1.1 and can be imported with `canopy import-run SCENARIO DIRECTORY`. The legacy protocol validator rejects v2 manifests; the V2 reader accepts only 2.0.0. The original Canopy root website and large resources retain their URLs as a static compatibility deployment. They are excluded from the Python package and are not automatically converted into validated physics assets.

`storage.local.json` continues to configure data_root/cache_root. Metadata lives in the checkout's project directory; data lives in data_root/project. The server maps these locations explicitly without exposing private configuration or historical recovery records.

## Supported computational representations and coupling

Beyond asset kind and layer kinds, Method inputs can declare computational representations through `required_artifacts`. `heightfield` specifies shape_yx, spacing_m, origin_m, cell_center, ENU and checksummed height/solid arrays. `volume_json` describes TCZYX wind, ENU components, m/s and sampling times. `mac_state_json` separately retains positive cell-face velocities, the fluid mask, inlet and top boundary conditions. These two velocity representations are not interchangeable.

Temperature and steady-pollution interfaces check that the wind's `derived_from` includes the exact selected geometry version, and verify origin, spacing and shape. Mismatched inputs require an explicit conversion. Unknown historical relationships remain unknown; sharing a scenario does not justify inventing a geometry dependency.

Imperial Corridor's historical display arrays retain every original float16 sample, unit and mask, converted to `npy_frames`. Nonuniform flood timestamps are copied individually. Solar clocks are not forced into other physics results' epochs. The current view explicitly selects relative comparison: equal second values do not imply the same real event.
