# Geometry loading by view

[Visualizer](../README.md) · [Contributor standard](../CONTRIBUTING.md) · [Publication](publishing.md)

The public Viewer keeps the existing city overview visible and streams the original detailed building tiles around the current view target. Moving away cancels pending work and releases those tiles. This changes when data enters browser memory; it does not rewrite the source Assets or reduce scientific samples.

The design reference is the [Bristol preview](https://srst-by722.github.io/bristol-8km-geometry-preview/viewer/?v=ext001-20261111), inspected on 19 November 2026. Its [loader implementation](https://github.com/SRST-by722/bristol-8km-geometry-preview/blob/0f7f144d9bd644e07603e37740a64c9482abaec9/viewer/viewer.js) prioritizes a terrain overview, building overview parts and nearby detail, with bounded jobs and cancellation. Canopy implements this loading pattern around its existing assets. London's current overview is a single building model and its landscape uses separate surfaces; this change does not create Bristol's multi-level terrain assets or copy its interface.

## Loading contract

| Stage | Behavior |
| --- | --- |
| Opening | Keep the existing Canopy wordmark, Scenario introduction and measured download/preparation status. Open the city without waiting for physics masks. |
| City overview | Retain the existing overview model as a fallback. Apply the same terrain alignment used for detailed buildings. |
| Nearby detail | Rank tiles by view target, visibility and distance. Ordinarily retain at most six tiles. |
| UAV playback | Prioritize every tile crossed by the selected recorded route, allowing up to eight tiles. Routes requiring more than eight tiles offer complete geometry mode; routes outside published building coverage report that gap and offer a return to Overview. |
| Transfer and preparation | At most four occupied geometry jobs, including downloaded buffers waiting for preparation. GLB parse, terrain attachment and scene commit run sequentially. The queue yields between jobs. |
| Replacement | Hide the corresponding overview region only after the tile's base mesh and every landmark are ready. Partial or failed tiles retain the overview. |
| Movement | Replan every 250 ms. Keep a wider retention radius to reduce loading churn. Abort obsolete transfers; dispose any parse result completed after cancellation. |
| Failures | Retry a geometry job twice, then expose a retry button while preserving the overview. Do not retry forever. |
| Ground | Prepare at most two surface pairs concurrently through the existing single worker, or its identical main-thread fallback. Show completed surfaces incrementally. |
| Physics | Initialize masks when a physics widget is selected. Fetch its selected recorded sample and bounded look-ahead through the existing frame cache. A later widget selection takes precedence. |
| Rendering | Queue progress updates do not redraw the city. Render on actual scene or camera changes. Ground visibility compares the active flat/elevated representation to avoid perpetual redraws. |

Default geometry mode streams original detail. `?quality=full&lite=0` retains the existing complete geometry loader; `?lite=1` retains the explicit voxel display. The source files and their provenance remain available. The widget strip and bottom playback controls retain their existing layout. A retry action appears only after a loading failure.

## Interfaces for future changes

- [asset-queue.mjs](../site/viewer/3d/asset-queue.mjs) owns job priority, cancellation, bounded attempts and serialized preparation. `load` receives an abort signal and byte-progress callback; `prepare` returns an owned resource; `commit` attaches it; `discard` releases a stale result. A finished download keeps its queue slot until preparation finishes.
- [streamed-detail-tiles.js](../site/viewer/3d/streamed-detail-tiles.js) consumes the existing tile index. `update`, `setEnabled`, `setRequiredPoints`, `hasPoints`, `retry` and `dispose` manage current-view residency. `ready` means the index has been read. `progress.complete` describes the current requested view, not the complete Scenario.
- [complete-detail-tiles.js](../site/viewer/3d/complete-detail-tiles.js) remains the full-residency path. Its completion means every declared detail resource has been processed.
- [vector-landscape.js](../site/viewer/3d/vector-landscape.js) reports each prepared surface through `onSurface`. The shell keeps partial surfaces consistent with the selected widget while the remaining ground assets load.

Future loaders must dispose stale parsed resources, including materials and textures; retain a visible fallback until replacement is complete; separate transfer progress from preparation; and avoid rendering solely because a byte counter changed. Preserve existing coordinates, masks, recorded times, source vertices and per-vertex attributes. Do not put a solver in a loader or silently replace a missing result.

`window.cityDetailTiles.stats` exposes current jobs, attempts, resident tile count and owned geometry-array bytes for diagnostics without adding a visible panel. `currentViewBytes` and queue `bytes` describe decompressed GLB payloads delivered to the reader. They are not compressed network-transfer sizes. `residentGeometryBytes` counts attribute/index buffers owned by detailed building roots; it excludes the overview, landscape, textures, GPU copies, pending transfers, browser overhead and physics arrays. Six tiles are not a fixed byte limit.

Streaming does not reduce the complete web publication's size. The agreed 200 MB total and 150 MB category limits remain separate. The currently selected 558.07 MB London package still requires a complete optimized publication before those checks can pass.

## Existing route coverage

The retained London replay has 1,383 routes. Of these, 1,309 stay within the published building tile bounds and cross at most seven tiles. The other 74 include points outside those bounds. This was found while checking route-driven loading; the routes and source geometry are unchanged. A route with missing building coverage cannot pass `hasPoints`, including in the existing complete loader. Streaming now reports the coverage gap instead of treating it as unfinished downloading. No missing geometry or flight samples are invented.

## Measured London residency

At the same South Kensington camera, using the selected original publication:

| Detail resources | Previous complete loader | Streamed loader |
| --- | ---: | ---: |
| Resident tiles | 64 | 6 |
| Loaded detail GLBs | 331 | 117 |
| Owned geometry-array bytes | 656,654,218 | 229,365,514 |
| Detail geometry-array bytes after moving to the high overview | Retained | 0 |

The near-view array reduction is 65.1%. The overview and landscape remain loaded; this is not a 65.1% reduction in total browser memory. Ground comparison verified identical SHA-256 values for all 108 attribute arrays in the baseline, worker and main-thread fallback. The idle-view check observed no redraws over its 800 ms observation window after settling.

## Validation

Build an isolated static preview and run the checks from the repository root:

```sh
node --test visualizer/tests/test_*.mjs
python3 -m unittest discover -s visualizer/tests -p 'test_pages.py' -v
python3 visualizer/tools/build_pages.py --refresh --output cache/streaming-preview/canopy
python3 -m http.server 8778 --directory cache/streaming-preview
# In another terminal; set PUPPETEER_MODULE and CHROME_PATH if needed:
node visualizer/tests/browser_geometry_streaming.cjs http://127.0.0.1:8778/canopy/
node visualizer/tests/browser_loading_budget.cjs http://127.0.0.1:8778/canopy/
CANOPY_QA_PAUSE_RENDER=1 node visualizer/tests/browser_widget_player.cjs http://127.0.0.1:8778/canopy/
```

An optional second URL to `browser_geometry_streaming.cjs` supplies a baseline build at the same camera. `browser_ground_equivalence.cjs <baseline-url> <candidate-url>` compares every ground position, height and normal in both worker and fallback modes. Browser checks save their reports under `cache/qa/` and require the declared public London snapshot.

The software-WebGL runs pause continuous rendering and render explicit comparison frames at reduced pixel ratio. These checks validate resource ownership, cancellation, preservation of ground attributes and widget behavior; they do not establish production FPS or cold-network startup latency.
