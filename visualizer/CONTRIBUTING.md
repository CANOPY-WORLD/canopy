# Visualizer contribution standard

[Component overview](README.md) · [All component standards](../model/docs/framework/contributing.md)

The standard viewer is a read-only consumer of Geometry and Physics Assets. Extend its shared interfaces before introducing scenario-specific presentation. The curated Scenario is London's `imperial_corridor_8km`.

## Presentation boundary

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

The detailed London website under `site/` is a compatibility presentation with its own static data index. If a listed website file changes, update its `download-manifest.json` checksum and size. Retain remote London entries routed through `asset-routes.json`; local absence alone does not mean they can be deleted.

## Verify the change

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

`guide/` is a small buildless website with an inventory generated from current specs and London metadata. Update it when a component or interface changes; link to the canonical component guides rather than duplicating parameter manuals. Run `python model/tools/build_review_inventory.py`, then `node visualizer/tests/browser_guide.cjs http://127.0.0.1:8769/guide/`. The hosted review is a private Site containing documentation and summary metadata, not raw simulation data.
