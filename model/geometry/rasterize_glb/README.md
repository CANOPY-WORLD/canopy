# geometry / rasterize_glb 1.0.0

Samples static GLB triangles from the current Scenario into a computational heightfield, retaining the original display GLB and node/entity mapping. Implementation: `canopy.models.geometry.RasterizeGLB`, reusing the GLB reader and maximum-surface rasterization algorithm from Physics4D `urban_geometry.voxelization.prepare_glb`. Traversal follows the selected glTF scene, accumulates parent/child matrix/TRS transforms, then converts glTF Y-up coordinates to ENU.

The `geometry` input port requires a registered geometry asset in the current scenario containing the selected GLB layer. Animated, skinned, morphed, non-triangle and Meshopt-compressed computational inputs are explicitly rejected; Draco decoding requires DracoPy. The GLB origin must match the scenario. Relabeling coordinates does not replace a transformation. Output approximates vertical height columns above a planar datum; it does not represent a closed volume mesh, underground structures or cavities beneath overhangs.

Install with `python -m pip install -e '.[geometry]'`. Uncompressed GLB can use the base NumPy environment; Numba is an optional accelerator with additional compilation cost on first use.

| Parameter | Default | Description |
| --- | --- | --- |
| `layer_id` | `geometry` | GLB layer ID in the input asset |
| `bounds_xy_m` | Required | ENU metres `[west, south, east, north]`, within Scenario bounds |
| `cell_m` | 2 | Grid spacing in m; crop width and height must be integer multiples, with at least 3 cells per dimension |
| `max_cells` | 1,000,000 | Allocation limit; validate a small crop first |
| `ground_elevation_m` | 0 | Explicit planar datum, in Scenario ENU elevation metres |
| `uncovered_ground_m` | null | Samples not covered by triangles: null rejects the input; a number explicitly supplies a ground elevation in m |
| `obstacle_threshold_m` | 0.05 | Height above the planar datum in m at which a cell is marked solid |

```sh
canopy --root . models geometry rasterize_glb
# Edit scenario/examples/canopy/rasterize_glb.json: scenario_id, actual asset reference, layer_id, crop and datum.
canopy --root . run scenario/examples/canopy/rasterize_glb.json --dry-run
canopy --root . run scenario/examples/canopy/rasterize_glb.json
```

Outputs: original GLB, float32 `height.npy`, uint8 `solid.npy`, uint8 `coverage.npy`, `heightfield.json` and `entities.json`. `height` is relative to the planar datum. coverage=1 means coverage by source triangles; 0 records an explicit fill assumption. derived_from pins the input geometry version. Pass the new geometry reference to wind/solar/flood or other Methods requiring a heightfield.

Checks cover finite coordinates, face indexes, grid bounds, coverage, nonnegative relative heights and unique entity IDs. Building GLBs often omit the ground; choose a fill value supported by the datum or supply complete terrain, rather than treating automatic zeros as observations. Start with a small crop for large GLBs. Each primitive currently loads into memory, so the output grid limit does not cap source mesh size. Cancellation takes effect at node boundaries; resume is unsupported and rerunning creates a new asset. Reproduction retains input SHA, request, code snapshot and fill assumptions.
