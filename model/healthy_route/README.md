# Portable health-model handover

The portable path registers `healthy_route/breathing_cvae@1.0.0`: bundled trained weights and normalization, explicit cold-start state and supplied five-minute exposures/trajectory. It does not optimize routes or connect to live sensors. See [alignment and demo selection](ALIGNMENT.md).

## Run

Python 3.11+ and CPU PyTorch are required. From the checkout root:

```sh
python -m pip install -e '.[healthy-route]'
python model/tools/run_health_example.py --recorded --serve --open
```

This replays the pinned fictional record. Omit `--recorded` to compute a new fictional example in an isolated workspace under the configured cache root and opens the shared scientific Viewer on port 8772. Omit `--serve --open` for batch execution, or select `--port 8773`. Every new inference run receives a new Asset ID; it does not overwrite a recorded result. The viewer only reads results; opening a view never runs a solver. The selected recorded preview and replay command are described in ALIGNMENT.md.

## Inputs, output and limits

Copy `model/tests/fixtures/canopy/health_inference.json` and pass `--request REQUEST.json` to run your supplied inputs. Feature rows are PM2.5, air temperature, humidity, activity level, step count, walking indicator, hour sine and hour cosine. N five-minute intervals require N+1 ENU metre positions and irradiance samples. Complete parameter ranges and units are in the [Method specification](../src/canopy/models/specs/healthy_route/breathing_cvae.json).

The Method predicts breathing from zero recurrent memory and an explicit initial value. It exports breathing, latent spread, temperature, pollution, irradiance, thermal proxy, experimental health score and trajectory as standard retained layers, with complete request/environment/runtime provenance. Air temperature enters the CVAE; sunlight changes the heuristic thermal proxy/score for a fixed route. Environmental values are conditional inputs, not forecasts produced by this model.

The score and thermal proxy are experimental heuristics, not clinical risk or validated health advice. Latent spread is not calibrated total uncertainty. These caveats are visible in the scientific Viewer. Numerical completion is not physiological validation. No resume, GPU or distributed execution is supported. Cancellation is checked at each five-minute model step. Inputs are bounded to 288 intervals and 128 latent particles; CPU is sufficient for the small example.

Missing/nonfinite features and positions are rejected; missing irradiance is rejected. This complete-grid format does not represent a missing internal trajectory segment: use separately identified complete runs rather than deleting samples or joining across gaps. No missing values are converted to zeros. Samples outside the retained time range remain unavailable. Breathing/score series hold between samples; supplied trajectories interpolate linearly between complete adjacent positions. Nonphysical predictions fail rather than being clipped.

Weights load with `weights_only=True` and SHA-256 verification. Packaged tensors/scaler contain no participant observations, personal baseline or saved recurrent state. They are training-derived artifacts, not a differential-privacy guarantee. User requests and outputs containing sensitive inputs must stay private.

## Opt-in local city integration

The [current-city setup](LOCAL_CITY.md) adds registered `city_exposure`, `city_breathing` and `city_walk` Methods. It reuses the shared renderer with pinned city Geometry/fields and optional Health-only replay/interpolation. The public example uses fictional physiology inputs and packaged weights; participant-based outputs are not included. The private wave optimizer remains excluded. Canonical city fields, publication and other widgets' clocks stay unchanged. Hosted integration and independent physiological/vertical validation remain separate work.

## Verification

Run `python -m unittest discover -s model/tests -v`, `node --test visualizer/tests/test_viewer.mjs`, `python model/tools/check_contract.py model/tests/fixtures/contract-v1/manifest.json`, and `python model/tools/check_repository.py`. The health browser test checks eight layers, caveat visibility, result seeking, playback, pause, visibility, final sample and restart at desktop/mobile widths. See [VALIDATION.md](VALIDATION.md) for exact evidence and unrun private-city checks.
