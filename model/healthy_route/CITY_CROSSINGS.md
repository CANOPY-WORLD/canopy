# Local crossing waits and current traffic

The opt-in `healthy_route/city_walk` policy `modelled_with_current_traffic` restores
pedestrian WAIT/WALK heads and stationary crossing waits on the current mapped
route. Select `crossing-health-profile.json` from the existing Scenario experiment.
This remains local research simulation, not real-world traffic control or navigation.

## Exact inputs and mapping

The current main publication reference was checked on 25 November 2026 and matches
the local `london-complete-tube53-20261125` snapshot at scenario repository revision
`1ef461432127e66934c100cab1af7d9d14cbc068`. The native traffic source is the newer
`london-traffic-native-20261122` payload, not the old private 16 November traffic.
Its file SHA-256 is `76f4f497901bfe5a54ee99b6d7da04c1dcb97a203cefb7a2e705866f8eaf13f7`.

Both `transportation-source/connectivity-segments-2026-10-21.0.parquet` and
`scenes/imperial_corridor_8km/context/traffic-native.json` are already declared
artifacts in the exact city input Asset. Results retain the same exact Geometry,
city Physics and physiology input dependencies, plus source hashes and the native
traffic's network/FCD/exporter/signal provenance. No source Asset is changed.

Crossings come from Overture's source-segment `crosswalk` subclass/ranges.
`city_crossings.py` splits existing edges at range boundaries without connecting
separate paths or moving geometry. Consecutive pieces of one crossing receive one
admission check, not a wait at every subdivision. Only supported ground-level
source paths are tagged. Crosswalk tags do not prove that physical traffic-light
hardware exists; all added pedestrian heads are labelled model assumptions.
Untagged or unsupported crossings remain unknown rather than invented.

## Explicit timing and footprint assumptions

Pedestrian phases use 45 s red, at least 15 s green, and 10 s clearance by default,
with a fixed 2 s admission margin. Green extends when required by the full tagged
crossing length and selected speed. The phase offset is a deterministic hash of
the crossing ID, retained in the result. These parameters are scenario assumptions,
not measured or inferred from the SUMO vehicle lamps.

Native traffic provides 410 vehicle frames at 0.1 s over 680–720.9 s, and a
declared signal interval [680,721). Health explicitly maps its seconds to
`680 + (Health time modulo 41)`. This repeats a short simulation clip; it is not
additional observations, a calibrated traffic forecast or the same observation
epoch as pollution/temperature. The last vehicle frame holds only to the declared
end. No movement is interpolated across the loop seam or absent vehicle identities.
Native times and bytes remain unchanged. The ordinary Traffic widget keeps its
own original clock and display.

Where a tagged crossing intersects native ground-band lanes and remains within
the clip region, swept vehicle bounding discs block entry for the whole crossing
plus margin. The front bumper is converted to body centre using the supplied type
length and heading. Native type dimensions are retained, with 1.4 m spatial and
1 s temporal buffers. Sparse arrivals/departures are handled without joining
different vehicles. Outside coverage, vehicle clearance is explicitly unavailable;
only the modelled pedestrian gate applies. A clip without a sufficiently long gap
causes an explicit failure, not a silently unsafe release.

Traffic is based on a flat native datum while Health uses restored terrain.
The `|native Z| < 2 m` ground band is an assumption, not surveyed grade separation.
Nearby vehicle lamps use the explicit display transform `terrain + native Z`,
retaining their original positions separately. This is not validated vertical
registration. Recorded vehicle phases are displayed separately from modelled
pedestrian permission and do not control the saved vehicles.

## Waiting and physiology

Wait events are inserted before alignment and inference. All wait positions are
verified on the selected path. Arrival time, environmental samples, private-history
clock and five-minute recurrent updates advance during waits. Integration is split
at wait boundaries without resetting model state. Recorded output includes movement
state, wait countdown, total wait time and integrated pollution-proxy exposure
during waits. Health scores keep the existing heuristic formula; waiting does not
imply a fixed score penalty or necessarily a lower score at every instant.

Historical humidity/activity remains the conditional template. This does not
simulate or validate a physiological rest/recovery response. Missing environmental
inputs still follow the existing labelled bounded-estimate policy. Full source
crossing and native traffic hashes, mapping counts, timing assumptions and limits
are retained in `crossing_summary` and shown in the local details panel.

## Checks

Run the full Python/Viewer suites and repository/contract checks. Synthetic tests
cover partial-tag mapping, preserved topology, grouped crossings, vehicle body
references, sparse membership, replay seams, unavailable coverage, rejected gaps,
and exposure/model updates during a stationary wait. Browser checks must verify
red waiting, release/motion, countdown, score replay, native vehicle phase changes,
pause/seek/restart and 60× playback. Submitted-revision evidence is recorded in VALIDATION.md. Private inputs are never published.
