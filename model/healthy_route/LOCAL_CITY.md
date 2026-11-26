# Local city Health preview

This opt-in extension uses the shared city renderer, buildings, camera and selected-widget timeline. It displays a retained Health result; opening the page or Health tab never runs inference. Explicit **Calculate route** requests invoke the registered `healthy_route/city_walk` Method through a loopback-only service.

The portable fictional scientific-viewer example remains available through `run_health_example.py`. The city example below uses the packaged CVAE with explicitly **synthetic** activity/humidity and an assumed breathing reference. It does not contain or reproduce a participant's personal history. The private wave optimizer is not included.

## Install and prepare

Python 3.11+ with CPU dependencies:

```sh
python -m pip install -e '.[healthy-route]'
```

Obtain the exact public city resources listed in the current Scenario publication manifest, stored under their `viewer_path` names. The existing city download inventory describes that package; `build_local_city_health.py` verifies all files and never substitutes a different release. Obtain the matching segment/connector GeoParquet and `.state` files using [the source connection instructions](CITY_CONNECTIONS.md).

```sh
python -X utf8 model/tools/prepare_city_health.py --city-data /path/to/public-city --segments /path/to/segments.parquet --connectors /path/to/connectors.parquet --workspace cache/health-example --example
python -X utf8 visualizer/tools/build_local_city_health.py --city-data /path/to/public-city --output cache/health-viewer
python -X utf8 model/tools/serve_city_health.py --workspace cache/health-example --site cache/health-viewer --port 8826 --recorded --select-routes
```

Both output directories must be new. `--example` explicitly selects a deterministic short mapped edge and fictional physiology inputs, not a saved user's route. Alternatively supply `--origin NODE --goal NODE`; `--departure SECONDS` sets relative Health time. Exact node IDs appear in the prepared `network.json`. The bootstrap imports new immutable city/physiology Assets, calculates one result, and writes explicit request/result indexes. No contributor's existing input or result is modified.

Open `http://127.0.0.1:8826/viewer/3d/?scene=imperial_corridor_8km&health=local&pedestrian=1&play=0&lite=1`. Use `lite=0` for full detail. Select start/end points, enter a scenario start time, then explicitly calculate. Playback supports 60×, focus/follow walker, start/end markers, crossing lamps and optional stationary follow-up. Recorded playback without endpoint calculation omits `--select-routes`.

## Ownership and isolation

- Model: registered calculation adapters, sampling, route selection and physiology under `model/`.
- Scenario: explicit experiment policies and display settings under `scenario/imperial_corridor_8km/experiments/healthy_route_current_city/`.
- Asset: immutable exact-version inputs/results in the workspace's ignored `asset/data/`; see [the input contract](../../asset/docs/health-inputs.md).
- Visualizer: read-only result rendering and explicit loopback request controls under `visualizer/`.
- Cache: disposable preparation files and local static builds. They are not Pages publication artifacts.

Health's extended pollution/temperature clock and bounded environmental estimates are separate model covariates. The native city samplers, masks, data files and clocks remain unchanged. Sunlight follows its native day timeline. Other widgets do not receive Health estimates. Public launches do not load the local Health controller; this PR does not publish a hosted city demo.

Synthetic versus authorized-history inputs remain explicit. To use authorized history locally, prepare the documented physiology Asset yourself and supply its exact version in a request. No participant records, personal baseline, retained private result, or machine path ships with the example. Do not publish resulting sensitive Assets merely because code is public.

## Validation limits

The health score and thermal proxy are heuristic; latent spread is not total calibrated uncertainty. Terrain/deck mapping and modelled crossing signals have the limits in [CITY_ALIGNMENT.md](CITY_ALIGNMENT.md) and [CITY_CROSSINGS.md](CITY_CROSSINGS.md). No clinical accuracy, live sensing, traffic safety or independently surveyed vertical alignment is claimed. Required coverage gaps fail visibly rather than turning into zeros. New result indexes are selected explicitly; the server never scans for a latest result.

### Camera handoff

In the full desktop viewer, entering WASD exploration releases Health's walker-follow camera. Focus walker, Follow walker and Frame route explicitly exit WASD before moving the shared camera. Health playback pauses its elapsed-time accounting while the document is hidden, so returning to the tab does not jump across the route. Verify these combined controls with `visualizer/tests/browser_health_camera.cjs`; `CANOPY_QA_PAUSE_RENDER=1` checks control behavior with continuous GPU drawing paused and is not a frame-rate benchmark.
