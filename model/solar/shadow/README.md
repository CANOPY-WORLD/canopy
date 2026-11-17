# Solar shadow and irradiance — solar/shadow@1.0.0

## Purpose and implementation

Uses ShadowNet / HorizonNet / ground_irradiance from urban_flow.physics.solar.model, with prescribed sun directions and ASHRAE clear-sky conditions. This does not replace meteorological observations.

Shared adapter: model/src/canopy/models/methods.py. Machine-readable interface: model/src/canopy/models/specs/solar/shadow.json.

## Installation and inputs

Requires Python 3.11+. From the repository root, run `python -m pip install -e '.[physics]'`. The geometry method only needs the base NumPy/jsonschema dependencies. CPU execution is the default. GPU execution requires a matching CUDA build of PyTorch and request execution.device set to cuda; unavailable devices raise an explicit error. No learned weights are required.

The geometry asset must contain a heightfield artifact on a uniform ENU grid. times_s and altitudes_deg correspond one-to-one, with strictly increasing times.

## Parameters

| Parameter | Default | Unit | Meaning and constraints |
| --- | --- | --- | --- |
| `times_s` | `[0, 3600]` | See description | Relative physical sample times in seconds, strictly increasing |
| `altitudes_deg` | `[30, 45]` | See description | Prescribed sun altitudes, one per time |
| `azimuth_deg` | `180` | deg | Clockwise from north [0, 360] |
| `month` | `6` | 1 | ASHRAE clear-sky monthly coefficients [1, 12] |
| `albedo` | `0.2` | 1 | Ground albedo [0, 1] |
| `horizon_directions` | `8` | 1 | Azimuth samples for sky-view integration [4, 64] |

## Minimal run

Set `EXAMPLE_ROOT` to the disposable workspace printed by the example tool before running subsequent commands.

```sh
canopy --root . models solar shadow
python model/tools/run_example.py --physics solar
canopy --root "$EXAMPLE_ROOT" validate demo
canopy --root "$EXAMPLE_ROOT" serve --port 8769
```

Open http://127.0.0.1:8769/src/visualization/viewer/?scenario=demo in a browser.
Standalone request template: model/tests/fixtures/canopy/solar.json. Use the disposable workspace printed by `python model/tools/run_example.py`; pass it with `--root` on subsequent commands. In physics requests, replace REPLACE_WITH_GEOMETRY_ASSET with the asset reference returned by the geometry run, then use `canopy run REQUEST --dry-run` and `canopy run REQUEST`. Placeholders are not valid inputs.

## Outputs and validation

irradiance.npy (TYX, W/m2), shadow.npy (TYX, 1) and height.npy.

Checks finite irradiance and binary 0/1 shadows. Sun directions are inputs; real dates are not inferred from relative seconds.

Each run returns run_id and assets. run.json / events.jsonl are in cache/demo/solar/RUN_ID/. Retained assets are in data_root/project/demo/assets/bundles/RUN_ID/ and remain available after cache is deleted.

## Resources, cancellation, and troubleshooting

The default is a 16×16 heightfield, or an 8×16×16 volume for wind, using one CPU thread for small checks. Resource use grows with grid size, frame count and horizon-direction count; small-example timings do not establish city-scale performance. Current adapters collect frames in memory. Large workloads require incremental frame export before scaling up.

Use `canopy cancel demo solar RUN_ID` or Ctrl-C to request cancellation. Resume is unsupported; rerunning creates new assets.
Missing torch: install the physics extra. Missing asset: check the exact reference in the same Scenario. Missing heightfield: use a compatible geometry tool; GLB cannot automatically replace it. Nonconvergence: check boundaries, grid and timestep, then inspect diagnostics and event logs. Do not hide failure states to bypass errors.

The asset provenance retains a source snapshot, input hashes and complete parameters. Device-dependent floating-point behavior may change results. Original imported-file checksums are in model/docs/framework/physics4d-import.json.
