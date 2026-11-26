# Conditional current-city breathing and health score

`healthy_route/city_breathing@1.0.0` reuses the packaged recurrent CVAE,
explicit initialization, supplied reference band and heuristic health formula.
It evaluates the already aligned route against the pinned current city fields.
This is a local conditional scenario, not measured current-city physiology,
clinical risk or health advice. It does not optimize a route or retrain weights.

The stricter [recorded exposure preview](CITY_ALIGNMENT.md) remains unchanged.
Its missing raw values are preserved in the new result. Estimated inputs use
different names and include donor cells, coordinates, distances and policies.
No data is uploaded. The new local server still only reads completed results;
opening the Health widget never runs inference or reveals participant source files.

## Implementation and input contract

- Adapter: `model/src/canopy/models/city_physiology.py`.
- Sampling/scoring: `model/src/healthy_route/city_physiology.py`.
- Original numerical implementation: `healthy_route.conditional_runtime.Runtime`
  and `healthy_route.conditional_breathing.BreathingCosts.transition`.
- Scenario defaults: `scenario/imperial_corridor_8km/experiments/healthy_route_current_city/physiology-profile.json`.
- Example request: `model/tests/fixtures/canopy/city_breathing.json`.

Exact input ports are `exposure` (aligned Physics Asset with `city_recording`),
`city` (the same pinned current-city input Asset used by that exposure), and
`physiology` (an explicitly supplied profile Asset). See [the input contract](../../asset/docs/health-inputs.md). The public example is synthetic and cold-started; authorized history can be supplied locally as complete past rows. Packaged weights/scaler are always checksummed. Missing inputs fail; no private file or synthetic fallback is selected implicitly.
The resulting `derived_from` includes all three exact references and preserves
their complete local dependency chains. The runtime retains source, environment,
request, checksums and numerical diagnostics with every immutable result.

## Explicit scenario assumptions

The current public pollution is an exhaust PMx concentration increment. The
conditional CVAE input is **assumed background + fraction × city PMx**. Default
background 6 µg/m³ comes from the original local scenario, not a current city
measurement. Fraction 1 is an experimental assumption, not a measured particle
size conversion. The original 6–40 tracer remapping is not applied to PMx units.

Masked model inputs may use the nearest valid cell centre within an explicit
distance limit. Distance is measured from the route position, with deterministic
ties; candidates must be valid at the requested recorded time. The source mask
is unchanged. If no donor satisfies the limit, inference stops with an error
instead of filling zero or silently using a training mean. Fields are sampled
within their real spatial/time coverage and are never repeated or extrapolated.

Humidity, activity, steps, walking and time-of-day use the explicitly supplied covariate template. Its clock is independent of the city observation clock. Initial state is cold-started unless complete authorized history is explicitly supplied. The assumed reference is not clinical calibration. The public example does not reproduce any participant's private predictions.

CVAE receives **air temperature**, not the thermal proxy. The health display uses
the original heuristic `air + 6 × clamp(sunlight/800, 0, 1.5)`, provisional
18–26 °C comfort interval, pollution reference 15 µg/m³, and burdens weighted
35% pollution, 15% thermal and 50% personal breathing deviation. The score is
`100 × exp(-ln(100/90) × total burden)`. Contributions are shares of the combined
score reduction, not separate causal risks. Latent spread is not calibrated total
uncertainty. These assumptions do not become validated through successful tests.

## Parameters

All are numeric, have defaults and reject values outside their declared ranges.
Unknown parameters are rejected. The exact selected values are in the request.

| Parameter | Default | Allowed | Meaning |
| --- | --- | --- | --- |
| `assumed_background_pm25_ug_m3` | 6 | 0–100 µg/m³ | Explicit assumed background |
| `pmx_to_pm25_proxy_fraction` | 1 | 0–1 | Experimental PMx fraction |
| `max_temperature_fill_m` | 128 | 0–256 m | Maximum valid-cell donor distance |
| `max_pmx_fill_m` | 16 | 0–64 m | Maximum valid-cell donor distance |
| `solar_warming_c_per_800` | 6 | 0–15 °C | Heuristic warming at 800 W/m² |
| `breathing_history_offset_s` | 39600 | 0–86400 s | Original historical template offset |
| `followup_until_elapsed_s` | 600 | 0–600 s | Optional stationary scenario endpoint |

The full run must fit both current field and private template coverage. The model
updates every 300 seconds with the original two-second integration. A short walk
can keep its initial breathing prediction until the next model boundary. The
original 156-second route remains the default visible timeline. The checkbox
adds a clearly labelled assumed stationary follow-up at its destination through
600 seconds, enabling inspection of the 300/600-second updates. This is not
recorded extra movement, temporal repetition or validated recovery simulation.
Stationary describes position only: the historical activity template continues.

## Run locally

Use Python 3.11+ and install this checkout with its documented health dependencies
(`numpy`, `torch`, `pandas`, and `jsonschema`). Execution is CPU only; the selected
run uses two threads, fixed seed 42 and 16 latent particles. The original runtime
initializes the explicitly supplied template state; cancellation is checked between evaluation
steps. Resume is unsupported. Each invocation creates a new retained Asset.

```powershell
.\.venv\Scripts\python.exe -X utf8 model/tools/prepare_city_physiology.py --workspace cache/health-inputs --exposure ALIGNED_RECORDING_physics@1 --city PINNED_CITY_physics@1 --physiology PHYSIOLOGY_INPUT_physics@1 --profile scenario/imperial_corridor_8km/experiments/healthy_route_current_city/physiology-profile.json
.\.venv\Scripts\python.exe -X utf8 visualizer/tools/build_local_city_health.py --city-data cache/city-health --output cache/city-health-physiology
.\.venv\Scripts\python.exe -X utf8 model/tools/serve_city_health.py --workspace cache/health-inputs --site cache/city-health-physiology --port 8824 --recorded --recording-index city-physiology-preview.json
```

Replace placeholders with explicit retained references. These commands preserve
the read-only preview. The [local setup](LOCAL_CITY.md) documents endpoint controls. Sensitive source inputs and weights are never placed in the static site.
Existing prepared site directories are not overwritten; use a new output name.

The retained `recording.json` contains native raw fields, separate model inputs,
breathing/latent spread, scores, personal reference summaries, component losses,
phase labels and estimation provenance. Compatible complete fields also export
as standard scientific-Viewer time series. Physiology and scores use step
sampling; the Viewer cannot interpolate toward a future model prediction.

## Verification and limits

Run the standard Python suite, Viewer tests, contract checker on the retained
result, repository checker, and inventory/public-build checks. Focused tests cover
bounded donors, unchanged masks, time coverage, the original score equation,
five-minute update timing and sensitivity to changed environmental input.
Compare the Python scores with the original JavaScript formula on the actual
output. Browser checks cover finite scores, seeking across 300 seconds, optional
follow-up, playback/pause/restart, visibility, desktop/mobile and full city tiles.

The model is conditional on the listed assumptions. Engineering success does
not demonstrate physiological accuracy, actual participant exposure, clinical
benefit, safe road crossings or a new measured London run. Native traffic remains
outside the overlapping field clock and is not rebased or overlaid as synchronized
traffic. See the local run validation report for tested revision and exact results.
