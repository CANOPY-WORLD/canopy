# Reproducible native traffic demo

[Model](../../README.md) · [Diagnostic investigation](../diagnostic/README.md)

These explicit experimental utilities rebuild the London traffic demonstrator
from raw OSM, rather than treating a display-network reconstruction as the missing
original SUMO input. They are **not a registered Canopy Method or Asset**. Opening
a viewer does not run them, and they do not replace the published Scenario data.

## Source and assumptions

The November 22 experiment uses the Geofabrik Greater London extract dated
2026-11-20, licensed under OpenStreetMap's ODbL. Retain its URL, downloaded PBF,
extracted XML and hashes. `extract_traffic_osm.py` selects highway ways having a
node inside the requested bounds, retains full way nodes, and includes relevant
turn-restriction members. It can miss a segment crossing the bounding box with
no node inside. Retained restrictions are not necessarily accepted by netconvert:
filtered roads, access restrictions and import ambiguities remain in its logs.

The projection is local WGS84 AEQD using the Scenario's longitude/latitude
origin, in metres. Left-hand driving is explicit. The core Scenario is about
8 × 8 km; imported roads include a routing buffer. OSM layer numbers become
estimated 5 m separations, **not surveyed elevation or terrain clearance**.
Lane connections, actuated signal plans and road priorities are generated from
OSM attributes and SUMO heuristics, not verified against London's live controls.

The demo uses upstream waiting (`contPos=0`) while preserving internal driving
lanes and external lane connectivity. Signals are rebuilt with separate incoming
approach phases, 4 s yellow and 2 s all-red. A 30 s jam threshold enables native
actuated-detector eligibility on shared turn lanes. Vehicles wait at the stop
line while a crossing foe passes (`jmAdvance=0`), with 2.5 m extra clearance
(`jmExtraGap=2.5`). These policies apply across the network; there is no fitted
junction-ID list, forced-speed controller, disabled collision detection or
teleport-based gridlock removal in the fresh demo.

Six illustrative classes are routed: car 60%, taxi 10%, bus 8%, light goods 15%,
heavy goods 5%, motorcycle 2%. Bus trips are generic OD trips, not GTFS services.
This mix and demand are synthetic. Departure rate is not simultaneous occupancy.
Lane-based continuous lane changes last 2 s; numerical steps and recorded samples
are 0.1 s. Vehicle dimensions and FCD front-bumper references are retained.

## Reproduce

Run from repository root with Python 3.12. Keep experiments under `cache/`; copy
accepted native bundles into private retained storage before removing cache.

```sh
python3 -m venv cache/sumo-env
cache/sumo-env/bin/pip install eclipse-sumo==1.28.0 sumo-data==1.28.0 traci==1.28.0 osmium==4.3.2
# Optional mapped-crossing export dependencies:
cache/sumo-env/bin/pip install pyproj==3.7.2 shapely==2.2.0
# Download and retain the dated PBF separately; record its source URL and hash.
cache/sumo-env/bin/python model/tools/extract_traffic_osm.py \
  cache/fresh-traffic-demo/source/greater-london.osm.pbf \
  cache/fresh-traffic-demo/source/extracted-roads.osm.xml \
  --bbox -.267 51.465 -.134 51.548
cache/sumo-env/bin/python model/tools/build_traffic_demo.py network \
  --osm cache/fresh-traffic-demo/source/extracted-roads.osm.xml \
  --scenario scenario/imperial_corridor_8km/scenario.json \
  --output cache/demo-network
cache/sumo-env/bin/python model/tools/build_traffic_demo.py upstream-waiting \
  --network cache/demo-network/network.net.xml --output cache/demo-protected
cache/sumo-env/bin/python model/tools/build_traffic_demo.py demand \
  --network cache/demo-network/network.net.xml --output cache/demo-demand \
  --rate 6000 --duration 600 --seed 42
cache/sumo-env/bin/python model/tools/run_sumo_diagnostic.py \
  --network cache/demo-protected/network.net.xml \
  --routes cache/demo-demand/routes.rou.xml --output cache/demo-run \
  --begin 0 --end 3600 --seed 42 --lane-mode continuous --record-signals
python3 model/tools/summarize_traffic_demo.py cache/demo-run
```

Commands refuse existing output directories. Each diagnostic retains exact
network/routes copies and hashes, command, solver version, logs, collisions,
trip information, summary and full FCD. Preparation retains commands and hashes.
For seed/load comparisons, `resample_traffic_demo.py` samples explicit routes
with replacement from a validated OD pool and preserves its vehicle types.
Use a new output directory and report its sampled mix and insertion backlog.

`audit_signals` in `traffic.demo_network` checks all signal programs for two
protected greens on connections marked as foes. It checks consistency with the
native foe matrix, not the correctness of that matrix or real-world signals.

## Acceptance and review

`diagnostic_pass` rejects collisions, teleports, emergency stops, invalid routes,
invalid departure positions, missing actuated detectors, discarded vehicles and
truncated runs. Emergency braking is reported separately; it is not silently
counted as a pass or as a physical collision. `traffic_system_validated` remains
false: these necessary checks do not establish universal correctness or measured
London realism. Check arrival completion, queue clearance and multiple seeds
before proposing a demo load. Do not infer capacity from area alone.

