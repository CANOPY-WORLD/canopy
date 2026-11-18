# Healthy-route research model

Version `healthy_route/wave_cvae@1.0.0` adapts the 16 November V2 planner. It includes bounded destination-guided wave search, recurrent CVAE costs, walking/running timing, candidate-arrival environmental sampling, solar thermal proxy and recorded-vehicle crossing gaps. Source identities are in `SOURCE.json`.

## Installation and input preparation

Python 3.11+; CPU only. Install from the repository root:

```sh
python -m pip install -e '.[healthy-route]'
python model/tools/prepare_healthy_route.py --source /absolute/private/release --workspace /absolute/private/research-workspace
canopy --root /absolute/private/research-workspace run /absolute/private/research-workspace/request.json --dry-run
canopy --root /absolute/private/research-workspace run /absolute/private/research-workspace/request.json
```

Select the complete private `2026.11.16-v2` release explicitly. The preparation command copies only the required network, recorded fields/traffic and private breathing inputs into an isolated workspace. It pins every input hash and rejects an existing workspace. No downloads, publication or modification of the canonical London Scenario occur. The release's participant history and weights must remain private. Run outputs also contain participant-derived summaries and require review before any sharing. The input provenance records the release version; it does not claim these are newer city assets.

The prepared request selects a mapped crossing for a small CPU example. Edit `origin` and `goal` to exact network IDs. `departure_s` is seconds after 08:50; `max_minutes` includes all waits; their sum cannot exceed 46,800 seconds. `travel_mode` is `walk` (4.8 km/h) or `run` (9 km/h). `solar_day` is `20260621` or `20261221`. Unknown request parameters are rejected. The strict schema is in `../src/canopy/models/specs/healthy_route/wave_cvae.json`.

## Ownership and outputs

The opt-in [London experiment](../../scenario/imperial_corridor_8km/experiments/healthy_route_extended_replay/README.md) owns extended timing and environmental assumptions. They are not defaults for other models or the public London presentation. The adapter currently accepts the pinned London bundle representation only; the reusable numerical kernels are independent modules. Other city providers require explicit adapters and coordinate validation.

Execution reads versioned inputs, writes traffic occupancy only inside the run workspace, and exports a validated V1.1 payload. `route.json` retains timelines, waits, environmental profiles, breathing summaries, gap policy and diagnostics. A `journey_elapsed` time-series layer works with the existing scientific viewer. Detailed route presentation modules are retained separately under `visualizer/src/visualization/healthy-route`; the public demo is not wired or changed by this integration.

Missing data or weights cause an error; there is no synthetic fallback. Inputs are never overwritten. Each successful run creates a new output Asset with exact `derived_from` references. The input checksum inventory, request, dependency versions and source snapshot provide reproducibility. Cache can be deleted after output retention.

## Verification and limits

Run `python -m unittest discover -s model/tests -v`, `python model/tools/check_contract.py model/tests/fixtures/contract-v1/manifest.json`, `python model/tools/check_repository.py`, and `node --test visualizer/tests/test_viewer.mjs`. Additional healthy-route tests use tiny synthetic networks and test temporal admission, waiting and bounded path search. The private example requires the retained input release and may spend minutes constructing occupancy for thousands of crossings; memory depends on decoded solar arrays and CVAE state. No GPU, distributed execution or resume is supported. Cancellation is checked between initialization, planning and export; it cannot interrupt an active inner search. Progress events report phases, not invented percentages.

Acceptance checks enforce input hashes, coordinate identity, available physiological horizon and strictly increasing output samples. Numerical completion is not clinical or road-safety validation. The search is bounded, historical activity covariates are retained, and running physiology is uncalibrated. Repeated 600-second traffic/environment fields are conditional scenarios rather than extended measurements. Environmental gap filling and solar warming are illustrative; original source masks and bytes remain intact.
