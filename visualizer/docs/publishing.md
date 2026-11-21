# Shared Canopy website, independent Scenario data

[Canopy](../../README.md) · [Visualizer](../README.md) · [Scenario standard](../../scenario/CONTRIBUTING.md)

[Canopy](https://github.com/CANOPY-WORLD/canopy) owns the shared Models, Viewer, scientific contracts, Scenario configuration and public links. Each published Scenario owns an independent data repository and data website. The shared Viewer reads the selected Scenario's files over HTTPS; the main Pages artifact does not contain those payloads.

| London entrypoint | Location |
| --- | --- |
| Shared website | [Canopy Pages](https://canopy-world.github.io/canopy/) |
| On-demand Viewer | [Imperial Corridor](https://canopy-world.github.io/canopy/viewer/3d/?scene=imperial_corridor_8km) |
| Architecture guide | [Components and standards](https://canopy-world.github.io/canopy/guide/) |
| Public link registry | [scenario-index.json](https://canopy-world.github.io/canopy/scenario-index.json) |
| Scenario data repository | [canopy-scenario-imperial-corridor-8km](https://github.com/CANOPY-WORLD/canopy-scenario-imperial-corridor-8km) |
| Scenario data website | [London data](https://canopy-world.github.io/canopy-scenario-imperial-corridor-8km/) |

## Ownership

The [CANOPY-WORLD organization](https://github.com/CANOPY-WORLD) groups the shared `canopy` framework and independently versioned Scenario data repositories. Keep reusable Models, scientific contracts, Scenario configuration and the Viewer in `canopy`. Name data repositories `canopy-scenario-<name>` and register their immutable publications in the main repository. An Organization groups repository ownership and collaboration; each Pages site retains its own publication budget.

```text
canopy/
  model/                              # Shared tools and execution
  asset/                              # Scientific contracts
  scenario/<scenario_id>/
    scenario.json                     # Scientific Scenario and Asset references
    publication.json                  # Data repository, revision and HTTPS snapshot
    data/manifest.json                # Locked file inventory only
  visualizer/
    site/                             # Shared website implementation
    guide/                            # Architecture and component guide
    tools/build_pages.py              # Build website and generated indexes
    tools/check_publications.py       # Verify deployed data identities
    tools/publish_pages.py            # Publish the shared website

canopy-scenario-<name>/                # Independent repository
  catalog.json                        # Snapshot index and shared Viewer link
  index.html                          # Data landing page linking back to Canopy
  snapshots/<snapshot_id>/
    manifest.json                     # Checksums, sizes, routes and provenance
    models/ physics/ context/         # Scenario-owned payloads
    tiles/ assets/ actors/
  tools/check_data.py                  # Standalone local snapshot verification
```

London's `imperial_corridor_8km` remains the only curated Scenario. Future Scenarios can be registered without copying their data into Canopy or duplicating the Viewer. The data landing page opens the shared Viewer. A separately maintained external presentation can be linked from documentation, but the implemented detailed Viewer currently uses the declared snapshot resources.

Private research bundles stay under the ignored `data_root`. Website builds never scan or include that directory, cache, credentials, recovery histories or the private Site's hosting identity. Independent storage does not change logical Scenario ownership or scientific Asset semantics.

## Publication reference, version 1.0.0

`scenario/<id>/publication.json` has `kind: canopy.publication-reference` and these required fields:

| Field | Meaning |
| --- | --- |
| `schema_version`, `scenario_id` | Reference version `1.0.0` and canonical owner |
| `repository`, `revision` | Public data repository URL and exact 40-character Git commit |
| `website` | Human-readable data website URL |
| `snapshot` | Immutable named data version |
| `base_url` | Public HTTPS directory ending in `/snapshots/<snapshot>/` |
| `manifest.path` | Locked local inventory, exactly `data/manifest.json` |
| `manifest.sha256` | SHA-256 of the inventory's exact bytes |

Use the [London reference](../../scenario/imperial_corridor_8km/publication.json) as a working example. No credentials, signed URLs, queries, fragments, traversal or implicit `latest` directories are accepted. URLs belong to this delivery reference, not to scientific Asset payload paths.

GitHub Pages serves the current deployed tree, so snapshot immutability is a publishing rule: never overwrite a published directory. The pinned Git revision preserves source identity, and the locked manifest detects changes. The remote checker compares the served manifest and, for GitHub repositories, the manifest at the pinned source revision.

## Distribution manifest, version 1.0.0

The data repository stores `snapshots/<snapshot>/manifest.json`. Canopy keeps a byte-identical locked copy at `scenario/<id>/data/manifest.json`. It has `kind: canopy.publication`, `schema_version: 1.0.0`, owning `scenario_id`, snapshot and representation labels, source identity, total bytes and a `files` array:

| Field | Meaning |
| --- | --- |
| `path` | Exact payload path relative to the snapshot directory |
| `viewer_path` | Unique logical route relative to the shared Canopy website |
| `bytes` | Stored file length, including compression |
| `sha256` | SHA-256 of those exact stored bytes |

Paths must be bounded relative POSIX paths. Traversal, escaping symlinks, duplicate files and duplicate routes are rejected. New routes start with `scenes/<scenario_id>/`; London's historical `assets/`, `tiles/` and `agents/` aliases remain reserved for compatibility. Every payload must be listed. A remote Scenario's `data/` directory in Canopy may contain only the locked manifest: shadow copies are rejected.

This is a distribution inventory. London's GLB/gzip, compressed fields, binary replays, JSON, images, coordinate conversions, quantization provenance, timestamps and masks are unchanged. It does not replace V2 Asset descriptors or V1.1 payload manifests. Reformatting or resampling creates a separately recorded transformation under the [Asset standard](../../asset/CONTRIBUTING.md).

The builder still supports explicit local `data/` publications without a reference for small fixtures or self-contained exports. Such files count against the main site budget. This is not the default for growing public Scenarios.

## Loading and caching

`build_pages.py` generates `asset-sources.json` version `2.0.0`. Logical Viewer paths map to relative frontend files or exact remote HTTPS resources under explicitly declared `remote_bases`. The worker accepts legacy version `1.0.0` local mappings for migration. Unknown versions and undeclared remote targets fail explicitly.

The worker preserves Range requests, gzip decoding, cancellation and bounded retries for transient network failures or HTTP 502/503/504. Data requests use CORS mode, omit credentials and do not forward application authorization headers. Redirects to undeclared targets are rejected. London's two Pages sites currently share the `canopy-world.github.io` origin; a future host on another origin must support browser CORS. Public Pages responses were checked to return `Access-Control-Allow-Origin: *`.

`scenario-index.json` exposes each Scenario's Viewer link, repository, pinned revision, data website, snapshot manifest and download-list URL. `download-manifests/<scenario_id>.json` contains shared frontend files plus only that Scenario's data. The root `download-manifest.json` remains an alias for the default Scenario's list. The opening page selects `?scene=<id>` or the configured default, verifies file lengths and SHA-256, and caches the result under logical Viewer URLs. Direct Viewer links use the same complete download and verification step before initializing the scene. The loading page stays visible until all detailed building tiles and the road/traffic context are ready. Complete geometry is the default on every device; `?lite=1` explicitly selects voxel geometry. A completed cache supports offline Viewer reloads.

Moving the payloads changes their hosting location, not their transfer size: a complete London offline download is still approximately 563 MB. Additional Scenarios do not enter London's download list. Cache versions derive from the selected file inventory, including the routing configuration.

## Publish data before links

1. Select an explicitly approved public export. New numerical results remain new scientific Assets; do not relabel historical results.
2. In the Scenario repository, create a new immutable snapshot directory and manifest, preserving provenance. Update `catalog.json` and run its standalone `python3 tools/check_data.py`. Keep an independently verified retained copy.
3. Commit and push the Scenario repository. Its GitHub Pages configuration is **Deploy from a branch → main → / (root)**. Keep `.nojekyll`. Confirm a successful Pages build and served data before modifying Canopy's reference.
4. Copy the exact snapshot manifest into Canopy and update `publication.json` with its source revision, hash and snapshot URL. Update the Scenario README and public catalogs when adding an explicitly authorized new Scenario.
5. Run the remote verifier. `--payloads` streams every file through SHA-256 with bounded concurrency; no downloaded data is added to the main repository:

```sh
python visualizer/tools/check_publications.py --payloads
```

Do not substitute another snapshot when a referenced host fails. Diagnose a failed URL or hash, restore its immutable bytes, or select a verified new version explicitly.

## Build, test and publish Canopy

```sh
python model/tools/build_review_inventory.py
python visualizer/tools/build_pages.py --refresh --output cache/pages-preview/canopy
python -m unittest discover -s visualizer/tests -p 'test_pages.py' -v
python -m unittest discover -s model/tests -v
node --test visualizer/tests/test_*.mjs
python model/tools/check_repository.py
python -m http.server 8769 --directory cache/pages-preview
```

Use a new output directory for each build. Open `/canopy/`, `/canopy/viewer/3d/?scene=imperial_corridor_8km` and `/canopy/guide/`. A local preview reads the declared HTTPS data host, exercising CORS. With Chrome and `puppeteer-core` available, run `node visualizer/tests/browser_pages.cjs http://localhost:8769/canopy/`; set `PUPPETEER_MODULE` and `CHROME_PATH` if needed. Check fresh loading, worker upgrades, field samples, complete selected-Scenario caching and offline Viewer reload.

`build_pages.py` verifies the locked inventories without network access, rejects stale generated indexes unless `--refresh` is requested, and copies only selected frontend files and metadata. Remote bytes are reported separately and excluded from the artifact size. A metadata build does not claim to verify live payload availability; that is the remote check above.

Commit the references, docs, code and generated indexes on a feature branch and open a pull request. `main` is protected, including administrators: PRs and resolved conversations are required; force pushes and deletion are disabled. There are currently no mandatory independent approvals or required CI contexts. Run the checks above and attach the actual results to the PR. The [review and merge workflow](../../model/docs/framework/contributing.md#pull-request-review-and-merge) also requires reviewing the diff, reporting findings and validation limits, and obtaining the user's explicit confirmation before an agent merges. Passing checks or GitHub reporting a PR as mergeable does not grant that confirmation.

For an organization maintainer, after committing on a feature branch:

```sh
git push -u origin HEAD
# Write the problem, change and validation evidence into this file first:
gh pr create --repo CANOPY-WORLD/canopy --base main --body-file cache/pr-description.md
```

Leave the PR open until the user confirms the merge; do not enable auto-merge while waiting. After confirmation, merge the reviewed, validated PR through GitHub. Only when publication is also authorized for the task, synchronize the formal source branch and publish:

```sh
git switch main
git pull --ff-only origin main
python visualizer/tools/publish_pages.py --push
```

The publisher requires a clean `main` checkout matching remote main. It verifies deployed manifests, uses a separate Git index to create the shared artifact, and makes a normal fast-forward push to `gh-pages`. It never rewrites source history or alters the checkout. Without `--push`, it prepares an artifact without publishing.

When changing Scenario navigation, run `browser_scenario_tabs.cjs` against the local scientific server. Supply the Pages preview URL as its second argument to also check the public navigation state under a project subpath. The public Scenario header is hidden by the minimal player; Scenario selection remains available through catalog links and direct URLs.

When changing public widget selection or playback, run `node visualizer/tests/browser_widget_player.cjs http://localhost:8769/canopy/`. It uses real London data in the existing lightweight geometry mode and checks every visible widget, play/pause, seeking, final samples, replay restart, rapid switching, keyboard interaction and desktop/mobile layout. On software WebGL machines, `CANOPY_QA_PAUSE_RENDER=1` pauses continuous GPU drawing during the control checks and renders explicit screenshot frames; report that limit rather than treating it as a frame-rate benchmark. This focused test does not replace full-detail geometry, complete offline download or data-integrity verification when those features change.

Canopy Pages uses **Deploy from a branch → gh-pages → / (root)**. `main` remains the formal source branch; `gh-pages` contains generated website output. A source push alone does not deploy the shared website: run the publisher and verify the resulting Pages build. The current OAuth connection lacks `workflow` scope; built-in branch publication requires no custom Actions workflow or new credentials.

## Moving repository ownership

Transfer existing repositories to preserve their commits and settings. Update local Git remotes, repository homepages, the data site's shared Viewer link, Canopy's publication references and documentation together. Regenerate the guide inventory and Pages indexes after editing their source references. Keep scientific payload bytes, locked manifests and original provenance unchanged.

Verify the data site under its new owner before publishing Canopy's updated references. GitHub redirects transferred repository URLs, but does not redirect their Pages sites. The shared website and data website therefore need explicit verification at their new URLs. Browser caches belong to an origin; a cache from the previous Pages origin does not automatically move to the new one. See [GitHub's repository transfer behavior](https://docs.github.com/en/repositories/creating-and-managing-repositories/transferring-a-repository).

## Capacity and migration scope

The independently hosted London snapshot has 1,477 payloads and 558,073,283 bytes. Canopy's shared website is approximately 5 MB after this split. Each Pages site remains limited to 1 GB, with a 100 GB/month soft bandwidth limit. Builders reserve a 950 MB publication budget and reject individual ordinary Git payloads at or above 100 MiB. Separate Scenario sites spread ownership and deployment; they are not unlimited storage. Use a suitable larger host when an individual Scenario or its retained snapshots outgrow Pages.

The main working tree and website no longer include London's bulk files. Earlier commits retain their binary history; this migration does not rewrite history or immediately shrink a full Git clone. Use a shallow clone when only current source is needed.

The detailed public presentation is static. The unified V2 scientific Viewer still uses its local Python API and retained research Assets; no solver or API is deployed by this change. See [GitHub project sites](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) and [large-file guidance](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github), checked 18 November 2026.
