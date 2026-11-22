# Conditional London 8 m preview — 22 November 2026

This is a self-review and an engineering demonstration, not measured air-quality validation. The production website and Health model inputs are unchanged.

## Run

- Run ID: `20261122T161940Z_41d85080fa`.
- Domain: ENU [-4000,4000) m east/north; [0,256) m up. Isotropic 8 m cells, 1000 x 1000 x 32.
- Frozen SCALED wind model time: 7500 s. The retained full 3D volume is explicitly interpolated and reconstructed, not treated as native MAC or a time sequence.
- SUMO 1.28.0: same network/routes/seed 42 and 0.1 s step as the retained traffic-facilities run, with a new emissions output. Transport uses recorded emissions during SUMO [600,1200) s as a conditional relative 0–600 s scenario. No collision events in this rerun.
- Network SHA256: `ccbc42e04aef68d143a5bd716249fea06eca47775dfded03a0fb9e49be07af97`.
- Routes SHA256: `8cacd0970aa06d0f3b8f08c1ad15aa33377f3d964eb29edcbef27016d5e450df`.
- 100 saved horizontal frames, including initial state; 696 internal substeps. The displayed first layer is a 0–8 m volume average, centred at 4 m.
- CPU/PyTorch 2.11.0+cu130 and RTX 5090. Runtime events from execution start through the final recorded frame span about 13 seconds; this excludes input preparation, SUMO rerun, validation, retention and video rendering.
- Self-contained output payload: 919,046,804 bytes, including 400 MB horizontal frames, final 3D concentration, projected face velocities and provenance. No full-volume time history is claimed.

## Source coverage and assumptions

The user explicitly selected an incomplete preview with missing-source disclosure. Initial 2D mapping suggested about 0.25% unresolved emissions. Preserving SUMO road height subsequently exposed below-domain roads; the final number supersedes that estimate.

- Total network exhaust PMx: 138,661,412.584 µg.
- Outside the 8 km square: 9,411,834.732 µg.
- Excluded in-domain mass: 7,876,818.172 µg, **6.09427%** of in-domain emissions. Below-domain sources account for 5.89930 percentage points; remaining conflicts account for about 0.195 percentage points. Locations and masses are retained in diagnostics.
- About **10.3533%** of in-domain mass is moved horizontally to the nearest fluid cell at the same vertical layer, within 16 m. This is an explicit coarse-grid approximation, not a claim of exact street alignment.
- Emission height is SUMO road z plus an assumed 1 m exhaust height. Negative-height roads are outside this above-ground domain; their emissions are not moved to the surface. A tunnel/portal model is needed to include their contribution correctly.
- SUMO defaults supply five HBEFA4 emission classes; these are not a measured London fleet. No brake/tyre/resuspension emissions, background PM2.5, chemistry or deposition are included. Effective diffusivity is an assumed 1 m²/s.

Missing source contributions remain unknown, not zero. All displayed concentrations are conditional partial-source increments. Do not feed them directly to Health as calibrated total PM2.5.

## Numerical checks

- Pressure projection: 325 iterations; true relative residual 1.58035e-4, max discrete divergence 7.80821e-6 s⁻¹. Face-velocity L2 correction is 6.21044% of the reconstructed field. Projection is not CFD validation of the learned wind.
- At 600 s: included source mass 121,372,759.688 µg; retained mass 120,342,189.400 µg; integrated boundary outflow 1,030,570.117 µg. Relative balance error 1.41252e-9; concentrations are finite and nonnegative.
- Python suite: 111 tests, zero failures/errors, one existing optional road-geometry test skipped because its projection/geometry dependencies are absent. Eight new checks cover advection centroid, diffusion symmetry, mass balance, impermeable walls, pressure projection, invalid source/timestep rejection and adapter export/input identity.
- Existing viewer JavaScript checks: 5 passed. Contract fixture and repository checker passed.
- Real result loaded in the shared scientific Viewer: 1/1 layers, seek to 600 s, desktop and tablet widths, no captured page/request errors. This checks loading/display, not independent numerical accuracy.

The review video shows actual saved results with a fixed logarithmic colour scale, whole-domain and South Kensington views. Grey cells are solid; magenta marks indicate omitted sources. The result is local and has not replaced the production pollution layer. Full geometry reconciliation, emissions calibration, wind/dispersion validation and numerical grid sensitivity remain future work.
