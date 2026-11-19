# Public Scenario asset budgets

[Asset standard](../CONTRIBUTING.md) · [Scenario standard](../../scenario/CONTRIBUTING.md) · [Publishing](../../visualizer/docs/publishing.md)

Each Scenario's selected public distribution must meet **all three** limits:

| Scope | Maximum stored bytes | Decimal MB |
| --- | ---: | ---: |
| Complete Scenario resource package | 200,000,000 | 200 |
| Geometry | 150,000,000 | 150 |
| Physics State | 150,000,000 | 150 |

Equality passes. One byte over any limit fails the check. Limits apply per Scenario, not across the entire catalog. They measure stored published files, including existing compression, not decoded arrays, browser heap, GPU memory or the first frame's download size. Loading data lazily does not reduce its package size.

## What counts

The authoritative inventory is `scenario/<id>/data/manifest.json`, selected by the exact revision and checksum in `publication.json`. Count every entry once. Geometry includes buildings, terrain, roads, meshes, textures, placement data and related source files if they remain in the selected public package. Physics State includes physical fields, all recorded frames, masks, trajectories, replay data and their metadata. UAV, traffic and bird recordings are Physics State; their static display meshes are Geometry. General Scenario and result provenance metadata count toward Physics State.

An inactive widget or an older export still counts if its files remain in this inventory. To keep an export out of the selected web package, create a new immutable publication containing only its actual dependencies, retaining the old snapshot and original scientific data separately. Do not remove original Assets, discard samples, alter precision, crop grids or omit required dependencies to pass a size check.

Private retained scientific bundles, caches and earlier snapshots that are not selected by this Scenario's publication reference are outside this web-package budget. Shared Viewer code is outside the Scenario inventory and remains subject to the existing Pages artifact limit. The data repository's cumulative Pages storage limit is separate; keeping old snapshots can still exhaust that host.

## Classification

Each public Scenario must provide `asset-budget.json`. The [London policy](../../scenario/imperial_corridor_8km/asset-budget.json) is the current example:

```json
{
  "schema_version": "1.0.0",
  "scenario_id": "example",
  "groups": {
    "geometry": {"prefixes": ["geometry/"], "files": []},
    "physics_state": {"prefixes": ["physics/"], "files": ["scene.json"]}
  }
}
```

Prefixes end at directory boundaries. Every inventory entry must match exactly one category. Unknown paths, overlapping categories, missing policies, duplicate resources, invalid sizes and incorrect manifest totals fail. There is no exclusion list, per-Scenario limit override or legacy allowance. Review category changes against the data's actual meaning; changing a filename does not change an Asset's kind.

This is publication accounting metadata, not a new scientific encoding. V2 Asset descriptors, V1.1 payloads and their schema mirrors are unchanged. The writer, numerical samples and Viewer interfaces are unchanged.

## Check locally and in PRs

```sh
python3 -m unittest discover -s asset/tests -p 'test_budgets.py' -v
python3 asset/tools/check_budgets.py --json cache/asset-budgets.json
python3 asset/tools/check_budgets.py --verify-remote --json cache/asset-budgets.json
```

The offline check validates local payloads or the pinned inventory and prints category totals, excess bytes and largest files. The remote check also compares the served and pinned manifests, then checks every declared payload's size against the pinned GitHub tree. Missing/unlisted files, symlinks, a truncated tree or incorrect byte counts fail. This avoids downloading hundreds of MB on each PR. It verifies Git blob sizes and manifest identity, not every remote payload's SHA-256; continue to use `check_publications.py --payloads` before publication. Remote verification currently supports public GitHub data repositories containing ordinary Git blobs.

The Actions workflow runs for every PR to `main`, pushes to `main`, merge groups and manual dispatch. It has no path filter, conditional skip or `continue-on-error`. It uses read-only repository permissions, runs synthetic tests and then checks the complete selected inventories against remote sizes. A failure exits nonzero and reports the excess; the PR stays open for correction.

The exact **Scenario asset budgets** check is required on `main`, with GitHub Actions (app ID `15368`) as its source and up-to-date branches required. This setting was activated and read back on 19 November 2026; admin enforcement, required PRs, resolved conversations and the existing force-push/deletion restrictions were preserved. A failed or absent required check blocks merging. [GitHub's protected-branch documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) describes this enforcement. Passing CI never grants an agent permission to merge.

Workflow source and branch protection are two separate installation steps. The [first hosted run](https://github.com/CANOPY-WORLD/canopy/actions/runs/44485596752) passed all 15 budget tests and then rejected the oversized London publication. During rollout, the workflow source is in [PR #10](https://github.com/CANOPY-WORLD/canopy/pull/10), pending an approved merge. Other branches without the workflow cannot supply the required check and are also blocked; they must include the reviewed workflow before merging. Do not bypass the rule or temporarily raise the limits to complete rollout. GitHub credentials need permission to write `.github/workflows/`; ordinary repository write access alone may not include it.

## Existing London publication

The pinned `london-public-20261118` inventory is over budget. Remote Git sizes and the served manifest were checked on 19 November 2026:

| Scope | Bytes | MB | Excess bytes |
| --- | ---: | ---: | ---: |
| Total | 558,073,283 | 558.07 | 358,073,283 |
| Geometry | 281,269,092 | 281.27 | 131,269,092 |
| Physics State | 276,804,191 | 276.80 | 126,804,191 |

The earlier 166.79 MB physics measurement covered the `physics/` directory only. This policy also counts trajectories, inactive exports and metadata, accounting for the larger Physics State total. Geometry includes the source material still present in the selected distribution, not just the subset used by a review page.

The gate deliberately rejects this publication. There is no temporary higher limit. Connect an approved, complete optimized snapshot through a reviewed publication change before expecting a green check. The current official website and retained originals remain untouched by this policy change.
