# Integration validation

Verified on 22 November 2026. Executable revision: `b2389ffd21b3c582bbaaae4c75c7765cd8f93f55`, merged against upstream `666fe6450f9646007ad8968146a56299ed097e04`. This report is a documentation-only follow-up to that revision. The final submitted head and its confirmation checks are recorded in the PR description.

## Correction to earlier evidence

The earlier evidence for `ad3ceec017be266431ca6677af25adcc7e696b73` did not establish a reproducible Git checkout. The local scaler used CRLF bytes while Git stored LF; the previous clean-copy check copied working-tree bytes and missed the defect. Those handover claims are superseded by the checks below.

Packaged JSON now has `text eol=lf` attributes. The scaler SHA-256 from committed bytes is `c109bb0cc70c9db1028f9bcf8c5097d14770fb11fb38cd65b00ee7a4281cb289`. Checksum enforcement remains enabled. Regression tests check exact hashes/LF bytes and reject both corrupted weights and CRLF-converted scaler bytes.

The merge preserved current contribution/publication guidance, the transient-pollution Method registration and current city metadata. The review inventory was regenerated from merged sources. No health-specific changes were made to the public site, canonical London declaration or publication reference relative to that upstream revision.

## Environment and reproducible commands

The Linux checks used a fresh Git clone and detached checkout, not a file copy: Ubuntu 22.04 / WSL2, Python 3.12.16, CPU PyTorch 2.15.0+cpu, NumPy 2.5.5, SciPy 1.18.1, pandas 3.1.1, Shapely 2.2.0, jsonschema 4.26.0, setuptools 78.1.0 and pip 26.3. `OMP_NUM_THREADS=2` and `MKL_NUM_THREADS=2`; no inherited `PYTHONPATH`. Dependencies were already installed in the test environment; the checkout was installed with `--no-deps --no-build-isolation`. Optional `pyproj` was unavailable. No private release or retained London payloads were copied into the clone.

```sh
git clone --no-hardlinks --no-checkout /path/to/source-checkout /tmp/canopy-health-review
cd /tmp/canopy-health-review
git -c core.autocrlf=false checkout --detach b2389ffd21b3c582bbaaae4c75c7765cd8f93f55
# With the dependencies listed above installed in the active environment:
python -m pip install --no-deps --no-build-isolation -e '.[physics,healthy-route]'
python -m unittest discover -s model/tests -v
node --test visualizer/tests/test_viewer.mjs
python model/tools/check_contract.py model/tests/fixtures/contract-v1/manifest.json
python model/tools/build_review_inventory.py
python model/tools/check_repository.py
git diff --exit-code -- visualizer/guide/inventory.json
python model/tools/run_health_example.py
python -m pip wheel --no-deps --no-build-isolation . -w cache/wheels
python -m pip install --no-deps --target cache/installed-wheel cache/wheels/canopy_world-0.2.0-py3-none-any.whl
```

Installed-wheel smoke, with isolated Python and an explicit assertion that the imported package comes from the installation target:

```sh
python -I - "$(pwd)/cache/installed-wheel" <<'PY'
import sys, hashlib, json
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from healthy_route.inference import ASSETS, predict
assert ASSETS.is_relative_to(Path(sys.argv[1])), ASSETS
manifest = json.loads((ASSETS / 'manifest.json').read_bytes())
for name, expected in manifest['files'].items():
    assert hashlib.sha256((ASSETS / name).read_bytes()).hexdigest() == expected
assert b'\r' not in (ASSETS / 'scaler.json').read_bytes()
values, spread, _ = predict([[10, 22, 50, .03, 0, 1, 0, 1]], 16, 16, 42)
assert len(values) == 2 and values[0] == 16
print(values.tolist())
PY
```

## Results

| Check | Observed result |
| --- | --- |
| Unmodified Python discovery command | 141 tests run in 22.824 s; 140 passed, one optional dependency skip, no failures/errors |
| Optional skip | `test_review_facilities.FacilitiesTests.test_only_explicit_markings_are_painted_and_clipped`: missing optional projection dependency; test was not changed or disabled |
| Scientific-viewer unit tests | Six passed |
| Contract fixture | Valid, five layers and declared assets checked |
| Repository and inventory | One London Scenario, 11 Assets, 11 Methods, schema mirrors and 77 English documents; regeneration produced no inventory diff |
| Fresh Linux checkout example | Complete, retained `20261122T185354Z_260b171f49_physics@1`; eight layers, no private inputs |
| Installed wheel | Hash checks and inference passed; two predictions `[16.0, 16.51461927428889]` from the installation target |
| Fresh Windows checkout | `git -c core.autocrlf=true clone --no-hardlinks --single-branch . cache/windows-audit-final`; example completed as `20261122T185314Z_f1b6ebb99d_physics@1` with LF packaged JSON |
| Health browser behavior | Passed at 1440×1000 and 390×844, eight layers/seven charts, no page/request/HTTP errors |
| Guide browser | 11 Methods and 11 Assets at desktop/mobile widths; no captured errors |
| Diff and privacy review | Whitespace checks passed; no participant records, baseline, private histories, extra checkpoint state or local run artifacts added |

