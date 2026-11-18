# Data storage strategy

[Asset](../README.md) · [Asset contribution standard](../CONTRIBUTING.md)

**Current choice: one Canopy GitHub repository, with approved public data under `scenario/<id>/data/` and one GitHub Pages deployment from `main`.** The London presentation contains 1,477 files and 558,073,283 bytes. Its checked distribution manifest preserves existing encodings and routes; see the [publishing standard](../../visualizer/docs/publishing.md). Complete private computation bundles remain in a dedicated local data directory. Object storage is an option if future public datasets outgrow Pages.

The current repository ships one Scenario: `imperial_corridor_8km`. Its [Asset catalog](../../scenario/imperial_corridor_8km/asset-catalog.json) records the nine registered Assets, their actual layer encodings, byte counts and manifest hashes. These counts cover the unified retained bundles, not all upstream research output or the detailed website's separate terrain, traffic and UAV resources.

## Where to put each type of information

| Content | Recommended location | Current Canopy support |
| --- | --- | --- |
| Code, specs, schemas, guides, Scenario configuration and small review indexes | Git | Implemented |
| Approved public Scenario display resources | `scenario/<id>/data/` in the same GitHub repository | Implemented; checksums and one Pages artifact |
| Retained Geometry and Physics bundles | Dedicated SSD/NAS/server directory selected by `data_root` | Implemented; defaults to ignored `asset/data/` |
| Temporary solver state | `cache_root`, separated from retained data | Implemented |
| Remote immutable bundles | S3-compatible bucket with versioned object keys and an integrity index | Recommended; no new generic remote resolver is implemented |
| Browser distribution | Same-origin files in the Canopy Pages deployment | Detailed London website and guide are static; the unified scientific viewer uses the local read-only server |
| Disaster recovery | Independently retained bundle copy or scenario archive, with tested restoration | `canopy pack` is implemented; remote backup automation is not |

For the immediate single-case workflow, an external SSD or research-server directory is sufficient. Configure its absolute path in the ignored `storage.local.json`; use `canopy validate imperial_corridor_8km` after copying or restoring data. A synchronized directory is not an independent backup if deletion propagates to every copy.

## Remote options

| Option | Good fit | Tradeoff and assessment |
| --- | --- | --- |
| Cloudflare R2 | Frequently viewed geometry and field frames | S3-compatible API and no direct R2 egress charge; storage and operation charges still apply. A strong candidate for browser delivery. Check required API features rather than assuming full S3 equivalence. |
| Amazon S3 | Research retention with native object versioning and lifecycle management | Native versioning can recover overwritten/deleted objects; retained versions incur storage costs. A strong candidate when these retention features matter. |
| GitHub Releases | A small number of named downloadable snapshots | Useful for distribution and the existing compatibility site; individual release assets have plan-dependent size limits. It is not the proposed working store for growing frame sequences. |
| Git LFS | Selected large authoring files that should version alongside code | Stores pointers in Git and external content in LFS. Useful for a few `.blend`/GLB sources; whole-file versioning is a poor match for constantly growing simulation outputs. |
| Ordinary Git | Source, small metadata and the bounded current public London snapshot | Current public files fit the limits. Large evolving research outputs remain external; binary history grows with updates. |

These are Canopy-specific recommendations based on access patterns. Provider facts were checked against [R2 API documentation](https://developers.cloudflare.com/r2/get-started/s3/), [R2 pricing](https://developers.cloudflare.com/r2/pricing/), [S3 Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html), [GitHub large-file guidance](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github), and [Git LFS](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage) on 2026-11-17. No bucket, credentials or paid service is provisioned by this change.

## File format and loading

| Format | Use in Canopy | Loading behavior |
| --- | --- | --- |
| JSON | Scenario, Asset descriptor, manifest, small trajectories and indexes | Read metadata first; use explicit IDs and checksum-bound references |
| GLB | Display geometry | Load a selected geometry or existing detailed tile; computational geometry is separate |
| NPY / `npy_frames` | Current scalar/vector display fields and retained arrays | Fetch recorded frames on demand; preserve original dtype, units, times and masks |
| Zarr | Future large multidimensional volumes | Chunked remote access could reduce unnecessary spatial/time reads; requires new schemas, exporter, validator and viewer/analysis readers |

[Zarr's storage guide](https://zarr.readthedocs.io/en/latest/user-guide/storage/) describes local and remote stores; [its performance guide](https://zarr.readthedocs.io/en/latest/user-guide/performance/) explains how chunk shape follows access patterns. This makes Zarr a reasonable future candidate for large T×Z×Y×X volumes. Choose chunk shapes using measured slice/region requests and consider sharding when object counts become large. Canopy currently rejects Zarr payloads: do not label existing NPY files as Zarr or claim that remote volume slicing is available.

## A migration that preserves the contract

1. Keep an unchanged verified local copy. Record a file inventory, byte sizes and SHA-256 values for each immutable bundle.
2. Mirror the existing relative layout under a remote prefix, for example `canopy/project/imperial_corridor_8km/assets/bundles/<run_id>/`. Upload new IDs; do not overwrite an old bundle.
3. Transfer bulk objects first, verify them, and publish the bundle index last. Select retention/versioning controls supported by the chosen provider and maintain an independent backup.
4. Keep credentials in private machine configuration or a secret store. Do not put expiring signed URLs, access keys or absolute workstation paths into Scenario/Asset JSON.
5. Initially materialize requested bundles into the configured local `data_root`; the current readers can then validate and use them without a format change.
6. Add a remote resolver separately if direct remote loading is required. It must preserve bounded relative paths, checksums, range/CORS behavior, access control and cancellation; measure first-frame latency, transferred bytes and peak memory.
7. Validate the London view and a restored archive before changing a public data route. Retain the current compatibility resources until their replacement is verified.

Moving files out of a working tree does not remove old binary history from Git. History rewriting is a separate migration; it is not part of this cleanup.
