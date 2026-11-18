# Detailed London website

[Canopy](../../README.md) / [Visualizer](../README.md) / Detailed website

This directory contains the shared implementation of the detailed Imperial Corridor presentation. Scenario data lives under [scenario/imperial_corridor_8km/data](../../scenario/imperial_corridor_8km/data/manifest.json). The Pages builder packages both into one website.

| Part | Role |
| --- | --- |
| `index.html`, `viewer/` | Entry page and detailed viewer |
| `scenes/index.json`, `agents/` | Scene navigation and shared actor presentation code |
| `vendor/` | Viewer dependencies and their original notices |
| `asset-router.js`, `asset-sources.json` | Same-origin mapping to Scenario-owned data |
| `tools/` | Static field/terrain preparation utilities |

The [London Scenario README](../../scenario/imperial_corridor_8km/README.md) documents integration, dataset provenance and UAV validation scope. The original terrain model and terrain-normalized physics geometry retain their distinct vertical meanings.

For local review, run `canopy serve` from the repository root and visit `/index.html` or the existing `/viewer/` routes. The server maps these public URLs into this directory. For a static preview, follow the [publishing standard](../docs/publishing.md) to build the complete site; this source directory alone omits Scenario data and the guide.

The [Pages publisher](../tools/publish_pages.py) verifies the committed `main` source and publishes the complete artifact to the `gh-pages` deployment branch. This presentation needs no Python API or external data gateway. The separate unified scientific viewer still uses the local read-only API for retained V2 Assets.
