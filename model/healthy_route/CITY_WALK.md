# Local endpoint-selected city walks

`healthy_route/city_walk@1.0.0` calculates a shortest-distance walking path between
two explicitly selected nodes on the pinned current-city walking network, then
evaluates it with the packaged CVAE and the conditional input policy in
[CITY_PHYSIOLOGY.md](CITY_PHYSIOLOGY.md). It does not reintroduce the private wave
optimizer or claim to find the healthiest route. The shared city renderer remains
the presentation surface; no separate planning page is required.

The local [source-aware connection adapter](CITY_CONNECTIONS.md) prepares a new
immutable network using pinned junction IDs and pedestrian access rules. It adds
supported shared-use paths and keeps unresolved gaps visible. Route calculation
does not repair topology in the Viewer or mutate that network.

## Inputs and execution

Install Python 3.11+ and `pip install -e '.[healthy-route]'`. The exact Geometry and city Physics Assets must share a verified snapshot. The physiology Asset declares `physiology.json` using [the input contract](../../asset/docs/health-inputs.md); weights/scaler are packaged and verified. The public example uses a synthetic template, not a participant history. See [complete runnable setup](LOCAL_CITY.md).

The request template is
`model/tests/fixtures/canopy/city_walk.json`. Replace its three input references
and two node placeholders with exact local Asset versions and node IDs. Every
parameter is documented in the Method spec. `origin` and `goal` are required;
`speed_m_s` defaults to 4/3 and `departure_s` to 0. The remaining parameters are
the explicitly labelled physiology assumptions. Default optional follow-up is
600 elapsed seconds; it is not a maximum route duration. Routes and follow-up
must fit the declared Health coverage described below.

```sh
canopy --root cache/health-example run cache/health-example/city-walk-request.json
python -X utf8 model/tools/serve_city_health.py --workspace cache/health-example --site cache/health-viewer --port 8826 --recorded --select-routes
```

The second command requires a separately prepared static city build, the explicit
`crossing-native-request.json` and the existing saved physiology preview. It only loads
metadata and the saved result on startup. In the local Health panel, select START
and END by clicking highlighted walking points, enter **Start time**, then press
**Calculate route**. The browser submits the two node IDs and `departure_s` to
the loopback service. Method, input Assets, speed and proxy policy remain fixed.
The time control uses the pinned solar clock's declared origin (08:50 here),
not UTC or live weather. Changing it shifts environmental sampling and private
history together; it hides stale scores until calculation succeeds. The final
departure must leave room for both the route and the configured follow-up within
the Health horizon. Invalid or out-of-coverage requests are rejected upstream.
The same controls work with `lite=1` and `lite=0`. **Saved preview** restores the
prepared replay without calculation. Selection hides the previous result so its
scores cannot be mistaken for scores for pending endpoints.

The local map draws a six-pixel pink route with a contrasting outline, enlarged
START/END pins and a walker whose screen size remains readable while zooming.
These are presentation overlays, including through buildings; they do not change
recorded coordinates, validate access or represent physical person/road sizes.
Absent segments remain gaps. **Frame route** shows the whole walk; **Focus walker**
centres a closer view; **Follow walker** keeps camera angle and zoom as playback
or seeking moves the person. Manual camera movement and Frame route stop following.
**Playback speed** offers 1×, 5×, 10×, 30× and 60×. This scales the replay clock
for the walker and recorded health values together; it does not change walking
speed, departure time, exposure calculations or the model update interval.

## Health-only time extension

`field_time_policy` defaults to `native`, retaining the original 0–600-second
restriction for requests that do not opt in. The separate Scenario experiment
`extended-health-profile.json` selects `health_replay` for the local Health app.
It repeats each pollution/temperature source sequence on the continuously
advancing Health clock. `field_replay_blend_s=60` reproduces the original local
smoothstep blend from the last 60 seconds toward the first frame, including the
first cycle. At 600 seconds the Health input returns to source second zero; the
native city field at second 600 still retains its actual last source sample.

The Health horizon is the lesser of remaining model-template coverage and the
unrepeated solar day coverage. The original runtime has 86,400 seconds, and the
configured history offset is 39,600 seconds: **46,800 seconds (13 hours)** remain
at departure zero. A later departure reduces the remaining allowance. The
breathing model keeps its recurrent state and five-minute update schedule across
all field boundaries. Sunlight follows its declared day clock (offset 31,800 s);
it is not put on the ten-minute loop. Traffic/signal data is not extended.

