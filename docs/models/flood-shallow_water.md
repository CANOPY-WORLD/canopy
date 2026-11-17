# Shallow-water flooding — flood/shallow_water@1.0.0

## Purpose and implementation

Uses urban_flow.physics.flood.model.ShallowWater with a semi-implicit C-grid, Manning friction and closed boundaries. Rain falls only on non-solid cells; rooftop rain is not redistributed.

Shared adapter: src/canopy/models/methods.py. Machine-readable interface: src/canopy/models/specs/flood/shallow_water.json.

## Installation and inputs

Requires Python 3.11+. From the repository root, run `python -m pip install -e '.[physics]'`. The geometry method only needs the base NumPy/jsonschema dependencies. CPU execution is the default. GPU execution requires a matching CUDA build of PyTorch and request execution.device set to cuda; unavailable devices raise an explicit error. No learned weights are required.

The geometry asset must contain a heightfield and solid mask. The default initial condition is dry. Spatially varying Manning roughness and open boundaries are not exposed by this method.

## Parameters

| Parameter | Default | Unit | Meaning and constraints |
| --- | --- | --- | --- |
| `frames` | `4` | 1 | Saved intervals after initial state [1, 10000] |
| `frame_seconds` | `1` | s | Physical time between saved frames [0.001, 3600] |
| `dt_max_s` | `0.1` | s | Maximum integration step; velocity CFL may shorten it [1e-06, 10] |
| `rain_mm_h` | `20` | mm/h | Uniform rain on non-solid cells [0, 1000] |
| `initial_depth_m` | `0` | m | Initial water depth [0, 100] |
| `manning` | `0.03` | s/m^(1/3) | Uniform Manning roughness [0, 1] |
| `cg_max` | `400` | 1 | Surface linear-solver iteration limit [1, 10000] |

## Minimal run

```sh
canopy --root . models flood shallow_water
canopy --root . demo --scenario demo --physics flood
canopy --root . validate demo
canopy --root . serve --port 8769
```

Open http://127.0.0.1:8769/src/visualization/viewer/?scenario=demo in a browser.
Standalone request template: examples/canopy/flood.json. Start with `canopy init demo`. In physics requests, replace REPLACE_WITH_GEOMETRY_ASSET with the asset reference returned by the geometry run, then use `canopy run REQUEST --dry-run` and `canopy run REQUEST`. Placeholders are not valid inputs.

## Outputs and validation

water_depth.npy (TYX, m), velocity.npy (TCYX, m/s) and height.npy. Outputs include the initial frame.

Checks mass conservation, finite values and the CG iteration limit. Exceeding the iteration cap or mass-error threshold fails the run without registering assets. Strong-shock behavior is subject to the original solver limitations.

Each run returns run_id and assets. run.json / events.jsonl are in cache/demo/flood/RUN_ID/. Retained assets are in data_root/project/demo/assets/bundles/RUN_ID/ and remain available after cache is deleted.

## Resources, cancellation, and troubleshooting

The default is a 16×16 heightfield, or an 8×16×16 volume for wind, using one CPU thread for small checks. Resource use grows with grid size, frame count and horizon-direction count; small-example timings do not establish city-scale performance. Current adapters collect frames in memory. Large workloads require incremental frame export before scaling up.

Use `canopy cancel demo flood RUN_ID` or Ctrl-C to request cancellation. Resume is unsupported; rerunning creates new assets.
Missing torch: install the physics extra. Missing asset: check the exact reference in the same Scenario. Missing heightfield: use a compatible geometry tool; GLB cannot automatically replace it. Nonconvergence: check boundaries, grid and timestep, then inspect diagnostics and event logs. Do not hide failure states to bypass errors.

The asset provenance retains a source snapshot, input hashes and complete parameters. Device-dependent floating-point behavior may change results. Original imported-file checksums are in docs/framework/physics4d-import.json.
