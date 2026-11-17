# MAC incompressible wind — wind/mac@1.0.0

## Purpose and implementation

Uses urban_flow.solvers.mac_torch.MAC: a staggered-grid projection for incompressible inviscid flow, without RANS/LES turbulence closure. The west boundary is an inlet, the east is a pressure outlet, and the top can optionally be a pressure outlet.

Shared adapter: src/canopy/models/methods.py. Machine-readable interface: src/canopy/models/specs/wind/mac.json.

## Installation and inputs

Requires Python 3.11+. From the repository root, run `python -m pip install -e '.[physics]'`. The geometry method only needs the base NumPy/jsonschema dependencies. CPU execution is the default. GPU execution requires a matching CUDA build of PyTorch and request execution.device set to cuda; unavailable devices raise an explicit error. No learned weights are required.

Converts the geometry heightfield into columns of solid voxels. Each dimension must be even before multigrid coarsening, and fluid cells must remain above the obstacles.

## Parameters

| Parameter | Default | Unit | Meaning and constraints |
| --- | --- | --- | --- |
| `nz` | `8` | 1 | Vertical cells [3, 128] |
| `slice_index` | `3` | 1 | Horizontal slice to visualize; full volume retained [0, 127] |
| `frames` | `2` | 1 | Saved intervals [1, 1000] |
| `frame_seconds` | `0.2` | s | Saved time spacing [0.001, 3600] |
| `dt_max_s` | `0.1` | s | Integration step cap [1e-06, 10] |
| `inlet_m_s` | `1` | m/s | West boundary eastward velocity [0.001, 100] |
| `open_top` | `false` | See description | Pressure outlet at top; otherwise slip lid |
| `pressure_rtol` | `0.0001` | 1 | Projection relative residual target [1e-08, 0.01] |
| `pressure_iterations` | `100` | 1 | PCG iteration cap [1, 1000] |

## Minimal run

```sh
canopy --root . models wind mac
canopy --root . demo --scenario demo --physics wind
canopy --root . validate demo
canopy --root . serve --port 8769
```

Open http://127.0.0.1:8769/src/visualization/viewer/?scenario=demo in a browser.
Standalone request template: examples/canopy/wind.json. Start with `canopy init demo`. In physics requests, replace REPLACE_WITH_GEOMETRY_ASSET with the asset reference returned by the geometry run, then use `canopy run REQUEST --dry-run` and `canopy run REQUEST`. Placeholders are not valid inputs.

## Outputs and validation

velocity.npy contains the selected-height TCYX slice. The full 3D field is retained in velocity_tczyx.npy + volume.json; invalid.npy marks solid samples in the slice.

The original solver checks the pressure residual and records divergence_rms. The small CPU example checks implementation behavior; it does not validate city-scale CFD.

Each run returns run_id and assets. run.json / events.jsonl are in cache/demo/wind/RUN_ID/. Retained assets are in data_root/project/demo/assets/bundles/RUN_ID/ and remain available after cache is deleted.

## Resources, cancellation, and troubleshooting

The default is a 16×16 heightfield, or an 8×16×16 volume for wind, using one CPU thread for small checks. Resource use grows with grid size, frame count and horizon-direction count; small-example timings do not establish city-scale performance. Current adapters collect frames in memory. Large workloads require incremental frame export before scaling up.

Use `canopy cancel demo wind RUN_ID` or Ctrl-C to request cancellation. Resume is unsupported; rerunning creates new assets.
Missing torch: install the physics extra. Missing asset: check the exact reference in the same Scenario. Missing heightfield: use a compatible geometry tool; GLB cannot automatically replace it. Nonconvergence: check boundaries, grid and timestep, then inspect diagnostics and event logs. Do not hide failure states to bypass errors.

The asset provenance retains a source snapshot, input hashes and complete parameters. Device-dependent floating-point behavior may change results. Original imported-file checksums are in docs/framework/physics4d-import.json.

The final frame also exports `faces_czyx.npy` (positive cell-face ENU velocities), `fluid_zyx.npy`, `inlet_zy.npy` and `mac_state.json`. pollution/steady_tracer consumes this representation; temperature consumes the cell-center sequence declared in `volume.json`. Existing assets are not amended. Rerun the computation when these artifacts are missing.
