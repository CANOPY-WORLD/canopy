# Health model and local visualization

## Run from a fresh checkout

The repository now includes the trained CVAE weights and fitted normalization parameters in `model/src/healthy_route/assets/`, and installs them in the Python wheel. No participant CSV, personal baseline, history timestamps or saved recurrent state is included. The runnable example needs neither the old private release nor the London dataset.

```sh
python -m pip install -e '.[healthy-route]'
python model/tools/run_health_example.py --serve --open
```

The command runs the model first, retains its results, selects all eight layers and opens the existing shared local scientific viewer on port 8772. It creates a separate disposable workspace, leaving canonical London and the hosted web demo unchanged. Use `--port 8773` if necessary. Omit `--serve --open` for batch execution; the command prints the workspace and a `canopy serve` command. No solver runs just because a view is opened.

The viewer displays breathing rate, latent spread, air temperature, pollution, irradiance, thermal proxy, experimental health score and a moving trajectory. Its shared timeline supports pause, play and seek; breathing and scores are held between five-minute samples. No new renderer or private HTTP planning API is required.

## Inputs and interpretation

`healthy_route/breathing_cvae@1.0.0` accepts explicit five-minute exposure/activity inputs and a supplied trajectory. Copy `model/tests/fixtures/canopy/health_inference.json`, edit it, and pass `--request /path/to/request.json` to the launcher. It evaluates that trajectory; it does not optimize a new route. Future environments must be supplied by the caller and are conditional scenarios, not predictions made by the CVAE.

Each feature row contains PM2.5, air temperature, humidity, activity level, step count, walking indicator, hour sine and hour cosine, in that order. N intervals require N+1 trajectory and irradiance samples. The initial breathing value, particle count, random seed and score-reference parameters are explicit. Full parameter bounds and defaults are in the Method specification. The shipped example is fictional, including its reference range and initial state; it is not an anonymized participant trajectory or a reproduction of the personalized experiment.

Cold-start inference uses zero recurrent memory and the supplied initial breathing value. It deliberately does not load observed participant history. Therefore its predictions are not equivalent to the earlier personalized run. The reference score is an illustrative index, not calibrated health risk. Air temperature enters the CVAE; sunlight changes only the heuristic thermal proxy and score for a fixed trajectory. Latent spread is not calibrated total uncertainty. Predictions outside physical validity cause an error rather than silent clipping.

Weights are verified against SHA-256 before inference and loaded with `weights_only=True`. The checkpoint contains model tensors only; the scaler contains fitted aggregate model parameters. These are training-derived model artifacts, not a differential-privacy guarantee. The user's supplied request and resulting predictions are retained locally for provenance; treat outputs as private if supplying sensitive inputs. No observations should be committed or added to the public package.

## Connect to a real Scenario

The Method uses the standard `describe/validate/prepare/execute/export` lifecycle. Supply an actual same-frame trajectory and exposures in a request for an existing Scenario, run `canopy --root WORKSPACE run REQUEST.json`, then select returned Asset references with `canopy --root WORKSPACE view SCENARIO ASSET_REFERENCE`. Serve that workspace normally. Outputs use existing `time_series` and `trajectories` representations, so the local viewer reads the model's results directly.

The original `wave_cvae` route optimizer remains available for authorized researchers with their private history and city bundle; it is not silently replaced by cold-start inference. Its export now includes trajectory, breathing and available environmental layers as well as the complete route artifact. Exact personalized replay still requires private inputs. The public runnable path above solves the repository-only handover without publishing them.

The private route export preserves every route bend, waiting boundary and breathing-update timestamp in its shared sample axis; the complete original route remains an artifact. Environmental layers with missing values are omitted rather than filled for display, while their original missing values remain in `route.json`. Retained compatibility UI modules are inactive and reuse the shared half-float decoder; they do not replace the scientific Viewer or add a public planning API. The example launcher honors the configured cache root.

## Future city presentation

This PR delivers the local model handover, not a hosted city health widget or live sensing. A future city integration must use the shared Canopy renderer and surrounding buildings, a declarative Scenario preset, exact retained result Asset references and the selected-widget timeline. Opening that widget must only load recorded results. Keep the public widget/canvas/playback layout minimal and scientific inspection in the local Viewer or supported details host.

That integration needs pinned current city geometry and environmental/traffic inputs, verified coordinate transforms and actual recorded time coverage. The private 16 November release and repeated 600-second fields are historical experimental inputs, not the latest measured city run. Record any resampling or extrapolation as a derived transformation with explicit provenance and limits. Engineering tests do not establish physiological accuracy; stronger claims require an authorized held-out evaluation, baseline comparison and reported errors.

