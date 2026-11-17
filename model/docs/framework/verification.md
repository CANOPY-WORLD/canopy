# Verification record

## Four-domain organization review — 2026-11-17

The tracked root now contains only `model/`, `scenario/`, `asset/` and `visualizer/`, plus repository metadata files. The root README presents one overview SVG and directory navigation; internal diagrams, run guides and scene details live below those domains. Earlier records below describe checks before this relocation and retain their historical command paths.

| Check | Result and scope |
| --- | --- |
| Python | 69 passed: all 63 existing checks plus 6 checks for new metadata/data roots, external storage, cache isolation, source resolution, schema mirrors and public HTTP mounts |
| JavaScript | All 5 viewer unit checks passed; both V1 and V1.1 contract examples validated |
| Synthetic browser | 6/6 layers; controls and desktop/mobile layout; no page or HTTP errors |
| Real and coupled browsers | South Kensington 3/3, White City 3/3, Imperial Corridor 9/9, coupled example 4/4; final recorded samples available, with no page or HTTP errors |
| London retained data | All 9 registered Assets passed payload validation after local storage relocation; historical full-domain task recipes remain unmigrated |
| Installation | Wheel built from both source roots; isolated installed packages discovered all 8 Methods and ran geometry plus all five physics model types in a metadata workspace containing no source code |
| Scenario archive | Wheel-generated example: 6 Assets, 8 display layers and 74 archive files; archive retains `project/demo/...` members and excludes cache |
| Diagrams | Overview SVG inspected at 1440 px and 900 px; all four child README Mermaid diagrams rendered successfully |
| Documentation | 61 tracked Markdown/HTML files checked: English text and no broken local Markdown links |
| Source retention | All 661 imported inventory files resolve through the relocation map; original hashes remain unchanged in the source inventory |
| Publication scope | No private `asset/data/`, cache or storage configuration staged; existing public website files were relocated with unchanged content |

Evidence is in `cache/qa/layout-python-tests.log`, `layout-new-tests.log`, `layout-demo-browser.json`, `layout-scenarios-browser.json`, `layout-london-validation.json`, `layout-wheel-smoke.json`, `layout-docs-audit.json` and `domain-diagrams/`. The test archive is `cache/qa/layout-wheel-scenario.tar.gz`. These local artifacts are excluded from Git.

## Initial framework verification

Verification date: 2026-11-17. Changes were made in the separate Canopy checkout; the source Physics4D checkout was not modified.

| Check | Result and actual scope |
| --- | --- |
| Python | 63 passed: 43 imported protocol checks + 20 Canopy lifecycle, ownership, checksum, cancellation, failure, archive, GLB transform, coupling and numerical checks |
| JavaScript | 5 passed: ENU conversion, time bounds/interpolation, static layers, path isolation and sparse-trajectory entity lifecycle |
| V1 example | `python3 tools/check_contract.py examples/contract-v1/manifest.json` passed, with 5 layers |
| README diagrams | All 4 Mermaid diagrams rendered in a real browser; screenshots and SVGs are in cache/qa/readme-diagrams |
| Synthetic viewer | 6/6 layers; visibility, time, play/pause and camera controls; no horizontal overflow, page errors or network errors at 1440×1000 and 390×844 |
| Scenario landing page | Shared entrypoint for real and synthetic scenes; layout passed at 1440×1000 / 390×844; data loading is read-only |
| Real-scenario viewer | South Kensington 3/3, White City 3/3, Imperial Corridor 9/9; all final recorded frames available, with no page or HTTP errors |
| Coupled viewer | geometry → wind → temperature / pollution, 4/4 layers; temperature preserves wind timestamps, and steady pollution is a static layer |
| Imperial data preservation | Compared the GLB, 8 array groups and 806 individual NPY frames in 7 historical assets with their sources: identical values, dtype, timestamps and masks; no spatial resampling |
| Real-geometry computation | Imperial GLB node transforms → 128×128 m crop, 4 m spacing, 32×32 heightfield → solar; both runs completed; 458 uncovered samples explicitly used the recorded 0 m planar ground assumption |
| Installation package | Wheel built successfully, approximately 1.9 MB; a separate installation, invoked outside the repository, discovered all 8 Methods, ran geometry and five physics model types, and validated 6 assets; schemas loaded from the wheel |
| Scenario package | Independent wheel outputs packaged as dist/canopy-demo-scenario-v2.tar.gz: 74 files, approximately 8.3 MB; includes Scenario, all Assets, requests and provenance, and excludes cache |
| Provenance | No imported files missing from physics4d-import.json; adaptation inventory updated; both copies of the V2 schemas match |

Numerical checks cover rainfall mass conservation in a flat closed basin, native MAC pressure-projection acceptance, NumPy/PyTorch temperature agreement, and steady-pollution nonnegativity, linear residual and mass conservation. Provenance tests confirm that run snapshots include packages resolved by the executing interpreter, even when the metadata workspace contains no source code.

Reproducible logs and screenshots are in `cache/qa/`: `python-tests.log`, `javascript-tests.log`, `scenarios-browser.json`, `corridor-preservation.json`, `real-glb-run.json` and `wheel-smoke.json`. Build outputs are in `dist/`; they are not published automatically.

Long-running city wind, RANS, traffic and coupled thermal-environment research simulations were not rerun. External software and data requirements of every historical compatibility entrypoint were not validated. These tests verify the implementation and listed numerical properties; they do not establish city prediction accuracy. Full 3D fields remain artifacts, while the unified viewer displays exported horizontal slices. Detailed maps, traffic and UAV presentation retain compatibility entrypoints; see migration-status.md.

## English documentation review

The documentation review on 2026-11-17 translated 21 Markdown and HTML files and added an English-only documentation requirement to AGENTS.md. A scan of all 62 tracked documentation/HTML files, plus 40 JSON contracts, examples and scenario descriptors, found no remaining Chinese text. Markdown command blocks and link targets were compared against the pre-translation copies. Both HTML method pages retain their element structure, equations and every numeric value.

All four English README diagrams rendered successfully. Both method pages loaded at 1440×1000 and 390×844 with English language metadata, no horizontal overflow, no script errors and no new HTTP errors. The browser's fallback request for /favicon.ico returns 404 in both the original and translated page; this pre-existing request is recorded separately. The Imperial Corridor API still reports nine available selected layers. Translation evidence is retained under `cache/qa/english-docs/`.

The import inventory still contains all 661 source files, with zero missing files. Original source hashes remain unchanged in physics4d-import.json; import-adaptations.json records the seven translated imported documents alongside earlier implementation changes. This documentation review did not rerun the numerical simulations listed above.
