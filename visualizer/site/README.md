# Detailed London website

[Canopy](../../README.md) / [Visualizer](../README.md) / Detailed website

This directory contains the shared implementation of the detailed Imperial Corridor presentation. The [publication reference](../../scenario/imperial_corridor_8km/publication.json) selects the independent London data website; [data/manifest.json](../../scenario/imperial_corridor_8km/data/manifest.json) is its locked file inventory. The Pages builder packages the Viewer and metadata without the remote payloads.

| Part | Role |
| --- | --- |
| `index.html`, `viewer/` | Entry page and detailed viewer |
| `scenes/index.json`, `agents/` | Scene navigation and shared actor presentation code |
| `vendor/` | Viewer dependencies and their original notices |
| `asset-router.js`, `asset-sources.json` | Bounded mapping to explicitly declared Scenario data hosts |
| `scenario-index.json`, `download-manifests/` | Public links and a separate offline download list for each Scenario |
| `tools/` | Static field/terrain preparation utilities |

The [London Scenario README](../../scenario/imperial_corridor_8km/README.md) documents integration, dataset provenance and UAV validation scope. The original terrain model and terrain-normalized physics geometry retain their distinct vertical meanings.

For local review, run `canopy serve` from the repository root and visit `/index.html` or the existing `/viewer/` routes. The server maps these public URLs into this directory; the detailed presentation reads its data over HTTPS. For a static preview, follow the [publishing standard](../docs/publishing.md) to build the shared site. Use the complete download flow before testing offline viewing.

The [Pages publisher](../tools/publish_pages.py) verifies the committed `main` source and deployed remote manifests, then publishes the shared artifact to the `gh-pages` deployment branch. This presentation uses the independently hosted data and needs no Python API. The separate unified scientific viewer still uses the local read-only API for retained V2 Assets.