# Private personalized route workflow

Version `healthy_route/wave_cvae@1.0.0` adapts the 16 November V2 planner. It includes bounded destination-guided wave search, recurrent CVAE costs, walking/running timing, candidate-arrival environmental sampling, solar thermal proxy and recorded-vehicle crossing gaps. Source identities are in `SOURCE.json`.

## Installation and input preparation

Python 3.11+; CPU only. Install from the repository root:

```sh
python -m pip install -e '.[healthy-route]'
python model/tools/prepare_healthy_route.py --source /absolute/private/release --workspace /absolute/private/research-workspace
canopy --root /absolute/private/research-workspace run /absolute/private/research-workspace/request.json --dry-run
canopy --root /absolute/private/research-workspace run /absolute/private/research-workspace/request.json
```

Select the complete private `2026.11.16-v2` release explicitly. The preparation command copies only the required network, recorded fields/traffic and private breathing inputs into an isolated workspace. It pins every input hash and rejects an existing workspace. No downloads, publication or modification of the canonical London Scenario occur. Keep the original release bundle and participant history private; only the separately packaged tensor-only weights and aggregate normalization described above are distributed publicly. Run outputs also contain participant-derived summaries and require review before any sharing. The input provenance records the release version; it does not claim these are newer city assets.

The prepared request selects a mapped crossing for a small CPU example. Edit `origin` and `goal` to exact network IDs. `departure_s` is seconds after 08:50; `max_minutes` includes all waits; their sum cannot exceed 46,800 seconds. `travel_mode` is `walk` (4.8 km/h) or `run` (9 km/h). `solar_day` is `20260621` or `20261221`. Unknown request parameters are rejected. The strict schema is in `../src/canopy/models/specs/healthy_route/wave_cvae.json`.

## Ownership and outputs

The opt-in [London experiment](../../scenario/imperial_corridor_8km/experiments/healthy_route_extended_replay/README.md) owns extended timing and environmental assumptions. They are not defaults for other models or the public London presentation. The adapter currently accepts the pinned London bundle representation only; the reusable numerical kernels are independent modules. Other city providers require explicit adapters and coordinate validation.

Execution reads versioned inputs, writes traffic occupancy only inside the run workspace, and exports a validated V1.1 payload. `route.json` retains timelines, waits, environmental profiles, breathing summaries, gap policy and diagnostics. The existing scientific viewer reads the elapsed-time series, trajectory, breathing and available environmental layers. Detailed route presentation modules are retained separately under `visualizer/src/visualization/healthy-route`; the public demo is not wired or changed by this integration.

Missing data or weights cause an error; there is no synthetic fallback. Inputs are never overwritten. Each successful run creates a new output Asset with exact `derived_from` references. The input checksum inventory, request, dependency versions and source snapshot provide reproducibility. Cache can be deleted after output retention.

## Verification and limits

Run `python -m unittest discover -s model/tests -v`, `python model/tools/check_contract.py model/tests/fixtures/contract-v1/manifest.json`, `python model/tools/check_repository.py`, and `node --test visualizer/tests/test_viewer.mjs`. Additional healthy-route tests use tiny synthetic networks and test temporal admission, waiting and bounded path search. The private example requires the retained input release and may spend minutes constructing occupancy for thousands of crossings; memory depends on decoded solar arrays and CVAE state. No GPU, distributed execution or resume is supported. Cancellation is checked between initialization, planning and export; it cannot interrupt an active inner search. Progress events report phases, not invented percentages.

Acceptance checks enforce input hashes, coordinate identity, available physiological horizon and strictly increasing output samples. Numerical completion is not clinical or road-safety validation. The search is bounded, historical activity covariates are retained, and running physiology is uncalibrated. Repeated 600-second traffic/environment fields are conditional scenarios rather than extended measurements. Environmental gap filling and solar warming are illustrative; original source masks and bytes remain intact.

## Full-suite test environment

The full suite exercises real local HTTP sockets, hard links and symbolic-link escape rejection. Run it outside a restricted process sandbox. On Windows, symlink tests require Developer Mode or an appropriately privileged process; use Linux/WSL when those privileges are unavailable. Do not disable these tests to obtain a passing result.

Use Python 3.12 and install both physics and healthy-route dependencies, including SciPy:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -e '.[physics,healthy-route]'
.venv/bin/python -m unittest discover -s model/tests -v
```

CPU PyTorch is sufficient. Local research data is not needed for the automated suite; the full mapped-crossing example separately requires the private bundle described above.