`export_traffic_demo_scene.py` exports a checked interval for offline recording:
actual sparse samples, front-bumper XYZ, heading, slope, dimensions and native
road geometry. It rejects failed runs and incomplete intervals. It does not
invent absent vehicles or signal states. This experimental JSON is not a public
Asset encoding or registered widget. The older XY exporter refuses nonzero
recorded elevation/slope rather than dropping those fields.

For synchronized signals, pass `--record-signals` to the diagnostic runner. It
retains native `SaveTLSSwitchStates` output in `signals.xml`, including actual
actuated changes. The exporter maps each native connection's `linkIndex` to
that recording; it never reconstructs colors from a nominal cycle. Missing
recordings leave lamps dark. Replay holds the last recorded state only inside
the exported interval.

```sh
cache/sumo-env/bin/python model/tools/export_traffic_demo_scene.py \
  cache/demo-run cache/demo-review/scene.json \
  --begin 550 --end 611 --center 600 3340 --radius 210 \
  --osm cache/fresh-traffic-demo/source/extracted-roads.osm.xml
```

Explicit OSM crossing-way markings provide zebra, dotted or lined crossings.
Unknown/unmarked ways receive no invented stripes. Projection and network
offset are preserved; centerlines are clipped to native road surfaces and
paint elevation follows nearby lanes. Fixture placement, stripe widths and
pole dimensions are illustrative, not a survey. This does not add pedestrian
simulation, infer priority from paint or change routes. The facilities rerun
used the same 1,000-departure seed-42 inputs: all trip attributes matched the
previous run, with zero collisions/teleports and three emergency brakes.

The offline review video shows this native diagnostic geometry, not the existing
city's terrain/buildings. Only its MP4/poster may be shared under the user's
video-review request; publishing native payloads or replacing production requires
separate task authorization.

## References

- [SUMO OSM import](https://sumo.dlr.de/docs/Networks/Import/OpenStreetMap.html)
- [Native connection parameters](https://sumo.dlr.de/docs/Networks/PlainXML.html)
- [Vehicle junction parameters](https://sumo.dlr.de/docs/Definition_of_Vehicles,_Vehicle_Types,_and_Routes.html)
- [Safety checks and limits](https://sumo.dlr.de/docs/Simulation/Safety.html)
- [Recorded traffic-light states](https://sumo.dlr.de/docs/Simulation/Output/Traffic_Lights.html)
- [FCD coordinates](https://sumo.dlr.de/docs/Simulation/Output/FCDOutput.html)
- [Greater London extracts](https://download.geofabrik.de/europe/united-kingdom/england/greater-london/index.html)

## November 22 results and blocker

The retained source extract has SHA-256
`3774937db3908111c24c26b9781bd399b67b5a978b5f4e67f1e58446c348b566`.
The tested protected network has SHA-256
`ccbc42e04aef68d143a5bd716249fea06eca47775dfded03a0fb9e49be07af97`.

| Demand over 600 s | Peak concurrent | Mean concurrent, 300–900 s | Arrivals | Collisions | Teleports |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1,000, original OD seed 42 | 919 | 758.0 | 1,000 | 0 | 0 |
| 1,000, resampled seed 43 | 907 | 752.6 | 1,000 | 0 | 0 |
| 3,000, resampled seed 44 | 2,760 | 2,314.6 | 3,000 | 4 | 0 |

The two low-load runs each recorded three emergency-braking events. All trips
cleared by 2,206.6 s and 2,340.6 s respectively. The higher load cleared by
3,311.3 s but **failed acceptance**. It must not be used to recommend 2,760 or
10,000 simultaneous vehicles. About 750 mean / 900 peak is only a tested
low-load diagnostic preview, not an established capacity or production setting.

The four high-load collisions include short-link spillback and turning-body
conflicts. Native links `509244114` and `70521361#0` provide only 0.2 m and
5.39 m respectively between junctions. Increasing generated turning radius
and automatic join distance did not remove these links. A subsequent general
short-link consolidation attempt crashed netconvert 1.28 with SIGSEGV, both
when reading native XML and when rebuilding from explicit node/edge/connection
files. Discarding loaded signals did not fix that crash. The failed candidate
was not used, exported or published; the exact commands, XML inputs and a gdb
backtrace remain in the private experiment bundle. Its exploratory join code
is not included in the supported preparation utilities.

The implementation PR remains a draft until the geometric/network failures can
be repaired and higher-load, multiple-seed checks pass. The existing production
Scenario pin and public native datasets are unchanged. See the small
[experiment results](../../../scenario/imperial_corridor_8km/experiments/traffic-demo-results.json)
for the measured counters and explicit validation status.

The larger-radius candidate (12 m radius / 30 m automatic join distance, native
sublane motion) also failed: 1,000 departures, four collisions and 15 vehicles
still halted at the end of 3,600 s. It is a rejected investigation, not a new
default. The exposed geometry options support reproducible diagnostics only.
