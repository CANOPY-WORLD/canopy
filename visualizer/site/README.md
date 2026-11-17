# Detailed London website

[Canopy](../../README.md) / [Visualizer](../README.md) / Detailed website

This directory contains the preserved Imperial Corridor presentation: building and terrain context, recorded fields, traffic and UAV demonstrations. Its HTML, scripts, vector assets and relative resource paths move together as a self-contained website.

| Part | Role |
| --- | --- |
| `index.html`, `viewer/` | Entry page and detailed viewer |
| `scenes/`, `assets/`, `tiles/`, `agents/` | Presentation metadata and existing public resources |
| `vendor/` | Viewer dependencies and their original notices |
| `asset-router.js`, `asset-routes.json` | Existing large-resource routing |
| `tools/` | Static field/terrain preparation utilities |

The [London Scenario README](../../scenario/imperial_corridor_8km/README.md) documents integration, dataset provenance and UAV validation scope. The original terrain model and terrain-normalized physics geometry retain their distinct vertical meanings.

For local review, run `canopy serve` from the repository root and visit `/index.html` or the existing `/viewer/` routes. The server maps these public URLs into this directory. A static host can serve the contents of this directory as its document root.

The repository's existing GitHub Pages deployment remains configured separately. Moving source files on `main` does not change that deployment or publish private Scenario Assets. Large resources retain their existing read-only gateway/Release routing.
