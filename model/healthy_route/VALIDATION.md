# Health handover and local city validation

Checked 25 November 2026. Original city runtime implementation: `a3f2f9aa12b4572fb31268d5c25c608d6ccf0163`, including main `2e83effd8f362a3e34b7e232e4ccbc352db46941`; evidence was recorded at `87849e3b4e9c1403f668ed96b42482974e1bc65e`. The widget-switch correction below is the subsequent runtime change. The PR identifies the final submitted head. Earlier 23 November validation describes the prior portable-only revision and is superseded by this record.

## Widget-switch correction, 25 November 2026

A fresh remote download of main and PR 27 combined without conflicts; its tree matched PR head `87849e3b4e9c1403f668ed96b42482974e1bc65e`. Side-by-side browser testing found that leaving Health could hide the selected Traffic/UAV model-information card: Health's bubbling click handler cleared its active state after the other widget's handler refreshed the UI. The correction clears Health in the capture phase, before the selected widget handler runs. A browser regression checks both restored cards and paused Health playback.

The exact candidate files were compared byte-for-byte with the tested local source and built browser module:

- `city-recording.mjs` SHA-256: `752bb1f1c747848a3ec7f36aee424c79762f21600ea6dcb0e71fb1eb66834745`.
- `browser_health_city.cjs` SHA-256: `8decb78b55044b1435e32d1c8d716e461ed3312e9052a25a6be9ff03b8622d90`.

After the correction, Traffic, UAV, Pollution, Wind, Sunlight, Flooding and Overview matched fresh main's clock bounds and information cards; play, pause and seek passed. Native layer/phase definitions were identical. The full-detail Health browser test passed with all 64 tiles, two later start times, reversed endpoints, finite synthetic predictions, mobile/error recovery and the new Traffic/UAV assertions, with no unexpected captured errors.

Before pushing, the Viewer suite was rerun: 69 passed, one optional skip. Contract and repository checks passed. Python, weights, schemas, Scenario policies and public data were unchanged; their earlier evidence below was retained rather than reported as a new run. This follow-up contains only the two Visualizer files and this validation record. Self-review confirmed that no personal data, generated results or local launchers are included; independent review remains outstanding.

## Environment and installation

Windows, Python 3.12.14, CPU torch 2.15.0, numpy 2.5.5, scipy 1.18.1, pandas 3.0.1, shapely 2.2.0, pyarrow 26.0.1, jsonschema 4.26.0, setuptools 84.2.1, pip 25.0.1; Node 24.22.3, Edge headless and puppeteer-core 25.12.0. Separate virtual environments reused already installed dependencies. This checks installation and execution, not a fresh dependency download/resolution. Linux filesystem checks used Python 3.12 under WSL2 with the same source revision.

```sh
python -m pip install --no-deps --no-build-isolation -e .
python -X utf8 -m unittest discover -s model/tests -v
node --test visualizer/tests/test_*.mjs
python -X utf8 model/tools/check_contract.py model/tests/fixtures/contract-v1/manifest.json
python -X utf8 model/tools/build_review_inventory.py
python -X utf8 model/tools/check_repository.py
python -X utf8 visualizer/tools/build_pages.py --refresh
git diff --check
```

The suite was also run in a fresh clone of the implementation commit, with a separate editable installation and `core.autocrlf=true`.

- Python: 162 tests; 157 passed, one optional SUMO/projection environment check skipped, and four Windows symlink setup errors (`WinError 1314`). The four unchanged tests all passed separately on Linux: `test_catalog_server.RegistryServerTests.test_public_scenario_mount_is_bounded`, `test_contract.ContractTests.test_symlink_escape`, `test_layout.DomainLayoutTests.test_public_routes_read_new_layout_without_exposing_source`, and `test_storage.StorageTests.test_reject_escaping_symlink`. This is combined platform evidence, not a claim of a wholly green Windows run.
- Viewer: 70 tests, 69 passed, one optional archived Tube timetable test skipped; no failures.
- Contract and repository checks passed: one curated London Scenario, 11 catalog Assets, 13 registered Methods and 86 English documents. Generated inventory was refreshed from merged sources.
- Pages build passed: 1,494 remote public resources, 126 frontend files, **zero bundled city payload bytes**. Native publication inputs remain pinned. Frontend download indexes were generated from committed LF bytes, avoiding unrelated Windows line-ending hash changes.

## Fresh checkout and installed wheel

```sh
python -X utf8 model/tools/run_health_example.py
python -X utf8 model/tools/run_health_example.py --recorded
python -m pip wheel --no-deps --no-build-isolation . -w cache/wheels
python -m pip install --no-deps --target cache/installed-wheel cache/wheels/canopy_world-0.2.0-py3-none-any.whl
```

Both fresh-checkout examples completed. Recorded replay preserved `20261123T130814Z_ccd01c3453_physics@1`, whose inputs are explicitly fictional and whose empty dependency chain is documented in `DEMO_RESULT.json`. Its fixture source archive was inspected: 658 source/model members, no participant CSV/Parquet or private input paths.

The installed-wheel smoke process used `python -I`, explicitly inserted only the installed-wheel directory ahead of dependencies, and asserted that inference and the conditional runtime resolved inside it. It verified every packaged inference checksum, rejected CR bytes in the scaler, loaded all three new city Method specs, and initialized 289 synthetic template states. `predict([[10,22,50,.03,0,1,0,1]],16,16,42)` returned `[16.0, 16.51461927428889]`. Wheel SHA-256: `9bb740427fd695c721e8701f560a6192898bdf9959ff6f7181035255928d1307`. Scaler SHA-256: `c109bb0cc70c9db1028f9bcf8c5097d14770fb11fb38cd65b00ee7a4281cb289`. Checksum enforcement remained enabled.

