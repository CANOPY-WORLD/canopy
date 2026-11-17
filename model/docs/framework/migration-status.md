# Canopy capabilities and integration status

## Implemented

Canopy provides Scenario / Asset / Model / Running / Visualization interfaces, schemas and CLI commands. The four README diagrams describe these interfaces. Shared implementations and contracts are packaged in the Python wheel; scenarios and their private assets are exported as self-contained archives with `canopy pack`.

| Model | Registered Method | Implementation / inputs |
| --- | --- | --- |
| geometry | heightfield | Small synthetic heightfield and GLB for interface examples |
| geometry | rasterize_glb | Imported GLB reader and rasterizer, accumulated node transforms, explicit clipping and ground assumptions |
| solar | shadow | Physics4D ShadowNet / HorizonNet / ground_irradiance; heightfield |
| flood | shallow_water | Physics4D ShallowWater; heightfield / solid |
| wind | mac | Physics4D MAC; heightfield, retaining display slices, the full volume and native faces |
| temperature | finite_difference_numpy | Extracted Physics4D NumPy thermal-transport kernels; exact-version geometry + wind |
| temperature | finite_difference_torch | The same thermal-transport contract, implemented in PyTorch for CPU/CUDA |
| pollution | steady_tracer | Physics4D conservative finite-volume passive scalar; geometry + native MAC faces |

All eight Methods provide input ports, parameter schemas, output types, dependencies, capabilities, run guides and examples. Each implements describe/validate/prepare/execute/export. Failed or cancelled runs, and runs that fail numerical acceptance checks, do not register results. Inputs retain immutable version references, SHA-256 checksums and derived_from relationships. Source snapshots come from the actual executing packages, without substituting the metadata checkout's Git revision.

The Visualizer uses a fixed standard template. The engineering/city/laboratory presets share camera, layer, picking, timeline and legend controls; Scenarios declare the defaults. The `canopy serve` landing page provides scene entrypoints without starting solvers. Specialized panels require explicit integration through the shared widget interface; unknown panels are not executable configuration.

## Real scenarios and validation scope

- Only Imperial Corridor is shipped as a curated Scenario. Earlier separate city and synthetic workspaces were archived outside the checkout; reusable source implementations and original provenance remain.
- Imperial Corridor: retained local_viewer_20261102 physics geometry, wind, temperature, summer/winter solar and shadow, pollution and flood were imported as 7 private assets / 9 display layers. Large NPY arrays were split into individual frames without changing samples. All original float16 values, times, units and masks are preserved, with no further spatial aggregation.
- A separate real Imperial Corridor GLB computation completed a 128 m crop → 32×32 heightfield → solar chain. A ground value of 0 m for uncovered cells is an explicitly recorded assumption in the terrain-normalized frame, not a claim of GLB coverage at those samples.
- Small reference tests check flood mass conservation, MAC pressure projection, NumPy/PyTorch temperature agreement, steady-pollution residuals and mass conservation, GLB parent transforms and rejection of uncovered samples. These do not establish long-term city calibration or experimental accuracy.
- The three real scenarios and the coupled example use the same viewer. Checks cover every selected layer, final recorded frames, cameras and mobile layout. See verification.md for evidence.

### London 8 km × 8 km case

`scenario/imperial_corridor_8km/scenario.json` is the V2 entrypoint for the existing London case. Its declared bounds follow the retained source coverage rather than forcing every imported asset onto an exact 8,000 m square.

| Part | Current integration |
| --- | --- |
| Scenario | One declarative V2 scene with its own spatial metadata and asset index |
| Asset | Seven historical geometry/physics assets, plus two assets from the real-geometry crop/solar verification; no shared asset references to other scenarios |
| Model | Uses the common registry; the crop → heightfield → solar chain has run through standard Methods |
| Running | Full-domain historical computation recipes have not been migrated into Scenario.tasks; the current tasks object is empty |
| Visualization | The shared standard template with the city preset reads all nine selected historical layers |
| Detailed website | Original terrain/context, traffic and UAV presentation remain available through the compatibility viewer |

The data and visualization migration is complete for the listed layers. Reproducing every historical full-domain simulation through a single standardized task chain remains separate work. Importing recorded output does not rerun or revalidate the original solver, and display slices do not automatically supply the native 3D inputs required by coupled Methods.

## Importing recorded scenes

Imperial Corridor uses the retained local_viewer_20261102 data and its provenance report:

```sh
python model/tools/migrate_imperial_corridor.py --source /path/to/local_viewer_20261102 --report /path/to/local_physics_20261102.json
```

These commands import recorded assets. They do not rerun the original simulations or create full-domain task recipes.

## Retained compatibility components

Imported Physics4D source retains its import paths and provenance inventory. Historical scripts are listed in legacy-entrypoints.json. Research scripts that depend on specific scenes, trained checkpoints, SUMO, OpenFOAM, Blender or Triton remain compatibility entrypoints; they do not automatically become registered Methods. Their specialized environments and research parameters are outside the validation scope of the eight adapters above.

The original public Canopy Imperial Corridor website retains its URLs, detailed tiles, terrain/map context, traffic and UAV demos. Its listed physical data can now be read through the unified V2 viewer. The unified template does not yet reproduce every presentation feature of the old website. Original terrain and terrain-normalized physics geometry must remain distinct.

Full 3D fields can be retained as artifacts; the current viewer displays explicitly exported horizontal slices. Zarr, arbitrary unstructured meshes, dynamic meshes, checkpoint resume and distributed scheduling are not implemented. The small temperature and wind adapters retain complete field sequences in memory; loading display frames on demand does not make the solvers capable of unlimited streaming computation.

## Provenance and publication

physics4d-import.json pins the source revision and original per-file SHA-256 values. import-adaptations.json records subsequent changes; temperature-extraction.json separately records the extracted numerical functions. The source repository contained uncommitted research work, so the import inventory explicitly identifies a working-tree snapshot. Original copyright and citation notices are preserved; no additional rights to third-party code are granted.

Private assets, cache and machine configuration are excluded from Git and the wheel. Scenario metadata and migration tools remain in the repository. Pushing repository changes does not upload private datasets; website deployment and dataset releases are separate operations.