This is a Health research scenario, not new city observations or a forecast.
The source Assets, masks and other widgets remain unchanged. Native values after
their own source interval stay null; separately named model-input estimates use
the replay. Each sample records source seconds, cycle index, blend weight and
donor details. `temporal_policy` records the horizon and transformation. The
time extension does not relax the existing spatial donor-distance limits.

## Results and acceptance

The optional local `wide-temperature-health-profile.json` keeps the same 13-hour
clock but permits a nearest valid temperature cell within **256 m**, instead of
128 m. This is a user-selected Health-only spatial estimate, not additional city
data or a validated temperature reconstruction. The default Method parameter
remains 128 m. Pollution's 16 m bound and all native masks remain unchanged.
The display labels the current temperature source distance, highlights distances
above 128 m as wider-area estimates and retains unavailable native values.
Required input gaps are checked before loading the conditional inference runtime;
an unresolved gap reports its field, position and Health time. The time replay
does not itself fill spatial gaps.

The separate `interpolated-environment-health-profile.json` selects
`spatial_missing_method=idw4`, `max_pmx_fill_m=64` m and
`max_sunlight_fill_m=256` m, with the existing 256 m temperature bound. For a
missing pollution or sunlight value, the adapter uses up to four nearest valid
cell centres within the bound, weighted by inverse squared distance and
normalized to sum to one. A single available donor is labelled as such. Valid
native values, including zero, are never spatially averaged or replaced.
Donors must be valid at the requested source time, including both frames when
temporal interpolation is needed. No spatial-domain or time-domain extrapolation
is permitted by this policy. A completely unsupported gap remains an error.

The pollution interpolation is applied before CVAE inference and before adding
the declared background proxy. Sunlight estimates feed the thermal proxy/score;
they do not change the CVAE air-temperature feature. Solar follows its original
day clock; only pollution and temperature use the declared periodic replay.
The result retains separate `sunlight_estimate`, `pollution_proxy` and raw fields,
plus source cells, source values, distances, weights and time transformation.
Every spatially estimated input is labelled in the local Viewer. Such estimates
may smooth pollution peaks or shadow boundaries; neither local physical accuracy
nor clinical validity is established. Existing Method defaults remain nearest
sampling, 16 m pollution bound, and native-only sunlight (`max_sunlight_fill_m=0`).

Each successful explicit calculation retains a new immutable Physics Asset with
exact `derived_from` references to Geometry, current fields and the physiology Asset.
Outputs include `recording.json`, ground-relative ENU trajectory, available series,
request, environment, source snapshot, checksums and diagnostics. The display uses
the native terrain/deck conversion documented in [CITY_ALIGNMENT.md](CITY_ALIGNMENT.md).
No existing result, input bundle or source route is overwritten.

Routing uses Dijkstra distance on source walking edges. It preserves vertices,
rejects disconnected endpoints and rejects paths longer than declared Health
coverage. It adds no missing links. Signal waits are enabled only by the explicit
crossing policy below; the default `none` preserves previous requests. A calculated walk is simulated research output,
not recorded participant movement or safe navigation advice.

Source masks remain unchanged. Bounded donor estimates remain separately labelled
and audited. If required model inputs cannot be obtained within the declared
limits, calculation fails explicitly; the saved preview remains recoverable.
Missing solar values outside the declared estimation policy leave the thermal score unavailable. Health score and thermal
proxy remain heuristic, latent spread is not calibrated total uncertainty, and
engineering success establishes no physiological or clinical accuracy.

The solver checks cancellation during graph search, alignment and inference.
Use the standard `canopy cancel SCENARIO healthy_route RUN_ID` command; closing
the browser is not cancellation. Resume and GPU execution are unsupported.
Memory includes the current network, a bounded field-frame cache and private
runtime; elapsed time depends on disk checksums and CPU inference. Two same-server
calculations cannot run concurrently. Do not run a separate writer against the
same private workspace at the same time.

Verification covers endpoint-dependent geometry, reversed paths, disconnected
and over-duration rejection, preservation of input geometry, cancellation, API
policy restrictions and browser map selection/playback. Private smoke results
are recorded separately in the local validation report, never as clinical tests.

The optional [crossing policy](CITY_CROSSINGS.md) restores modelled pedestrian lights,
stationary waits and current recorded vehicle-gap estimates where supported.

Generated playback samples are unique on the scenario clock after adding the
selected departure. If adjacent floating-point elapsed values map to the exact
same scenario timestamp, only the later generated sample is retained. Distinct
scenario timestamps are not rounded or shifted; source observations, route/wait
events and physiological integration timing remain unchanged.