## Participant-free city preparation

The commands in [LOCAL_CITY.md](LOCAL_CITY.md) completed using the pinned public `london-complete-tube53-20261125` snapshot and matching Overture 2026-10-21.0 segment/connector inputs. `prepare_city_health.py --example` created a new disposable workspace, explicit synthetic physiology Asset and selected-route result. It did not copy a private physiology bundle or a user's saved route.

The generated initial result was `20261125T202809Z_ba0f3652ad_physics@1`, with direct dependencies:

- Geometry: `city_connections_02da72fd8378_b320c988_geometry@1`.
- City Physics: `city_connections_02da72fd8378_b320c988_physics@1`.
- Synthetic physiology: `health_physiology_5854ec9657c54226_physics@1`.

Each Asset retains its descriptors, exact upstream dependencies, hashes and preparation provenance locally. These generated Assets and public city payloads are **not committed or published**. This identifies the tested local result, not a new hosted demo input. The portable committed recording remains a separate fictional example.

## Browser behavior

Tests used the shared renderer from the merged revision, with `CANOPY_PUPPETEER` and `CANOPY_BROWSER_PATH` selecting installed tooling:

```sh
node visualizer/tests/browser_health_city.cjs
node visualizer/tests/browser_active_crossing.cjs
node visualizer/tests/browser_health.cjs http://127.0.0.1:8828
```

`CANOPY_CITY_URL` selected the prepared loopback city preview in lite and full-detail modes. The crossing test used a separately calculated synthetic 78.69 m route with two waiting crossings and an explicit request/result index. Opening either preview produced no inference POSTs.

- City lite and full detail: play advances, pause holds, seeking updates the trajectory and five-minute prediction, fractional final sample reaches Arrived, restart succeeds, visibility changes, 60x works, controls fit 390 px mobile. Full detail loaded all 64 tiles without errors.
- Explicit endpoint reversal and start times 12:50:37 / 18:50:37 produced new results at relative times 14,437 / 36,037 seconds. All checked samples had finite breathing/score, strictly increasing times, and native pollution/temperature remained null beyond native coverage while separately labelled Health inputs supplied estimates. Tests assert the native layer definitions and phase clocks are unchanged. Switching to Pollution restored its native timeline; an ordinary city launch requested no Health API and mounted no Health controls.
- A deliberate HTTP 503 showed the error and hid stale results; restoring the saved preview worked. No unexpected captured browser/HTTP errors.
- Crossing lamps remained fixed beside the road across seek, playback, camera and viewport changes. Red WAIT changed to green WALK; active lamps were 96 screen pixels while other heads retained their normal dimensions. Focus, transition to the next crossing, mobile visibility and route visibility passed. No POSTs occurred during playback.
- Fresh-checkout scientific Viewer: eight layers, seven charts, desktop/mobile, seek/result/trajectory/render-matrix/pick, advance/pause, visibility, final sample and restart all passed without captured errors.
- Latest-main navigation and model-card assertions passed. Their test launchers were copied to disposable cache and only the hard-coded Linux Chrome executable was replaced with Windows Edge; repository implementations/assertions were unchanged.

Model tests cover source connector topology, disconnected roads, masks, valid zero values, bounded donor selection, missing-input failure, Health-only temporal replay, sunlight's separate day clock, crossing wait accounting, service privacy and fixed-input request boundaries. This does not certify every possible road/start-time combination.

## Review and limits

Self-review checked the four-domain split, exact Asset inputs, preserved current contribution guidance, minimal shared-viewer hooks, absence of the private wave optimizer, and exclusion of participant files, private results, local launchers and assistant artifacts. No contributor's city field/clock/mask is overwritten. A byte comparison confirmed that all 66 inventoried source files in the user's working local checkout remained unchanged.

The city preview is an opt-in local research scenario, not a hosted or validated city result. Spatial mapping is tied to pinned source geometry and declared terrain/deck conventions, not independent surveyed vertical control. The Health clock is an illustrative scenario mapping: repeated short pollution/temperature sequences and traffic clips are not new measured coverage; pedestrian signals are model assumptions distinct from recorded vehicle signals. Activity/humidity and the assumed breathing reference in the public example are synthetic, so its scores do not reproduce a person's private results.

Not run: participant-dependent/private optimization, reproduction of an individual's predictions, independent vertical control-point survey, common measured observation-clock validation, held-out physiological evaluation or clinical validation. The score and thermal proxy remain heuristic and latent spread is not calibrated total uncertainty. Trained weights are not a differential-privacy guarantee. Independent review remains required; this work does not merge or deploy the PR.

## Maintainer camera-handoff follow-up (26 November 2026)

On top of submitted head `d3debb59dc853f60595ffe27a9dbd3c5d8730c47`, fixed Health follow/focus versus desktop WASD ownership and hidden-tab elapsed-time accounting. The local full-detail browser regression (`browser_health_camera.cjs`) passed handoff in both directions, route focus, movement, background pause/resume and Overview exit. Continuous GPU drawing was paused for that control test; it is not a frame-rate measurement.

A fresh isolated Linux environment ran all 162 Python tests: 161 passed, one skipped. Viewer tests: 69 passed, one optional skip. Repository/contract checks and Pages build passed. Prepared the pinned city and Overture resources, and computed a new synthetic-input South Kensington walk of 318.66 m with four modelled crossings; no participant inputs were used. Local preview artifacts and the retained run are not part of the PR or a public dataset deployment. Self-review covered the actual camera changes and generated frontend indexes; scientific model code is unchanged.
