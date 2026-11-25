# Source-aware local walking connections

The local Health input adapter uses the Overture release pinned by the displayed
city (`2026-10-21.0`). It matches each eligible display line to a unique source
segment, then uses that segment's connector IDs and pedestrian access metadata.
The original city files and earlier walking-network Asset remain unchanged.

Two overlapping lines do not establish a walking junction. Overture explicitly
defines connectivity through [shared connectors](https://docs.overturemaps.org/guides/transportation/segments-and-connectors/).
Its [access rules](https://docs.overturemaps.org/guides/transportation/roads/)
also distinguish unconditional use from private, directional and timed access.

## Preparation and provenance

This is an offline input conversion in
`model/src/healthy_route/source_walking_network.py`; routing and physiological
inference remain in the registered `healthy_route/city_walk` Method. Opening a
widget only reads the saved result. No public city payload or traffic replay is
modified, and the physiology input Asset is neither copied into the new city
input nor exposed through the static site.

Install `overturemaps==2.1.1` in the preparation environment, in addition to the
Health dependencies. The runtime server does not need to download maps. Download
both segment and connector GeoParquet with the same explicit release and bounded
London area; retain their `.state` records beside them:

```sh
python -m overturemaps download --bbox=-0.259,51.469,-0.141,51.544 -f geoparquet --type=segment --release=2026-10-21.0 --stac -o cache/segments.parquet
python -m overturemaps download --bbox=-0.259,51.469,-0.141,51.544 -f geoparquet --type=connector --release=2026-10-21.0 --stac -o cache/connectors.parquet
python model/tools/prepare_city_connections.py --workspace cache/health-inputs --request cache/health-inputs/city-walk-request.json --segments cache/segments.parquet --connectors cache/connectors.parquet --origin NEW_START_NODE --goal NEW_END_NODE --output-request cache/health-inputs/city-connected-walk-request.json
```

Select explicit new node IDs from the prepared graph; old coordinate-only node
IDs are not transferable junction identities. The adapter refuses existing
staging/output targets. It retains a new Geometry/Physics bundle derived from
the exact preceding Geometry and city Physics Assets. Public payload bytes are
copied unchanged; the new graph, per-source acceptance/exclusion audit, raw public
transportation metadata, hashes, release/download coverage and preparation source
are retained with it. The output request keeps the same physiology Asset and Health
time policy. Execute that request with the normal runner, inspect its result, then
select its explicit request/result index for the local service. Preparation does
not replace a running preview or publish anything.

## Mapping and conservative limits

Source geographic coordinates use local equirectangular XY with radius 6,378,137 m,
the pinned scene longitude/latitude origin and cosine of origin latitude for east.
The adapter verifies agreement with the current 0.1 m display geometry within
0.081 m, including clipped boundaries. Accepted connector coordinates are rounded
to that same precision. The audit records actual maximum residuals. This is an
explicit local mapping, not a certified geodetic survey.

- Only a shared source connector can join separate paths. Nearness, a visual
  intersection or identical coordinates with different connector IDs cannot.
- Footway/path/pedestrian/steps and living streets use an explicit research
  pedestrian-class default. Cycleway/bridleway/track require an unconditional
  explicit `foot` permission. Ordinary vehicle road centrelines are not added as
  invented pavements. This is not a complete street-navigation network.
- Private/customer/time/direction-dependent pedestrian access, denials, unresolved
  pedestrian turn restrictions and partial grants are conservatively excluded.
  The adapter does not infer permission or evaluate an invented UTC date.
- Hidden display segments remain real gaps. Indoor, tunnel, inactive and varying
  level paths remain excluded. Bridges require the existing native deck support;
  a shared connector with more than 0.1 m height disagreement stays separated.
- Unmatched/ambiguous source geometry and collapsed connector positions are
  reported, not guessed. Whole-segment exclusions can omit otherwise usable
  portions; remaining disconnected components are expected.
- Route geometry retains every prepared vertex. Regular internal cuts and via
  nodes preserve endpoint selection, loops and parallel paths without creating
  new road junctions. No signal programs, signal waits or clearance are inferred.

Terrain/deck height semantics, environmental masks, bounded donor distances and
the optional 13-hour Health-only replay are unchanged. Graph connectivity does
not guarantee available environmental inputs: a route can still fail explicitly
when its required model inputs are unavailable. In END selection, mint points
share START's component; grey points do not. Scores remain experimental, with no
clinical accuracy or safe-navigation claim.

## Verification

`test_source_walking_network.py` checks shared-connector recovery, coincident and
crossing-but-unconnected lines, missing segments, foot-access rules, private and
tunnel exclusions, height separation and geometry mismatch. Run the full Python
suite, Viewer tests, contract/repository checks and the actual local endpoint
browser checks. Saved model results, network comparisons and remaining exclusions
are documented separately in the PR validation record. Participant-dependent runs require the authorized private
input bundle and must be reported as not run if it is absent.
