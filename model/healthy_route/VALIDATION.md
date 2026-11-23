# Portable handover validation

Checked 23 November 2026 against main `02024b0eac94f9b593086ce4e745ec1bd3d6ee48`. Full clean-checkout validation passed at implementation commit `34f24d81f8a3894fc0757196d57bcf18008fd781`. Subsequent changes correct README encoding and record this evidence; runtime, weights and recorded payload remain identical. The PR records the final submitted commit and final rerun results separately, avoiding a self-referential commit hash in this file.

## Environment and installation

Linux: Ubuntu 22.04 under WSL2, Python 3.12.16, CPU torch 2.15.0, numpy 2.5.5, scipy 1.18.1, jsonschema 4.26.0, setuptools 78.1.0 and pip 26.3. A new detached checkout used `core.autocrlf=false`. Dependencies were already present; installation used:

```sh
python -m pip install --no-build-isolation --no-deps -e '.[physics,healthy-route]'
```

This checks package installation into that environment, not fresh dependency resolution. Windows checks used Python 3.12.14, torch 2.14.1 and numpy 2.5.4. A separate fresh clone with `core.autocrlf=true` passed both new inference and pinned replay. Python documentation tools on Windows require `-X utf8` on non-UTF-8 locales; the first unqualified invocation failed on encoding, then passed with UTF-8 enabled.

## Commands and results

```sh
python -m unittest discover -s model/tests -v
node --test visualizer/tests/test_viewer.mjs
node --test visualizer/tests/test_camera_journey.mjs
python model/tools/check_contract.py model/tests/fixtures/contract-v1/manifest.json
python model/tools/build_review_inventory.py
python model/tools/check_repository.py
git diff --exit-code -- visualizer/guide/inventory.json
python model/tools/run_health_example.py
python model/tools/run_health_example.py --recorded
```

- Python: 123 tests, 122 passed and one optional projection/geometry test skipped (`test_only_explicit_markings_are_painted_and_clipped`; SUMO review environment unavailable).
- Viewer: six tests passed; camera journey: four tests passed.
- Fixture contract, repository and regenerated inventory checks passed: one London Scenario, 11 catalog Assets and 10 Methods. The fictional recording remains a test fixture, outside that catalog.
- Fresh inference completed with bundled weights and checksum enforcement. Recorded replay preserved `20261123T130814Z_ccd01c3453_physics@1`; its empty `derived_from` chain is deliberate because all inputs are explicit fictional parameters. Tests verify replay never calls inference and rejects changed trajectory bytes.
- Windows Edge headless browser: eight layers, seven charts at widths 1440 and 390; caveats visible, seeking updates field values and rendered trajectory, play advances, pause holds, visibility changes, final sample/restart succeeds. No captured page, request or HTTP errors. Command: `node visualizer/tests/browser_health.cjs http://127.0.0.1:8774` against the local recorded workspace; `CHROME_PATH` and `PUPPETEER_MODULE` select Edge and puppeteer-core.

Wheel commands:

```sh
python -m pip wheel --no-deps --no-build-isolation . -w cache/wheels
python -m pip install --no-deps --target cache/installed-wheel cache/wheels/canopy_world-0.2.0-py3-none-any.whl
```

An isolated `python -I` process outside the checkout inserted only the installed-wheel target before importing `healthy_route.inference`. It asserted that `ASSETS` resolves inside that target, compared every manifest SHA-256 with its actual file bytes, rejected carriage returns in `scaler.json`, and ran `predict([[10,22,50,.03,0,1,0,1]],16,16,42)`. Result: `[16.0, 16.51461927428889]`. Checksum enforcement was never disabled.

## Review and limits

Self-review checked removal of the private registry entry, private-only dependencies and obsolete UI references; exact recording identity and bytes; no changes to the London Scenario configuration, current city renderer or publication; and preservation of the prior workflow at `02024b0` on `preserve/healthy-route-private-20261123`. An unintended README encoding change was corrected to the original UTF-8 text. Independent review is still required before merge.

Not run: private participant-dependent planner, private full-city optimization, alignment against pinned city Geometry/roads, vertical control-point residuals, common observation-clock validation, held-out physiological evaluation or clinical validation. No city integration or hosted deployment is claimed. The recording contains fictional inputs plus trained aggregate model artifacts, not participant records; weights are not a differential-privacy guarantee.
