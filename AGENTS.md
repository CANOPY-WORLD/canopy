# Canopy development contract

Write all documentation in English, including README text, diagram labels, interface descriptions and run guides.

The four top-level domains are `model/`, `scenario/`, `asset/` and `visualizer/`. The root README explains their relationships; internal diagrams, setup and interface details belong in the relevant directory README. View configuration belongs to Scenario.

The only curated Scenario is `imperial_corridor_8km`, the London 8 km case. Other scene datasets stay outside this checkout; test requests and tiny payloads live under `model/tests/fixtures/`. Use `model/tools/run_example.py` for disposable synthetic runs.

Start at `model/docs/framework/contributing.md` and read the affected component's `CONTRIBUTING.md`. Scoped `AGENTS.md` files reinforce the same standards.

The remote `main` branch is protected, including administrators: use a feature branch and pull request. Force pushes and deletion are disabled, and review conversations must be resolved. The **Scenario asset budgets** check from GitHub Actions is required, with branches up to date before merging; see the [publication budgets](asset/docs/publication-budgets.md). There is no mandatory independent approval because the repository has one maintainer. Run the documented checks and include their evidence in the PR. These server settings do not authorize an agent to merge.

Follow the review and merge workflow in `model/docs/framework/contributing.md`: open a PR, review the actual diff, address findings, and report the PR link, review outcome and validation limits to the user. Leave the PR open until the user explicitly confirms that it may be merged. A request to implement or push changes, passing checks, or GitHub reporting a PR as mergeable is not merge approval. Do not enable auto-merge, bypass protection or weaken it to publish. After an approved merge, publish only with task-specific authorization and from clean, synchronized `main` as described in `visualizer/docs/publishing.md`.

Read `model/docs/framework/protocol-v2.md` and `model/docs/framework/method-guide.md` before adding a Method, Asset or Scenario.

- Shared Python implementations and the SDK: `model/src/`; keep package import names stable.
- Scenario metadata: `scenario/<scenario>/scenario.json`.
- Public website data: independent Scenario data repositories. `scenario/<scenario>/publication.json` pins the repository revision, immutable HTTPS snapshot and locked `data/manifest.json`; only metadata stays here. Build the shared website with `visualizer/tools/build_pages.py`. Never copy remote payloads into the main Pages artifact.
- Asset schemas: `asset/schemas/`, mirrored in `model/src/canopy/schemas/` for wheel installation.
- Private retained Assets: `<data_root>/project/<scenario>/assets/`; default data root `asset/data/` is ignored by Git.
- Browser implementation: `visualizer/src/visualization/`. The preserved static website lives in `visualizer/site/`.
- Disposable runs: `<cache_root>/`, default `cache/`. Retained data and recovery histories are not cache.

Scenarios share Model implementations and the Visualizer template, and own their geometry and physics results. Registered Methods implement describe/validate/prepare/execute/export and ship a schema, example and detailed run guide. Keep solvers out of widgets.

Use `common.layout` and `Storage` to resolve paths. Original Physics4D checkouts still use `src/`, `schemas/` and `project/`; adapters must continue to accept that source layout. Public resource URLs and portable archive member paths are independent of repository paths. Preserve coordinates, recorded samples, masks, provenance and private storage boundaries.

Do not upload private datasets or remove original histories. Preserve source notices and the original hashes in `model/docs/framework/physics4d-import.json`; record relocations and adaptations separately in `import-adaptations.json`. Publication requires task-specific authorization.

Run `python -m unittest discover -s model/tests -v`, `node --test visualizer/tests/test_viewer.mjs`, and `python model/tools/check_contract.py model/tests/fixtures/contract-v1/manifest.json` after installation. Check viewer behavior when changing routes, loading or widgets.

Run `python model/tools/check_repository.py` to check the one-case catalog, Method references, documentation links and generated inventory. Follow `visualizer/docs/publishing.md` after public data or website changes. Explanation-page source under `visualizer/guide/` contains summary metadata only. The Pages build includes this guide; preserve the existing private review Site’s audience when maintaining that separate deployment.
