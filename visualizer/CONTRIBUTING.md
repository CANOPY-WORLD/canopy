# Visualizer contribution standard

[Component overview](README.md) · [All component standards](../model/docs/framework/contributing.md)

The standard viewer is a read-only consumer of Geometry and Physics Assets. Extend its shared interfaces before introducing scenario-specific presentation. The curated Scenario is London's `imperial_corridor_8km`.

Use one shared Viewer across Scenarios. A new Scenario must not copy the Viewer, start another renderer or add a Scenario-ID branch to shared rendering logic. Extend a shared layer, representation reader or small declarative preset. The [architecture review](docs/architecture-review.md) describes the two existing rendering paths; the [upgrade plan](docs/upgrade-plan.md) defines their consolidation. Proposed Source and registry APIs are not available until implemented and tested.

The public presentation has a fixed minimal layout: widget buttons at the top, a full-page canvas, and play/pause plus a progress slider at the bottom. Do not add visible titles, Scenario headers, side panels, legends, counters or hover readouts. Put existing compatibility state and dynamically created detail panels inside the hidden `#viewer-details` host. Preserve loading feedback and actionable errors. The local scientific Viewer retains its inspection UI and catalog navigation using `shared/scenario-tabs.mjs`. Public Scenarios remain selectable through catalog links and direct URLs; never create placeholder public cases.

The bottom controls must follow the selected widget's actual clock and bounds. Pause and seek must affect that widget, and reaching the last field sample must keep the current selection. Playing again restarts from its first sample. Camera orbit progress is presentation time, not a physical result; static camera views and single snapshots have disabled playback. Inactive replay clocks must not keep advancing, and asynchronous loaders must not steal a newer selection. Preserve keyboard operation, visible focus and horizontally scrollable widget buttons on small screens.

The minimal layout applies after loading. The separate loading page contains only the Canopy wordmark, a Scenario introduction from the public catalog, and a progress bar with its current loading status. Do not add a preview renderer, animated city or decorative content. Use actual transfer progress when known and an indeterminate bar otherwise; never invent an overall completion percentage. Hide playback controls until initialization completes, honor reduced motion and keep a readable retry path if loading fails.

## Presentation boundary

Normal homepage entry opens the existing Viewer without a full-package download; `?download=all` explicitly caches the enabled presentation. Keep original geometry and field samples. Prioritize visible nearby geometry while loading all source detail in the background. Read the current field frame with a small look-ahead window and a byte-bounded cache; never decode an entire sequence on widget selection. The [loading and asset review](../asset/docs/london-display-budget.md) describes current limits.

The shell owns the renderer, scene, camera, timeline, selected layers, legend and picking. Scenario configuration selects `template:standard`, a supported preset, Asset/layer references and optional camera. Widgets implement display behavior. A widget must not start a solver, mutate an Asset, write scenario configuration, infer a new physical result or fetch undeclared private filesystem paths.

| Widget interface | Required behavior |
| --- | --- |
| `load(context, layer, signal)` | Load only the declared payload; honor abort, validate representation and add render objects |
| `setTime(seconds)` | Respect actual samples, interpolation rules, epochs and unavailable intervals |
| `setVisible(visible)` | Preserve state while toggling display; unavailable data stays hidden |
| `setOpacity(value)` | Apply supported opacity consistently to render objects |
| `pick(query)` | Return a supported selection with layer/run identity and units, or `null` |
| `dispose()` | Cancel/release owned resources, remove render objects and controls; tolerate repeated disposal |

The implementations in `src/visualization/widgets/index.mjs`, `binary.mjs` and `trajectories.mjs` define the current call behavior. Use `shared/time.mjs` for coordinates, time and bounded asset URLs. Binary dispatch happens through `createWidget`; adding only a JSON registry entry does not add a binary loader.

## Add a layer or preset

1. Reuse a compatible typed layer and widget where possible. Read the Asset's encoding and computational meaning before choosing a renderer.
2. Add a loader/widget only for an explicitly supported representation; update its contract and rejection behavior together with Asset validation.
3. Keep physical vectors ENU and convert to rendering coordinates once. Preserve masks, field units and real timestamps; interpolate trajectories only for entities in both adjacent frames.
4. Expose capabilities accurately. Current full-volume visualization uses exported horizontal slices; arbitrary volume slicing is not implemented.
5. Keep preset differences declarative and small. New presets require coordinated schema, API and viewer changes, including packaged schema mirrors.
6. Keep keyboard interaction, visible focus, responsive layout and readable loading/error states. Avoid continuous rendering when nothing changes.

The detailed London website under `site/` is a compatibility presentation. Approved public data belongs in an independent Scenario data repository, selected by `scenario/<id>/publication.json` and a locked `data/manifest.json`. After changing website code or a publication reference, run `python visualizer/tools/build_pages.py --refresh`; it verifies locked inventories and regenerates routing, Scenario links and per-Scenario download indexes. Remote payloads must not enter the main Pages artifact. Follow the [publishing standard](docs/publishing.md).

Keep resource addresses in the generated mapping, preserve recorded encodings, and test from a project subpath. Only explicitly declared HTTPS snapshot roots may serve remote resources; cross-origin hosts must permit CORS. Do not forward credentials to data hosts. Preserve Range, cancellation, bounded retries and offline caching. A selected Scenario download must never include another Scenario's data. Verify deployed manifest hashes before updating public references; there is no silent fallback to another dataset.

## Verify the change

Optional public bird/traffic availability belongs in Scenario's `website.json`, using the [website profile standard](docs/publishing.md#optional-website-profile). Keep its download exclusions and runtime feature switches in agreement. Removing a widget button alone does not stop a data download. Keep terrain and mapped roads available when vehicle replay is disabled.

```sh
node --test visualizer/tests/test_viewer.mjs
python -m unittest discover -s model/tests -v
python model/tools/check_repository.py
canopy --root . serve --port 8769
# Another terminal; requires Chrome, Puppeteer and the London payloads:
node visualizer/tests/browser_canopy_scenarios.cjs http://127.0.0.1:8769
```

Check all nine selected London layers, the final recorded samples, visibility, camera fitting, time controls, and desktop/mobile layouts. Inspect page and failed-network errors. Tests requiring missing data must be reported as not run. Use an isolated example workspace for synthetic checks rather than adding another Scenario to the main catalog.

## Maintain the explanation website

`guide/` is a small buildless website with an inventory generated from current specs and London metadata. Update it when a component or interface changes; link to the canonical component guides rather than duplicating parameter manuals. Run `python model/tools/build_review_inventory.py`, then `node visualizer/tests/browser_guide.cjs http://127.0.0.1:8769/guide/`. The Pages build includes the guide at `/guide/`, with documentation and summary metadata. The existing private review Site remains a separate deployment with its existing access settings.
