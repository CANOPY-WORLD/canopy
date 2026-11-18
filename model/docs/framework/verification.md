# Verification record

## Scenario data and unified Pages publication — 2026-11-18

The Canopy repository now owns its public London resources under `scenario/imperial_corridor_8km/data/`. The 1,477 files total 558,073,283 bytes; every file matches the prior public source inventory or an already tracked source file. Previously gateway-only resources were recovered from checksum-matching published Release copies. No numerical payload was resampled or re-encoded.

| Check | Result and scope |
| --- | --- |
| Publication integrity | All 1,477 data checksums verified; no missing, duplicate or unlisted resources |
| Static artifact | 562,791,949 bytes; includes viewer, guide and Scenario data; excludes private retained bundles, cache, credentials and hosting identities |
| Python | 70 framework tests and 4 publication boundary tests passed |
| JavaScript | 5 viewer tests and 7 service-worker routing tests passed, including recovery from transient HTTP 503 and bounded failure |
| Static browser | Full GLB geometry loaded from `/canopy/`; first and final samples decoded for all 18 declared field resources |
| Complete browser cache | All 1,563 download entries verified and cached; offline reload succeeded; no page/HTTP errors or external data-origin requests |
| Local scientific viewer | London remains the sole catalog entry, all 9 selected layers load and final dynamic samples remain available; no errors |
| Architecture guide | Desktop/mobile interaction and layout checks passed, including all 8 Methods and 9 Assets |
| Documentation | English documents, component links, schema mirrors and review inventory passed the repository checker |

Initial live checks matched 13 hosted resources against their local SHA-256 values and passed guide interaction checks. Two transient HTTP 503 responses observed during direct city loading motivated bounded transport retries; both affected files subsequently matched their source hashes.

The Pages publisher builds from committed `main` and pushes the static artifact to `gh-pages`. The available GitHub OAuth connection lacks `workflow` scope, so publication uses built-in branch hosting instead of a custom Actions workflow. Source, public-data ownership and publication instructions are documented in [the publication standard](../../../visualizer/docs/publishing.md). Browser evidence is under `cache/qa/pages/` and execution logs under `cache/github-pages-migration/`. This change publishes the existing detailed presentation; the unified V2 scientific viewer continues to use its local read-only API. Historical simulations were not rerun.

## London-only catalog and contributor guide — 2026-11-17

The curated catalog now contains only `imperial_corridor_8km`. Other local Scenario datasets and the unrelated windfarm presentation were moved to a local archive outside the checkout, preserving the data. Synthetic contract examples now live under `model/tests/fixtures/`; `model/tools/run_example.py` creates separate disposable metadata workspaces.

| Check | Result and scope |
| --- | --- |
| Python | 69 tests passed, including fixture relocation and the new bounded `/guide/` HTTP mount |
| JavaScript | 5 viewer unit checks passed; V1 and V1.1 examples validated |
| London retained data | All 9 Assets passed payload and checksum validation; default view has 9 selected layers |
| London browser | Exactly one catalog entry at desktop/mobile widths; all 9 layers ready and all 8 dynamic layers' final recorded samples available; no page or HTTP errors |
| Isolated example | Geometry plus solar, flood, wind, temperature and pollution completed as 6 retained Assets in a separate cache workspace; the curated catalog remained London-only |
| Explanation website | Search, Method details, command copy, 2/7 Geometry/Physics filters, keyboard tabs and all 4 contribution guides passed at 1440 px and 390 px; no page/HTTP errors or page-wide overflow |
| Documentation | Repository checker validates component standards, local Markdown links, English text, schema mirrors, Method example/guide references and generated inventory without private data |
| Static resource integrity | 869 local listed files matched their sizes and SHA-256 hashes; 684 remotely routed London entries were preserved |
| Source retention | All 661 imported inventory files still resolve; original source hashes are unchanged |
| Hosting | Documentation-only Site published with owner-private access; the existing GitHub Pages deployment was not changed |

Local evidence is retained under `cache/qa/london-guide/`: Python log, example output, London validation, static integrity report and desktop/mobile screenshots. The generated review inventory comes from Method specs and a validated safe Asset catalog; it contains no raw fields or private provenance paths.

The new storage guide is a design recommendation. No bucket or paid storage service was provisioned, and no remote Asset resolver or Zarr codec was added. Historical full-domain London task recipes remain unmigrated. These checks do not establish physical prediction accuracy or rerun the full historical London simulations.

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
