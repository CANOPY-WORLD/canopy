# pollution / steady_tracer 1.0.0

Freezes the final wind/mac velocity frame and solves conservative steady passive-scalar advection–diffusion. Uses the imported `urban_flow.physics.conservative_tracer.SteadyTracer`, wrapped by `canopy.models.transport.SteadyPollution`. It excludes chemical reactions and deposition. The mass unit is g, source rates are g/s, and output concentrations are g/m³.

Install with `python -m pip install -e '.[physics]'`. This Method requires SciPy and runs on CPU only. The `geometry` input provides a heightfield; `wind` must explicitly reference that geometry version in derived_from and include both `volume_json` and `mac_state_json`. The latter retains positive cell-face velocities, the fluid mask, west inlet and top boundary configuration. Cell-center display vectors cannot replace conservative face fluxes. Older wind assets lacking this representation require a new wind/mac run that exports it.

| Parameter | Default | Description |
| --- | --- | --- |
| `slice_index` | 3 | Horizontal display slice; the full ZYX field is retained separately |
| `diffusivity_m2_s` | 0.1 | Strictly positive isotropic diffusivity, m²/s |
| `sources` | `[{"cell_zyx":[3,4,4],"mass_g_s":1}]` | Nonnegative mass emissions; explicit cell indexes must lie in fluid; sources in the same cell are added |

```sh
canopy --root . demo --physics wind pollution
# For a standalone run, replace both placeholders with exact geometry and wind versions:
canopy --root . run scenario/examples/canopy/pollution.json --dry-run
canopy --root . run scenario/examples/canopy/pollution.json
```

Outputs: static YX `concentration` layer, invalid mask, full `concentration_zyx.npy` and `scalar_volume.json`. time.samples is empty; the driving wind snapshot time is recorded in diagnostics. A steady solution is not a time sequence. Both geometry and wind references are retained in derived_from.

Discretization uses conservative finite-volume donor-cell advection and impermeable solids. West/east and optional top boundaries connect to a zero background; diffusion uses a half-cell Dirichlet distance at open boundaries. Small problems use sparse LU; larger problems use ILU + BiCGSTAB. Acceptance requires a relative linear residual ≤1e-6, total emission/boundary-flux error ≤1e-6, and nonnegative concentrations within floating-point tolerance. Failed results are explicitly rejected from registration.

Memory scales with the 3D fluid-cell count and sparse-factorization fill-in; validate small grids first. Closed, disconnected cavities may produce singular matrices. The method does not silently alter emissions or boundaries. Cancellation takes effect before or after factorization/solution, without interrupting a single SciPy call; resume is unsupported. Nonfinite source fields, emissions inside solids, invalid face-velocity representations and mismatched geometry versions raise errors. Reproduction pins inputs, code snapshot, parameters and SciPy/NumPy versions.
