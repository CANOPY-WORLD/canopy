# Local workflow validation — 25 November 2026

Executable revision: `fec7e086f73b1bf887bcafc8561149a146cd4060`, based on current main `ba8e1da99a3f43afc4c1dbfeba06451ac137ac1b`. This evidence file is a documentation-only follow-up. The final PR head includes this evidence; no implementation changes follow the tested executable revision.

## Results

| Check | Result |
| --- | --- |
| Fresh Linux Git clone of exact executable revision | 148 Python tests: 147 passed, one optional projection/geometry test skipped |
| Fresh-checkout public health example | Completed and retained a valid result using packaged weights; no private inputs supplied |
| Fixture contract and repository checker | Passed; one curated London Scenario, 11 Assets, 11 Methods |
| Shared Viewer unit tests | Six passed |
| New private local planning/browser path | Small pinned crossing calculated and retained; desktop 1440×1000 and mobile 390×844 passed |
| Browser behavior | Actual trajectory position changes on seeking; play advances; pause holds; final sample/restart works; follow moves camera; route visibility changes; speed selection advances at the chosen multiplier |
| Browser failures | Missing recording and checksum-corrupt recording produce visible errors; no captured unexpected page exceptions |
| Local service boundary | Synthetic tests check GET does not compute, same-origin token is required for POST, other Host/Origin values are rejected, private input/provenance paths are blocked |
| Private paired planner checks | Walking at departure 0 and running at departure 540 s: original working app and packaged Method code produced exactly equal selected edge keys, timeline, environmental profile, breathing profile and personal reference arrays |
| Score formula parity | 36 synthetic cases against the original JavaScript formula; maximum absolute score/contribution difference 1.43e-14 |
| Installed wheel smoke | Separate Windows environment: packaged weight/scaler checksums, finite inference, recording helper and local service imports passed |
| Generated inventory | Regenerated and checked; semantic inventory unchanged, original committed bytes preserved |
| Windows Python suite | 145 tests before adding three service boundary tests: 140 passed, four existing symlink privilege errors, one optional skip. The final 148-test suite passed in Linux as above |

The browser checks exposed an endpoint rounding bug: an HTML slider could produce a number just beyond the exact final timestamp. The shared Viewer now clamps requested time to the actual bounds. Strong assertions exercise the resulting visible position and camera state, not only button text.

## Environments and commands

Windows: Python 3.12.14, PyTorch 2.15.0+cpu, NumPy 2.3.5; Microsoft Edge through Puppeteer. An isolated editable environment uses the preinstalled scientific dependencies from the earlier local audit. The wheel was installed into a separate environment using those same preinstalled dependencies. This is not a clean dependency-resolution test. The wheel was built and tested at the final executable revision above. Wheel SHA-256: `dbd18e98e6d19453407a05de9a40e65a3d7c608b0edac41f432efd85f0601838`.

Linux/WSL: Python 3.12.16, PyTorch 2.15.0+cpu, NumPy 2.5.5; existing dependencies, fresh Git clone with `core.autocrlf=false`, detached exact executable revision, `PYTHONPATH` set to that clone's `model/src`, `OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`. No participant inputs were copied into the fresh checkout.

```sh
python -m unittest discover -s model/tests -v
python model/tools/run_health_example.py
python model/tools/check_contract.py model/tests/fixtures/contract-v1/manifest.json
python model/tools/check_repository.py
python model/tools/build_review_inventory.py --check
node --test visualizer/tests/test_viewer.mjs

# Authorized private workspace only; source inputs and results stay outside Git:
python model/tools/prepare_healthy_route.py --source PRIVATE_V2 --workspace PRIVATE_WORKSPACE
python model/tools/run_local_health.py --workspace PRIVATE_WORKSPACE --port 8785
# Set PUPPETEER_MODULE and CHROME_PATH for the installed local browser:
node visualizer/tests/browser_local_health.cjs http://127.0.0.1:8785

python -m pip wheel --no-deps --no-build-isolation . --wheel-dir WHEEL_DIR
# Install the resulting wheel in a separate environment; call
# healthy_route.inference.predict with the fictional request parameters.
```

The private parity check used the original `canopy-pedestrian-integration-20261111` source, the same authorized original inputs and two CPU threads for both implementations. It did not compare different city datasets. Personal values, screenshots and private run payloads are excluded from this evidence and the public diff.

## Review and remaining limits

Self-review performed; no independent review is claimed. Review covered the changed files, explicit execution boundary, private-path handling, immutable result retention, unchanged planner logic, recording formula, unavailable values, timeline endpoints and preservation of the current public site. The diff contains code, documentation and tests only; no private participant data, generated runs, working-environment files or public-city payloads.

This is local workflow integration, not full parity with the old whole-city display. Current-city Geometry/vertical alignment, common observation clock, surrounding buildings, current traffic provider, street-color overlays and signal-head rendering are not implemented or validated here. The original local application remains unchanged. The private full-city optimizer was not rerun; only the small stated paired requests were exercised. No held-out physiological evaluation or clinical validation was run. Keep this PR open for review; no merge, public-data publication or website deployment is authorized by these checks.
