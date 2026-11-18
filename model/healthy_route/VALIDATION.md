# Local integration validation

Base: CANOPY-WORLD/canopy main commit `40d7c004adb73880e1f8b4f5573161713fd23021`.
Input release: private healthy-route `2026.11.16-v2`.

## Results

- Registered Method: `healthy_route/wave_cvae@1.0.0`.
- Private input preparation and a real mapped-crossing request completed through the standard runner, payload validator and retained Asset registration.
- Successful run: `20261118T143330Z_88d376d88d`; separate private research workspace, no canonical London changes.
- Healthy-route checks: 19 passed, including boundary-sample export, CPU enforcement, candidate budgets, time-dependent branching, vehicle sweeps, stationary vehicles, signal/gap conjunction, replay seams, waiting exposure and traffic-avoiding detours.
- Full Python suite: **96 passed, zero failures/errors/skips**, in 20.921 seconds on Ubuntu 22.04 (WSL), Python 3.12.16, CPU PyTorch 2.15.0+cpu, NumPy 2.5.5, SciPy 1.18.1, pandas 3.1.1 and Shapely 2.2.0. The tracked source tree was copied to Linux temporary storage for the run.
- The initial Windows run had nine environment errors. Installing SciPy and running outside the restricted sandbox resolved five; four remaining tests required Windows symlink privileges. All four pass unchanged on Linux, including in the full suite. No tests were disabled or skipped, and no model-code change was needed to resolve these errors.
- Existing scientific viewer tests: 5 passed.
- V1 contract fixture, repository checker and diff whitespace checks passed.
- Python compilation and all retained healthy-route JavaScript module syntax checks passed.
- Generated inventory refreshed: one curated London Scenario, nine registered Methods.

The run verifies execution, contract and retention for one crossing, not full-domain performance, all departures, running physiology, or clinical/road-safety accuracy. Interactive detailed presentation remains unwired; no public browser/deployment test is claimed.

## Scope

Shared routing code, an explicit experiment profile, private-bundle preparation, Method spec/adapter, research presentation modules, tests and documentation are included. Windows path serialization now uses portable forward slashes for retained manifests, Asset references and viewer URLs.

Canonical London scenario.json, publication.json, locked data manifest and visualizer/site are byte-unchanged. The 13-hour horizon, repeated fields/traffic, estimated gaps and solar coupling belong solely to the opt-in healthy-route experiment. The integration does not publish a website or data snapshot.

Private model weights, participant observations, generated networks/fields, runtime distributions, logs and research outputs are excluded from the source changes. Retained source files are identified by SHA-256 in SOURCE.json. Any later publication of participant-derived outputs requires a separate data review.

## Repeat checks

```sh
python -X utf8 -m unittest discover -s model/tests -v
python -X utf8 model/tools/check_contract.py model/tests/fixtures/contract-v1/manifest.json
python -X utf8 model/tools/check_repository.py
node --test visualizer/tests/test_viewer.mjs
git diff --check
```

See README.md for private-input setup and the complete execution command. The full-suite Linux/WSL setup is documented in README.md. Install both physics and healthy-route dependencies and permit temporary symlinks, hard links and local test sockets. Running from native Linux storage avoids slow repeated source-snapshot operations on Windows-mounted drives.
