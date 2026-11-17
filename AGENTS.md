# Canopy development contract

Write all documentation in English, including README text, diagram labels, interface descriptions and run guides.

The four top-level domains are `model/`, `scenario/`, `asset/` and `visualizer/`. The root README explains their relationships; internal diagrams, setup and interface details belong in the relevant directory README. View configuration belongs to Scenario.

Read `model/docs/framework/protocol-v2.md` and `model/docs/framework/method-guide.md` before adding a Method, Asset or Scenario.

- Shared Python implementations and the SDK: `model/src/`; keep package import names stable.
- Scenario metadata: `scenario/<scenario>/scenario.json`.
- Asset schemas: `asset/schemas/`, mirrored in `model/src/canopy/schemas/` for wheel installation.
- Private retained Assets: `<data_root>/project/<scenario>/assets/`; default data root `asset/data/` is ignored by Git.
- Browser implementation: `visualizer/src/visualization/`. The preserved static website lives in `visualizer/site/`.
- Disposable runs: `<cache_root>/`, default `cache/`. Retained data and recovery histories are not cache.

Scenarios share Model implementations and the Visualizer template, and own their geometry and physics results. Registered Methods implement describe/validate/prepare/execute/export and ship a schema, example and detailed run guide. Keep solvers out of widgets.

Use `common.layout` and `Storage` to resolve paths. Original Physics4D checkouts still use `src/`, `schemas/` and `project/`; adapters must continue to accept that source layout. Public resource URLs and portable archive member paths are independent of repository paths. Preserve coordinates, recorded samples, masks, provenance and private storage boundaries.

Do not upload private datasets or remove original histories. Preserve source notices and the original hashes in `model/docs/framework/physics4d-import.json`; record relocations and adaptations separately in `import-adaptations.json`. Publication requires task-specific authorization.

Run `python -m unittest discover -s model/tests -v`, `node --test visualizer/tests/test_viewer.mjs`, and `python model/tools/check_contract.py scenario/examples/contract-v1/manifest.json` after installation. Check viewer behavior when changing routes, loading or widgets.
