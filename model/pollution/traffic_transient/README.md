# pollution / traffic_transient 1.0.0

Computes a time-dependent traffic exhaust **PMx concentration increment**, using a frozen recorded three-dimensional velocity volume and time-varying SUMO mass emissions. This is a conditional scenario, not observed air quality or total PM2.5. The frozen wind model time and traffic clock are explicitly distinct. No Health inference input is updated automatically.

## Installation and use

Python 3.11+, NumPy, SciPy (conversion), PyTorch CPU or CUDA. Install `pip install -e '.[physics]'`. CPU is appropriate for tiny fixtures; the 1000 x 1000 x 32 experiment uses CUDA. No learned weights are needed by the transport solver; the supplied wind can itself be model-derived.

```sh
python model/tools/prepare_traffic_pollution.py \
  --workspace /absolute/new/experiment-workspace \
  --wind /absolute/retained/vectors/final_volume_8m_f32.npy \
  --height /absolute/retained/geometry/height_4m_yx.npy \
  --network /absolute/retained/network.xml \
  --emissions /absolute/new/emissions.xml.gz
canopy --root /absolute/new/experiment-workspace run /absolute/new/experiment-workspace/request.json
```

The London converter requires the retained 2026-10-30 wind metadata and matching geometry manifest, verifies the geometry identity and SUMO projection, and refuses an existing destination. It crops the full [-4000,4000) m square at 8 m spacing (1000 x 1000), with 32 vertical 8 m layers. The original centre locations are not relabelled: velocities are explicitly interpolated from [-4098,-4098,-2] m. At the target top centre of 252 m the final 250 m source centre is held. The source 4 m height representation is aggregated by 2x2 maximum. Originals remain unchanged.

Run SUMO on pinned native network/routes with an explicit seed, step and emission interval. Default conversion expects all 0.1 s records during SUMO seconds [600,1200), mapped to relative transport seconds [0,600). It integrates PMx rates in mg/s into micrograms per interval; no mass is inferred from the browser replay. Emission classes must be retained and reviewed: SUMO defaults are not a calibrated London fleet. Vehicles outside the domain are accounted separately. Emissions use SUMO road z plus an assumed 1 m exhaust height. Points intersecting a coarse solid cell may be relocated horizontally to the nearest open cell at the same layer within 16 m; the audit reports displaced and unresolved mass. Any unresolved mass rejects conversion by default. The explicitly authorized `--allow-unmapped-preview` option produces an incomplete demo, retaining excluded cell locations and mass. Its output is labelled `partial_source_preview`; it must not be claimed as the complete traffic contribution.

## Computational representations

Both inputs are immutable same-Scenario Physics Assets:

- `transport_grid_json` (version 1.0.0): `arrays.velocity` is float32 CZYX ENU m/s; `arrays.fluid` is uint8 ZYX with 1=fluid. Explicit `shape_zyx`, `origin_m`, isotropic `spacing_m`, `wind_model_time_s`, and `mode=frozen_cell_center_reconstruct_project`. Array paths must be declared artifacts.
- `emissions_json` (version 1.0.0): exact matching grid and wind manifest SHA256; `pollutant=SUMO_PMx_exhaust`, `unit=ug`, `time_alignment=explicit_relative_scenario`. `times` is float64 interval boundaries from zero; int64 `offsets` indexes int64 flat ZYX `indices` and float32 `mass_ug`. Mass is integrated over each interval and spread uniformly within it. Missing timesteps are errors. Every source cell must be fluid.

Cell-centre data is **not** native MAC velocity. The solver averages to shared faces, seals solids/bottom, and pressure-projects using open side/top boundaries. It records the velocity correction and true residual, and retains the exact projected face arrays. Projection enforces discrete continuity; it does not validate the original SCALED wind against CFD or measurements.

## Parameters and outputs

| Parameter | Default | Meaning |
| --- | --- | --- |
| duration_s | 600 | Must lie within emission coverage |
| frames | 100 | Saved horizontal slices, including initial state |
| slice_index | 0 | Horizontal layer; index 0 is a 0–8 m voxel mean centred at 4 m |
| diffusivity_m2_s | 1 | Assumed constant effective mixing, not calibrated turbulence |
| dt_max_s | 1 | Further restricted by the positivity CFL/diffusion bound and interval/output boundaries |

The donor-cell finite-volume solver evolves a nonnegative concentration in µg/m³, starting from zero incremental pollution. Open inflow has zero increment; open outflow and diffusion carry mass out. Buildings and the bottom are impermeable. No chemistry, deposition or non-exhaust emissions are represented. One exported `npy_frames` slice works with the existing scalar widget; final full 3D concentration, face velocities, diagnostics, request and source snapshot are retained as artifacts. Arbitrary volume slicing is not claimed.

An 8 m cell cannot resolve breathing-height gradients or every narrow street. Do not feed this PMx increment to a model requiring calibrated total PM2.5. Background concentration and pollutant conversion need separate justified inputs.

## Acceptance, resources and cancellation

Reject invalid sources, incompatible coordinates/units, missing intervals, unstable timesteps, nonfinite/negative concentrations, or relative global mass closure error above 2e-5. The pressure solve uses relative tolerance 1e-4 and verifies true residual below 5e-4, with a 2000-iteration cap. Emission mass equals stored mass plus integrated boundary outflow within numerical tolerance. Check source relocation and wind correction diagnostics before interpreting results.

At 32 x 1000 x 1000, each float32 scalar occupies 128 MB. One hundred horizontal frames occupy 400 MB uncompressed; the final volume is 128 MB and projected faces about 392 MB. GPU workspace is several GB; projection cost depends on geometry. The implementation checkpoints every pressure iteration and transport substep. No resume or distributed execution is supported.

```sh
python -m unittest discover -s model/tests -v
node --test visualizer/tests/test_viewer.mjs
python model/tools/check_contract.py model/tests/fixtures/contract-v1/manifest.json
python model/tools/build_review_inventory.py
python model/tools/check_repository.py
```

Tests cover mass conservation, solid-wall isolation, positivity timestep rejection and pressure projection. Full-city completion and calibrated accuracy must be reported separately. Publication is a separate authorized operation.

### Main city presentation

`model/tools/export_pollution_snapshot.py RUN_PAYLOAD SOURCE_SNAPSHOT OUTPUT_SNAPSHOT`
creates a presentation-only delta for the existing Pollution widget. The viewer shares the
city renderer, buildings and bottom playback controls. Explicit layer dimensions and
southwest offsets preserve the exact 8 km result inside the 8.192 km context. All recorded
samples are retained with an independent playback clock. Float16 gzip transport records
its measured error against the native float32 slices; it does not modify the scientific
result. The invalid mask stays exact, and units remain SUMO exhaust PMx increment in
µg/m³. The 0–8 m slice is a voxel mean, not resolved breathing-height exposure.

The exporter preserves source hashes, timestamps, assumptions and solver diagnostics.
The original scientific volume and wind faces are not part of the website download.
Publication uses a separate Scenario data PR followed by a verified Canopy reference
update; generating a snapshot does not publish it.
