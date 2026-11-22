# Integration validation

Updated against upstream `70688bc`. The PR adds model functionality and local scientific-viewer outputs; it does not deploy the public website.

## Runnable handover

- `healthy_route/breathing_cvae@1.0.0` includes checksum-verified tensor-only weights and fitted normalization. No participant observations, personal baseline, history timestamps, optimizer state or saved recurrent state are distributed.
- `python model/tools/run_health_example.py --serve --open` runs explicitly fictional inputs and opens eight layers in the shared scientific viewer.
- A clean Linux source copy without the private release completed inference and retained an output Asset (`20261122T000923Z_3877197709_physics@1`).
- The built wheel was installed into an isolated target and successfully loaded its packaged assets and produced predictions.
- Existing private `wave_cvae` results were re-exported and passed the payload validator with trajectory, breathing and four environmental layers. This checks export compatibility; it is not a new full-city solver validation.

## Checks

- Full Python suite: **101 passed, zero failures/errors/skips**, 21.442 seconds, Ubuntu 22.04 / Python 3.12.16 / CPU PyTorch 2.15.0+cpu. This includes the 19 routing tests and five new public-inference tests.
- New inference checks cover packaged-file allowlisting, tensor-only checkpoint structure, determinism, exposure sensitivity, checksum rejection, cancellation, coordinate bounds, contract-valid output and no direct sunlight effect on breathing.
- Headless Edge browser test: all eight layers and seven charts loaded without page/request errors; timeline seek to 1800 seconds, play/pause, visibility toggles and mobile layout passed. Command: `node visualizer/tests/browser_health.cjs`, with the local server running and `PUPPETEER_MODULE` / `CHROME_PATH` configured.
- Existing scientific-viewer JavaScript tests: five passed.
- Contract fixture, repository checker, wheel build and whitespace checks passed. Inventory contains one curated London Scenario and ten Methods.
- Initial Windows environment failures were resolved for testing by installing SciPy and using Linux for symlink privileges; no tests were disabled.

## Review and limits

Self-review covered the diff, package content, model initialization, provenance, privacy boundary and shared-viewer lifecycle. The missing-assets handover and elapsed-time-only export were addressed. The narrow-screen scientific timeline/chart layout was adjusted and browser-verified. No independent review is claimed.

The public inference path uses explicit cold-start state and supplied exposures/trajectory. It evaluates a route and does not optimize one or reproduce participant-specific history. Its health index and thermal proxy use illustrative coefficients; latent spread is not calibrated total uncertainty. Model parameters are training-derived artifacts, not a differential-privacy guarantee.

Exact personalized routing still requires authorized local history and city inputs through the separate private workflow. Real input requests and resulting predictions stay in local workspaces and may themselves be sensitive. Do not publish them by default. The hosted city demo and canonical London declarations remain unchanged relative to upstream; its optional extended-replay profile stays separate.
