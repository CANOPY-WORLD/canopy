# temperature / finite_difference_numpy and finite_difference_torch 1.0.0

One temperature interface with two computational backends. Reuses Physics4D's 3D upwind advection, isotropic diffusion, prescribed ground/roof temperature excess and heat-exchange implementation. Reusable kernels were extracted from scenario scripts into `urban_flow.solvers.temperature`; provenance and function inventory are in `docs/framework/temperature-extraction.json`. The adapter is `canopy.models.transport.Temperature`.

The `geometry` input must provide a heightfield. The `wind` input must be a physics asset **generated from that exact geometry version**, with a TCZYX float32 ENU velocity field in m/s declared by `volume_json`. Current inputs are compatible with wind/mac outputs and require matching spacing/origin and at least two uniformly spaced time samples. Historical 2D slices cannot replace 3D velocity, and no implicit resampling occurs. Each interval uses the recorded velocity at its left endpoint; output times match the original wind samples exactly.

Install with `python -m pip install -e '.[physics]'`. Running the NumPy backend only needs the base dependencies. The PyTorch backend supports execution.device=cpu/cuda and raises an error when requested CUDA is unavailable.

| Parameter | Default | Description |
| --- | --- | --- |
| `slice_index` | 3 | Horizontal Z-cell index for display; the full TZYX field is retained separately |
| `ambient_c` | 20 | Ambient and west-inlet reference temperature, °C |
| `surface_excess_c` | 5 | Ground and roof temperature excess above ambient, K |
| `surface_exchange_per_s` | 0.01 | Heat-exchange coefficient between the lowest fluid cells and the surface, s⁻¹ |
| `max_courant` | 0.15 | Advective Courant limit for adaptive substeps |
| `diffusivity_m2_s` | 0.01 | Thermal diffusivity, m²/s |

```sh
canopy --root . demo --physics wind temperature
# Alternatively, generate wind first and edit the examples with the returned geometry / wind references:
canopy --root . run examples/canopy/temperature_numpy.json --dry-run
canopy --root . run examples/canopy/temperature_numpy.json
canopy --root . run examples/canopy/temperature_torch.json
```

Outputs: a TYX scalar display slice in degC, solid-cell invalid mask, full `temperature_tzyx.npy`, `scalar_volume.json`, and actual dt/substeps/backend diagnostics. An input epoch is preserved when present. Boundary conditions follow the original method: ±0.1°C vertical variation at the west inlet, ambient temperature at the top, and zero gradient on the remaining lateral boundaries; solid roof temperatures are prescribed. This does not solve a radiative energy balance or implicitly couple weather or solar models.

Checks require finite values within the prescribed temperature range; regression tests compare both backends. Stable substeps account for advection and diffusion, but very large surface_exchange values or coarse saved intervals may still violate the range. Such results are rejected; reduce the interval or exchange coefficient. Memory scales with T×Z×Y×X because the implementation stores the full volume sequence. Use small grids first; this is not a large streaming solver. Cancellation is checked at substep boundaries; resume is unsupported. Reproduction requires identical input SHA, parameters, code and dependencies; GPU and CPU floating-point results may differ.
