# Shallow-water flooding — flood/shallow_water@2.0.0

## Implementation and provenance

This Method directly runs the original **AI4SWE Linear** numerical kernel from [Amin-Nadimy/Shallow_Water_Equations_NN4PDEs](https://github.com/Amin-Nadimy/Shallow_Water_Equations_NN4PDEs), pinned to commit `be4ccdac6270fb0a27a11856d4fafe44cef2ed9e`. It uses fixed convolution operators, Petrov–Galerkin stabilization, the original friction and boundary routines, two Jacobi sweeps per forward pass and two forward passes per timestep. It needs no learned weights or training.

- [Canopy lifecycle adapter](../../src/canopy/models/flood.py)
- [Upstream kernel loader and case state](../../src/canopy/models/nn4pdes.py)
- [Unmodified upstream code, license and source record](../../src/canopy/models/vendor/nn4pdes/README.md)
- [Machine-readable interface](../../src/canopy/models/specs/flood/shallow_water.json)
- [Example request](../../tests/fixtures/canopy/flood.json)

The loader executes the numerical initialization and complete `AI4SWE` class from the hash-checked vendored file. Canopy supplies the case configuration instead of executing the Carlisle file-reading/output script. It does not reimplement the upstream numerical equations or fetch code at runtime. The source, license and upstream identity are included in the installed wheel and retained run source snapshot.

## Installation

Use Python 3.11 or newer. From the Canopy repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[physics]'
canopy --root . models flood shallow_water
```

CPU is the default. For CUDA, install a matching CUDA build of PyTorch and set `execution.device` to `cuda`. An unavailable requested device fails preflight. The original Carlisle script's pandas and CSV inputs are not needed by this adapter; it consumes Canopy Geometry Assets. CUDA results can differ in floating-point rounding and require their own acceptance check.

## Inputs and physical meaning

The exact-version Geometry Asset must contain a validated heightfield and binary solid mask, with float32 heights, a square cell spacing and ENU sampling coordinates. GLB alone is insufficient. Rows increase north, columns east, and heights are relative to the declared grid origin. Buildings must already be represented by positive raised terrain heights. The mask excludes rainfall on buildings and hides their display cells; it does **not** create impermeable C-grid faces in the upstream solver. There is no added rooftop redistribution, drainage or infiltration.

The upstream state uses `values_H = -terrain_height` and `values_h = terrain_height + water_depth`. The initial depth applies only to non-solid cells. Exported water depth is `values_H + values_h`; velocity is `(-values_u, values_v, 0)` in east/north/up. This conversion is checked against the original derivative kernels. No missing frames, clipping corrections or replacement values are invented.

Boundary behavior is exactly the original `boundary_condition_u`, `boundary_condition_v` and `boundary_condition_eta`: normal velocity padding is zero, tangential velocity is copied, and the free-surface-related padding is zero. This is not a configurable open-boundary model or the former C-grid closed-basin model. Absolute terrain offsets can affect the fixed surface padding; select and validate the physical domain/datum deliberately. Arbitrary hydrographs, user boundary conditions, spatial roughness and the Quadratic variant are not exposed by this Method.

## Parameters

| Parameter | Default | Unit | Meaning and constraints |
| --- | --- | --- | --- |
| `frames` | `4` | 1 | Saved intervals after the initial state; 1–10000 |
| `frame_seconds` | `1` | s | Physical sampling interval; 0.001–3600 |
| `dt_max_s` | `0.025` | s | Upper bound on fixed integration step; 0.000001–10 |
| `rain_mm_h` | `20` | mm/h | Uniform rainfall on non-solid cells; 0–1000 |
| `initial_depth_m` | `0` | m | Initial depth on non-solid cells; 0–100 |
| `manning` | `0.055` | s/m^(1/3) | Fixed by upstream; any other value is rejected |

The driver chooses `steps_per_frame = ceil(frame_seconds / dt_max_s)` and `dt = frame_seconds / steps_per_frame`, then keeps that timestep fixed. Output times are exactly `0, frame_seconds, …, frames * frame_seconds`. There is no adaptive CFL adjustment or CG solver. A smaller timestep is not a substitute for validating wet/dry behavior, boundary effects and convergence on the intended case.

The default 1 m synthetic building case uses 0.025 s. At 0.1 s, its four-second run triggers the negative-depth rejection; the default was reduced without changing the kernel or acceptance threshold. A coarser 2 m reference case is separately checked at 0.1 s. These small-case settings are not city-wide stability guarantees.

## Run a complete CPU example

```sh
python model/tools/run_example.py --physics flood
# Set this to the workspace printed by the command above.
EXAMPLE_ROOT=/absolute/path/to/the/printed/workspace
canopy --root "$EXAMPLE_ROOT" validate demo
canopy --root "$EXAMPLE_ROOT" run-task demo flood --dry-run
canopy --root "$EXAMPLE_ROOT" run-task demo flood
canopy --root "$EXAMPLE_ROOT" serve --port 8769
```

Open <http://127.0.0.1:8769/src/visualization/viewer/?scenario=demo>. This is a small synthetic integration example, not a London reconstruction. For a custom request, copy the linked JSON template, set the Scenario ID and replace `REPLACE_WITH_GEOMETRY_ASSET` with an exact geometry reference in that Scenario. Run `canopy --root "$EXAMPLE_ROOT" run request.json --dry-run`, then the same command without `--dry-run`.

## Results and acceptance

Each successful run exports `water_depth.npy` (TYX, metres), `velocity.npy` (TCYX, m/s, ENU), `height.npy`, `invalid.npy` and a V1.1 `manifest.json`. The initial frame is included. The shared runner retains the request, dependency versions, original source, upstream identity and diagnostics, and registers a Physics Asset derived from the exact input Geometry Asset. Cached trials and retained Assets use the normal Canopy storage paths; deleting cache does not remove retained results.

Every step rejects nonfinite solver state, a free-surface correction exceeding the upstream driver's **10 m** stop condition, or negative depth below **−1e−6 m**. These checks do not alter the computed state. Cancellation is checked between steps. Failure or cancellation prevents Asset registration.

Diagnostics record the actual fixed timestep, step count, maximum surface correction, upstream revision and checksums, and sampled water volumes. `volume_change_minus_rain_m3` includes boundary exchange and numerical error. The original collocated scheme is not the previous conservative C-grid scheme, so this quantity is reported explicitly rather than labeled `mass_balance_passed`. Passing the kernel checks does not establish physical accuracy, mass conservation or suitability for an unvalidated city case.

## Migration from version 1

Version 1 used Physics4D's separate C-grid/CG implementation. Version 2 changes the numerical method and boundary behavior. Set `method_version` to `2.0.0`, remove `cg_max`, and use the fixed `manning: 0.055`. Review the changed assumptions before rerunning a task. Old requests are rejected instead of silently selecting a different solver. The old Python implementation remains available to historical scripts; existing London results and their provenance are untouched.

## Verification and limitations

```sh
python -m unittest discover -s model/tests -p 'test_nn4pdes.py' -v
python -m unittest discover -s model/tests -v
python model/tools/check_contract.py model/tests/fixtures/contract-v1/manifest.json
python model/tools/check_repository.py
```

The numerical regression uses small synthetic fixtures generated with the upstream standalone timestep loop, independent of the Canopy loader/driver, plus tests for coordinates, instance isolation, invalid state and lifecycle behavior. It establishes adapter parity for those inputs. It does not reproduce the published Carlisle flood or rerun the 8 km London case. Historical public flood playback still displays the previously recorded results.

Memory grows with grid size and saved frames; the current adapter holds saved arrays in memory. Large runs require a measured resource budget and incremental output before scaling. Use `canopy cancel SCENARIO flood RUN_ID` or Ctrl-C to cancel. Resume is unsupported. If a run fails, inspect `run.json`, events and the numerical error; verify terrain/datum, boundaries and timestep rather than weakening checks. Do not substitute synthetic terrain for missing real data.