The browser checks used Windows Python 3.12.14 / CPU PyTorch 2.14.1 / NumPy 2.5.4 / pandas 3.0.1, Node 24.22.3, Puppeteer 25.12.0 and Edge 158.0.4370.33. The synthetic workspace was regenerated from the merged source. The tests assert changed breathing values, held five-minute sampling, interpolated trajectory coordinates and rendered instance position, picked units/results, advancing playback, stable pause, actual chart/object visibility, final-sample retention and restart from the first sample.

```sh
# Terminal 1: generate and serve only the disposable fictional workspace.
python model/tools/run_health_example.py --serve --port 8774
# Terminal 2: configure CHROME_PATH and PUPPETEER_MODULE for your installation.
node visualizer/tests/browser_health.cjs http://127.0.0.1:8774
# Serve the metadata checkout separately for the generated guide.
canopy --root . serve --port 8775
node visualizer/tests/browser_guide.cjs http://127.0.0.1:8775/guide/
git diff --check
```

## Completeness and overlap audit

The follow-up audit found and corrected three interface gaps: the retained compatibility UI imported a missing half-float decoder path, the private Method did not declare its trajectory output, and the private export's sample axis omitted some exact route vertices and breathing-update times. It now reuses the shared decoder, declares both output kinds and retains route turns, wait boundaries and breathing transitions. A synthetic route regression checks their actual exported values; no participant data is needed. Browser checks also import the retained module tree without activating its private planning interface.

The launcher now honors `Storage.cache_root`. A runtime-snapshot regression verifies that weights, scaler and manifest are included byte-for-byte with matching hashes. The repeated audit found no unresolved relative imports in the retained health UI and no new files byte-identical to existing upstream files. The two health Methods have different responsibilities: supplied-route inference versus private personalized optimization; they share the same CVAE architecture and scientific Viewer, and introduce no new curated city or renderer.

Compared with upstream `666fe64`, the canonical London configuration, publication reference, distribution manifest and public site have no diff. The extended replay remains an opt-in experiment. The changed-file allowlist contains no participant records, private baselines, local results or agent artifacts. The Windows clone initially hit a process-sandbox restriction; an unrestricted fresh clone and example passed without changing any tests.

Main advanced again during this audit. The final tested merge incorporates the upstream native Tube/interior transition work without altering the health Methods or scientific Viewer. All four camera-journey tests also passed (`node --test visualizer/tests/test_viewer.mjs visualizer/tests/test_camera_journey.mjs`: ten total). No hosted Tube or private-city browser validation is claimed.

## Review scope and unrun checks

The supplied independent review identified the checksum and merge blockers at the previous head. The corrections received self-review of the actual diff, merge resolutions, byte-level packaging, regression tests and browser lifecycle. Independent approval of this corrected revision remains pending; keep the PR open for another review.

The private full-city optimizer, personalized replay/re-export, retained London payload validation, nine-layer London browser audit and hosted deployment checks were **not run for this revision**. The isolated validation checkout contains neither participant histories nor the required retained city inputs. No physiological accuracy evaluation or clinical validation was performed.

This is a local model handover: `breathing_cvae` evaluates supplied trajectories and five-minute exposures from explicit cold-start state, not live sensing or route optimization. Exact personalized `wave_cvae` replay still requires private inputs. The health score and thermal proxy are heuristic; latent spread is not calibrated total uncertainty. Training-derived weights/normalization do not imply differential privacy. Requests and outputs containing sensitive inputs must stay private.

Future city integration must reuse the shared scene/renderer, surrounding buildings, coordinate frame and selected-widget timeline through a declarative Scenario preset and exact result Asset references. It needs pinned current city inputs and verified real recorded coverage; the private 16 November release and repeated 600-second fields are not the latest measured city run. The public minimal layout and read-only recorded-result boundary remain required. That follow-up and publication are not delivered by this PR.
