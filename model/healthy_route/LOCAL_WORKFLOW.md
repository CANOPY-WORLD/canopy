# Local personalized journey workflow

This workflow preserves the historical local wave/CVAE calculation with explicitly supplied private inputs. It adds a separate local planning page and recorded inspection to the existing scientific Viewer. It is not a hosted city integration, real-time monitoring, clinical advice or evidence that a route is safe.

## Prepare and start

Install Python 3.11+ and the documented CPU dependencies from the repository root:

```sh
python -m pip install -e '.[healthy-route]'
python model/tools/prepare_healthy_route.py --source /absolute/private/2026.11.16-v2 --workspace /absolute/private/workspace
python model/tools/run_local_health.py --workspace /absolute/private/workspace --open
```

The source is the complete explicitly selected V2 release. It must contain the recorded network/fields/traffic and the authorized private physiology inputs. The setup refuses to overwrite an existing workspace and records exact input hashes. Reuse the prepared workspace on later starts. `--port 8775` changes the default port 8774. The service binds only to `127.0.0.1`; it is not intended for internet hosting or port forwarding.

On the planning page, pick start and destination from the recorded network or enter exact node IDs. Select walking/running, departure, duration and June/December sunlight. Click **Calculate and retain journey**. This explicit action invokes the registered `healthy_route/wave_cvae` Method through the shared runner. Loading the page, changing selection and opening the Viewer do not calculate anything. One calculation runs at a time. Errors remain visible; detailed failures and run diagnostics stay in the local workspace.

When calculation completes, open the recorded journey in the shared Viewer. Reopen the planner to calculate another journey; each successful run retains a new immutable Asset and exact dependency chain. The most recently completed explicit calculation becomes the workspace's selected view. Prior results remain retained. The separate read-only `canopy serve` interface is unchanged.

## Recorded inspection

The existing typed trajectory, breathing and environmental layers remain available. A declared checksummed `health_recording` artifact adds personal reference, heuristic score/component deductions, distance, waiting, selected route and an animated walker. Its controls use the shared Viewer timeline: play, pause, seek and final-sample restart. Follow camera and route visibility are local presentation controls. Charts show recorded pollution, temperature, sunlight, breathing, distance and waiting; the inspector also displays the recorded thermal proxy.

Recording happens on the model side, at one-second intervals plus original profile, route-vertex, wait, physiology and reference boundaries. Environmental values are sampled at those exact route positions and scenario times. The Viewer holds the preceding recorded inspection sample; the typed trajectory can interpolate between retained geometric samples. Inspection is not continuous sensing. There are no new learned parameters or changes to the route solver. Future results record this additional sampling and its source revision.

Missing recording fields remain JSON null and display as **Unavailable**. Chart paths break at missing samples. A malformed or discontinuous route timeline is rejected by the exporter. Existing typed environmental layers still require entirely finite arrays; the recording preserves individually available samples even when such a layer is omitted. The recording is a versioned inspection artifact, not a new V1.1 layer encoding. It contains participant-derived reference and health summaries and remains private unless separately authorized.

The score formula matches the working local display: pollution 35%, thermal comfort 15%, personal breathing deviation 50%, with the existing 1.5 deviation sensitivity and exponential score mapping. Contributions partition the score loss; they are not separate causal risks. The 18–26 °C comfort band and solar-warming proxy remain heuristic. Air temperature, rather than this proxy, enters the CVAE. Walking/running changes speed and arrival-time sampling; running-specific physiology is not calibrated.

## Boundaries and remaining city integration

The network picker and route preview use historical input coordinates. They do not imply placement against current buildings, roads or the newest London Geometry. The unresolved vertical datum and common observation clock in [ALIGNMENT.md](ALIGNMENT.md) remain unresolved. The scene is deliberately a standalone research preview.

Traffic-gap waits come from the original modelled pedestrian program plus recorded-vehicle occupancy. The inspector reports waiting; it does not present modelled phases as recorded SUMO vehicle lights. The current implementation does not yet bring surrounding buildings, current-city street-color overlays, recorded cars or signal-head rendering into this shared inspection view. Those require the pinned city provider/Geometry integration and validation described in ALIGNMENT.md, not a copy of the old whole-city renderer.

The extended-time replay remains an opt-in experiment under the existing London Scenario. Temperature/pollution and traffic repeat 600-second historical sequences; final-minute environmental blending, filled cells and solar zero extension remain labelled assumptions. These are not newly observed 13-hour fields. No canonical London configuration, public snapshot or production website is changed by this workflow.

The planning service requires a same-origin token for writes, rejects other Host/Origin values and does not serve the input bundle or run provenance. Result summaries are intentionally available to the local browser. It is a single-user local tool, not a multi-user access-control or publication service. Stop the terminal server when finished. Cancellation uses the existing runner's documented cooperative cancellation command; active numerical kernels stop only at supported checkpoints.

## Validation

See [the revision-specific validation record](LOCAL_VALIDATION.md) for actual environments, commands, results and remaining limits.

Run `python -m unittest discover -s model/tests -v`, the documented contract/repository checks, and `node --test visualizer/tests/test_viewer.mjs`. `visualizer/tests/browser_local_health.cjs` exercises an explicitly prepared workspace via its local planning service and requires Puppeteer/Chrome. It tests planning request protection, recorded inspection, seek, playback/pause, restart, follow, visibility and desktop/mobile layout. Never commit the workspace, browser captures or personal result payloads as fixtures. Synthetic recording tests cover score calculation, missing data, reference changes, waits and timeline gaps. Paired runs with authorized private inputs provide additional local parity evidence, not physiological validation.
