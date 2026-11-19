# Asset contribution standard

[Component overview](README.md) · [Storage strategy](docs/storage.md) · [All component standards](../model/docs/framework/contributing.md)

An Asset is immutable data owned by a Scenario. New data must satisfy both the V2 Asset descriptor and the V1.1 payload contract. The [protocol](../model/docs/framework/protocol-v2.md) and [schemas](schemas/README.md) are normative.

## Required information

| Concern | Requirement |
| --- | --- |
| Identity | Canonical Scenario ID, Asset ID, explicit version and Geometry/Physics kind |
| Dependency | Exact same-Scenario references in `derived_from`; unknown historical dependencies stay unknown |
| Space | ENU metres, geographic origin, vertical datum and bounds; record every coordinate conversion |
| Geometry | Self-contained GLB for display; separately declared computational representations for solvers |
| Arrays | Little-endian C-order NPY, explicit dtype/shape/axes/origin/spacing/sample location and field units |
| Time | Actual strictly increasing timestamps; preserve nonuniform intervals and epochs |
| Missing data | Explicit masks or sparse entity membership; missing observations are not zeros |
| Integrity | Relative bounded file paths, SHA-256 file checksums and payload manifest hash |
| Provenance | Input/source identity, complete request, software environment and numerical diagnostics |

A grid index is not a mesh vertex index. Validate grid alignment before coupling models; do not silently resample, change datums, average fields, relabel precision or manufacture traffic frames. A reduced or resampled dataset is a new derived Asset with its transformation recorded.

## Write and retain

Write computations in cache through a Method. The runner validates the complete export before retention. For recorded data, use the import adapter and `canopy import-run` after checking owner, coordinates and source provenance. Never overwrite an existing Asset or change hashes to hide a modified payload. Scenario archives preserve exact references and include all registered data and provenance.

The repository ships one London Scenario. Large private payloads live under the configured `data_root`, outside Git; local defaults are ignored. Credentials and machine paths belong in private configuration. Publishing a code change does not publish a dataset. Approved public exports live in dedicated Scenario repositories under immutable snapshot directories. Canopy retains a pinned publication reference and locked inventory, following the [publication standard](../visualizer/docs/publishing.md). Their distribution manifests do not register scientific Assets or publish private retained bundles. Adding a remote URL does not change the scientific format contract.

## Change a representation

Add the semantic definition to the protocol, extend both `asset/schemas/` and `model/src/canopy/schemas/`, and provide a valid small fixture plus a rejection case. Update the Python validator and all affected readers/writers. Reject unsupported versions. Use a new major contract version for incompatible changes. Zarr is a proposed extension, not an accepted payload encoding today.

## Verify the change

Public exports must satisfy the [publication budgets](docs/publication-budgets.md): each Scenario is limited to 200,000,000 stored bytes overall and 150,000,000 bytes per Geometry/Physics State category. Classify every distribution file in `scenario/<id>/asset-budget.json`. Preserve originals outside the selected web distribution; do not reduce scientific fidelity to satisfy the gate.

```sh
python3 asset/tools/check_budgets.py --verify-remote
python -m unittest discover -s model/tests -v
python model/tools/check_contract.py /path/to/export/manifest.json
canopy --root . validate imperial_corridor_8km
python model/tools/build_review_inventory.py --refresh-assets
python model/tools/check_repository.py
```

The London validation/refresh commands require its local payloads. The generated `asset-catalog.json` is a review summary, not a second runtime Asset registry. Its references, layer IDs and manifest hashes must match the Scenario and payloads; it includes no credentials or local source paths. Keep raw data out of the explanatory website.
