# One repository, one Canopy website

[Canopy](../../README.md) · [Visualizer](../README.md) · [Scenario standard](../../scenario/CONTRIBUTING.md)

The public project is [acse-yl222/canopy](https://github.com/acse-yl222/canopy). The [Pages publisher](../tools/publish_pages.py) builds its committed `main` source into [Canopy Pages](https://acse-yl222.github.io/canopy/) and the [architecture guide](https://acse-yl222.github.io/canopy/guide/). Code, Scenario metadata and approved public display data are in this one repository.

## Ownership

```text
canopy/
  model/                          # Shared tools and execution
  asset/                          # Scientific data contracts
  scenario/<scenario_id>/
    scenario.json                 # Scientific Scenario / Asset references
    data/
      manifest.json               # Public distribution inventory
      scene.json                  # Compatibility presentation settings
      models/ physics/ context/   # This Scenario's public data
      tiles/ assets/ actors/      # Details, replays and display models
  visualizer/
    site/                         # Shared website implementation
    guide/                        # Architecture and standards website
    tools/build_pages.py          # Verification and static packaging
    tools/publish_pages.py        # Publish the artifact to gh-pages
```

Only London's `imperial_corridor_8km` is currently included. Future Scenarios own their data in their own directories; renderers and Model implementations remain shared. Private full research bundles stay under the ignored `data_root`. The Pages builder never scans or includes that directory, cache, credentials, recovery histories or the private Site's hosting identity.

## Public distribution manifest, version 1.0.0

`scenario/<id>/data/manifest.json` has `kind: canopy.publication`, `schema_version: 1.0.0`, the owning `scenario_id`, a snapshot label, representation label, source identity, total bytes and a `files` array. Each record declares:

| Field | Meaning |
| --- | --- |
| `path` | Exact file path relative to this Scenario's `data/` directory |
| `viewer_path` | Unique presentation route relative to the published Canopy site |
| `bytes` | Stored file length, including compression when present |
| `sha256` | SHA-256 of those exact stored bytes |

Paths must be bounded relative POSIX paths. URLs, traversal, escaping symlinks, duplicate files and duplicate presentation routes are rejected. Every payload must be listed. New Scenario routes should start with `scenes/<scenario_id>/`; London's historical `assets/`, `tiles/` and `agents/` aliases are retained for compatibility and must remain unique.

This manifest governs distribution, not scientific interpretation. London's preserved presentation uses its existing GLB/gzip, compressed field parts, binary replays and JSON metadata. Its existing coordinate conversions, quantization provenance, timestamps and masks are unchanged. It is not a replacement for V2 Asset descriptors or V1.1 payload manifests. Reformatting or resampling requires a separately recorded transformation under the [Asset standard](../../asset/CONTRIBUTING.md).

## Build and update

1. Change the shared viewer or an explicitly approved public Scenario export. A new numerical result is a new scientific Asset; do not relabel an existing result.
2. For changed public data, update its source/snapshot identity and deliberate file inventory. Verify the new export independently; do not change checksums simply to hide corruption.
3. Regenerate the architecture inventory when its Model/Asset metadata changes, then refresh the website indexes and build into a new directory:

```sh
python model/tools/build_review_inventory.py
python visualizer/tools/build_pages.py --refresh --output cache/pages-preview/canopy
python -m unittest discover -s visualizer/tests -p 'test_pages.py' -v
python -m unittest discover -s model/tests -v
node --test visualizer/tests/test_*.mjs
python model/tools/check_repository.py
python -m http.server 8769 --directory cache/pages-preview
```

Open `http://localhost:8769/canopy/`. Also test `/canopy/viewer/3d/?scene=imperial_corridor_8km` and `/canopy/guide/`. Check a fresh browser, completed offline caching, direct entry, compressed GLB loading, field frames and failed network requests. The project subpath must work; do not assume the website owns the domain root. With Chrome and `puppeteer-core` available, run `node visualizer/tests/browser_pages.cjs http://localhost:8769/canopy/` in another terminal. Set `PUPPETEER_MODULE` and `CHROME_PATH` if needed. This check decodes field samples, verifies complete browser caching and reloads offline.

`build_pages.py` verifies every data checksum, generates `visualizer/site/asset-sources.json` and `download-manifest.json`, and copies only declared data plus selected frontend files. Without `--refresh`, stale generated files fail the build. Existing output directories are never overwritten. Payloads are copied without re-encoding. The browser uses the generated same-origin mapping; there are no hardcoded external gateway URLs. File-content changes produce a new download-cache version. The service worker retries transient network failures and HTTP 502/503/504 up to three times with short backoff, honors cancellation, and returns persistent failures to the caller.

Commit the approved data, implementation and both generated indexes together, then publish:

```sh
git push origin main
python visualizer/tools/publish_pages.py --push
```

The publisher requires a clean `main` checkout matching `origin/main`, verifies all resources again, and uses a separate Git index to create a static artifact commit. It pushes normally to `gh-pages`; a concurrent deployment is rejected instead of being overwritten. Without `--push`, it prepares the artifact and reports its location without publishing. It never changes the source checkout or rewrites history.

GitHub Pages is configured with **Deploy from a branch**, branch **gh-pages**, folder **/ (root)**. GitHub's built-in Pages job publishes that artifact at `/canopy/`. `main` remains the project's default and formal source branch; `gh-pages` contains only generated website output. Source updates require running the publisher after pushing main. A successful push alone does not establish deployment success; inspect the Pages build and the published URL.

The current GitHub OAuth connection cannot create custom Actions workflows because it lacks `workflow` scope. Built-in branch publishing uses the existing authorized connection and requires no additional service.

## Scope and capacity

The current public data is 558,073,283 bytes across 1,477 files. The site includes the detailed London presentation and the architecture guide. The separate unified scientific viewer uses a local Python API and retained V2 Assets; this publication does not claim to deploy that API on a static host.

The builder enforces a 950 MB site budget and rejects individual payloads at or above 100 MiB. GitHub documents a 1 GB published Pages limit, a 100 GB/month soft bandwidth limit, and a 100 MiB ordinary Git file limit. This bounded single-case presentation fits. Reassess before adding large time series or many Scenarios; file format and ownership need not change if storage later moves. See [Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) and [large-file guidance](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github), checked 18 November 2026.
