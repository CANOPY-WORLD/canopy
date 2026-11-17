# Synthetic heightfield and GLB — geometry/heightfield@1.0.0

## Purpose and implementation

Generates small synthetic heightfields, with an optional central obstacle. The output GLB is not a watertight volume mesh and is unsuitable for finite-element volume cells.

Shared adapter: model/src/canopy/models/methods.py. Machine-readable interface: model/src/canopy/models/specs/geometry/heightfield.json.

## Installation and inputs

Requires Python 3.11+. From the repository root, run `python -m pip install -e '.[physics]'`. The geometry method only needs the base NumPy/jsonschema dependencies. CPU execution is the default. GPU execution requires a matching CUDA build of PyTorch and request execution.device set to cuda; unavailable devices raise an explicit error. No learned weights are required.

No input assets are required. Generated extents must lie within Scenario bounds.

## Parameters

| Parameter | Default | Unit | Meaning and constraints |
| --- | --- | --- | --- |
| `nx` | `16` | 1 | Columns along east [3, 512] |
| `ny` | `16` | 1 | Rows along north [3, 512] |
| `cell_m` | `1` | m | Uniform cell spacing [0.01, 1000] |
| `obstacle_height_m` | `2` | m | Central synthetic 2x2-cell obstacle height; 0 means flat [0, 10000] |

## Minimal run

Set `EXAMPLE_ROOT` to the disposable workspace printed by the example tool before running subsequent commands.

```sh
canopy --root . models geometry heightfield
python model/tools/run_example.py --physics
canopy --root "$EXAMPLE_ROOT" validate demo
canopy --root "$EXAMPLE_ROOT" serve --port 8769
```

Open http://127.0.0.1:8769/src/visualization/viewer/?scenario=demo in a browser.
Standalone request template: model/tests/fixtures/canopy/geometry.json. Use the disposable workspace printed by `python model/tools/run_example.py`; pass it with `--root` on subsequent commands. In physics requests, replace REPLACE_WITH_GEOMETRY_ASSET with the asset reference returned by the geometry run, then use `canopy run REQUEST --dry-run` and `canopy run REQUEST`. Placeholders are not valid inputs.

## Outputs and validation

visual.glb, height.npy, solid.npy, entities.json and heightfield.json.

Validates the GLB container, coordinates, extents and data hashes. Geometry is explicitly synthetic, with no claim of measured city data.

Each run returns run_id and assets. run.json / events.jsonl are in cache/demo/geometry/RUN_ID/. Retained assets are in data_root/project/demo/assets/bundles/RUN_ID/ and remain available after cache is deleted.

## Resources, cancellation, and troubleshooting

The default is a 16×16 heightfield, or an 8×16×16 volume for wind, using one CPU thread for small checks. Resource use grows with grid size, frame count and horizon-direction count; small-example timings do not establish city-scale performance. Current adapters collect frames in memory. Large workloads require incremental frame export before scaling up.

Use `canopy cancel demo geometry RUN_ID` or Ctrl-C to request cancellation. Resume is unsupported; rerunning creates new assets.
Missing torch: install the physics extra. Missing asset: check the exact reference in the same Scenario. Missing heightfield: use a compatible geometry tool; GLB cannot automatically replace it. Nonconvergence: check boundaries, grid and timestep, then inspect diagnostics and event logs. Do not hide failure states to bypass errors.

The asset provenance retains a source snapshot, input hashes and complete parameters. Device-dependent floating-point behavior may change results. Original imported-file checksums are in model/docs/framework/physics4d-import.json.
