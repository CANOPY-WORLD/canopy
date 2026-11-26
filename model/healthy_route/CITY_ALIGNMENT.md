# Current city alignment, local recorded preview

The separate [conditional physiology extension](CITY_PHYSIOLOGY.md) reuses the
packaged breathing model with explicit estimated inputs. This strict preview
continues to show unsupported physiological values as unavailable.

`healthy_route/city_exposure@1.0.0` evaluates an existing saved route against a
pinned city presentation snapshot. It does not search for a route, run CVAE,
or infer missing health inputs. The original local comparison remains available.
Nothing in this workflow publishes data or changes GitHub.

Implementation: `model/src/healthy_route/city_alignment.py` and
`model/src/canopy/models/city_exposure.py`. The standard Method lifecycle retains
the result, runtime source snapshot, environment, input references and diagnostics.
The browser only reads that retained result; no computation is triggered by
opening the Health widget. The current scientific Viewer can also inspect its
standard trajectory and complete time-series layers.

## Inputs and preparation

Use the checkout's Python environment installed with `pip install -e .` and the
existing health dependencies needed to regenerate the walking network (`numpy`,
`shapely`). Preparation checks every public file against the locked Scenario
publication manifest. The isolated local workspace must already contain the
source route Asset and its complete private dependency chain.

```powershell
.\.venv\Scripts\python.exe -X utf8 model/tools/prepare_city_alignment.py --city-data cache/city-health --workspace cache/health-inputs --recording RECORDED_ROUTE_physics@1
.\.venv\Scripts\python.exe -X utf8 visualizer/tools/build_local_city_health.py --city-data cache/city-health --output cache/city-health-aligned
.\.venv\Scripts\python.exe -X utf8 model/tools/serve_city_health.py --workspace cache/health-inputs --site cache/city-health-aligned --port 8822 --recorded
```

Replace the recording placeholder with an exact saved route Asset, selected
explicitly; the tool does not select `latest`. Preparation refuses an existing
staging directory. An existing prepared input can be rerun using its saved
`city-alignment-request.json` through `canopy.running.runner.run`; each result is
immutable. The Method has no adjustable parameters: the source record supplies
trajectory and timing, and the pinned input bundle declares field/time policies.
The request schema example is `model/tests/fixtures/canopy/city_exposure.json`.

Geometry and city field inputs must refer to the same verified snapshot bundle.
The result's `derived_from` contains both exact city Assets and the original
recorded route. The original route's private dependencies are neither served nor
published. Full public snapshot bytes and their hashes are retained as input
artifacts, including detailed tiles, terrain, roads, signal/traffic records and
environmental transports. These public presentation files are not relabelled as
the original full-precision scientific run or a new measured city observation.

## Coordinates and clock

The local current-city snapshot is `london-complete-tube53-20261125`, repository
revision `1ef461432127e66934c100cab1af7d9d14cbc068`, locked manifest SHA-256
`a51b797d186edc975e1f68ab46414687fbf7f4c4dea873575ec3e0d1cb535e57`.
The horizontal origin is longitude -0.200473, latitude 51.506427, true north;
axes are right-handed ENU in metres. Every selected edge and XY vertex must
match the regenerated current network within 0.00001 m. No proximity snapping
or arbitrary map offsets are allowed. Unmatched edges or trajectory gaps fail
preparation rather than creating a line across the gap.

Original trajectory Z is not trusted as a datum conversion. Current ground
segments use the pinned terrain grid; supported elevated paths use matched
native road/deck heights from the network builder. The retained trajectory Z is
height above that pinned local ground. The prepared city position is
`[east, terrain_height + Z, -north]`; the browser adds only a declared 0.15 m
visibility lift. Control points record native height, ground height, above-ground
height, XY matching residuals and reconstruction residuals. These are internal
scene-alignment checks, not independent survey accuracy measurements. Terrarium
height datum conversion is undocumented; no certified ODN/ellipsoidal accuracy
claim is made. Canonical Scenario metadata is unchanged.

The recorded route retains its source departure seconds and waits. Temperature
and PMx are sampled at their actual relative simulation time within 0–600 s;
they are not a common observed UTC clock. Solar sampling explicitly selects
21 June clear-sky time `31800 + t` seconds since midnight BST (08:50 BST at
relative t=0, 07:50 UTC). This is a conditional scenario mapping. Native traffic
covers 680–720.9 s and has no overlap with the field clip. It is not rebased,
repeated or shown as synchronized traffic. Neither generated pedestrian signal
states nor vehicle signals are displayed by the Health widget. Source route
waits remain historical planner assumptions, not current vehicle-clearance checks.

## Sampling and scientific limits

PMx has a 1000×1000 grid, 8 m cells, lower corner (-4000,-4000), log1p
quantization and code 255 missing. Decode as `reference * expm1(code*scale+offset)`.
It is a partial traffic exhaust concentration increment, not total PM2.5, sampled
from a 4 m voxel-mean slice. Temperature uses the 32 m grid's 8 m slice. Solar is
an 8 m presentation grid. The bundle preserves exact masks, quantization,
spatial origins and recorded sample times. Sampling uses the containing cell and
linear interpolation in time only within recorded coverage. There is no spatial
filling, temporal repeat, endpoint extrapolation or breathing-height adjustment.

Missing fields stay `null` and visibly unavailable. Plot paths break at missing
values. Partial series remain in `recording.json`; the scientific protocol's
time-series layer is exported only when that whole series is finite. Breathing
and the combined Health score remain unavailable because compatible total PM2.5
and synchronized activity/humidity inputs are absent. No PMx proxy is used.
Historical thermal and Health scores remain heuristic; latent spread is not
calibrated total uncertainty. Engineering tests do not establish physiology.

## Validation and operation

Run `python -m unittest discover -s model/tests -v`,
`node --test visualizer/tests/test_city_recording.mjs`, the standard Viewer tests,
contract checker and repository checker. Numerical tests check log decoding,
the shifted grid, masks, boundary times, missing segments and native height
conversion. Browser checks must exercise full detail loading, single shared
canvas, playback advance/pause, seeking, visibility, final sample/restart,
mobile layout and network failure. See the local alignment validation record
for the actual tested revision and results.

Inputs consume roughly 300 MB plus retained copies and run provenance. Sampling
holds at most twelve field frames in its cache. Cancellation is cooperative at
route events and samples; resume is unsupported. Failures such as checksum
mismatch, changed geometry, absent route segments or unpinned inputs are explicit
errors. A recording outside a field's time/domain remains valid but that field
is unavailable. This is a local recorded research preview, not a hosted city
demo, live monitoring, clinical advice or a new full-city optimization run.
