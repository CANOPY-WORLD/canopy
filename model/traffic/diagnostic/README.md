# SUMO collision diagnostic

This is an explicit, unregistered research tool, not a production Method. It runs retained native inputs with SUMO 1.28.0. It does not rebuild or calibrate London traffic, recover missing historical signal timing, or register/publish Assets. Outputs stay in a new caller-selected directory.

Install `eclipse-sumo==1.28.0 traci==1.28.0 sumolib==1.28.0 libsumo==1.28.0` in an isolated Python 3.12 environment. Run from the repository root:

```sh
python model/tools/run_sumo_diagnostic.py --network /path/network.net.xml.gz --routes /path/routes.rou.xml.gz --output cache/native-review --begin 31680 --end 32400
python model/tools/run_sumo_diagnostic.py --network /path/network.net.xml.gz --routes /path/routes.rou.xml.gz --output cache/guarded-review --begin 31680 --end 32400 --guard-junctions scenario/imperial_corridor_8km/experiments/traffic-junction-guards.json
```

The first command returns exit code 2 if collisions or teleports occur; this is a failed diagnostic, not a successful accepted simulation. Existing output directories are refused. Interrupt with Ctrl-C; partial directories are not accepted or registered. CPU execution is supported; no GPU is required. A 720-second local run takes roughly one to several minutes and may write several hundred MB of FCD output at 0.1-second sampling.

Each run retains exact input files and hashes, solver version, command, seed, controller hash, FCD trajectories, collision/trip/summary XML, log and `validation.json`. Collision detection remains enabled; collision action is warning (never hiding collisions by removing vehicles), and jam teleportation is disabled. Numerical acceptance requires zero reported collisions and teleports. This check alone does not establish realism or safety outside the tested case.

The optional experimental controller reserves specified junction groups until the previous vehicle's rear clears. Native SUMO signals and car following remain active. Links shorter than 20 m join adjacent conflict areas. It can reduce throughput and must not be described as actual London signal operation. The supplied eight-junction list was selected from a diagnostic AM run's collision locations, so it is a fitted mitigation that needs other demands and periods tested before broader deployment.

## Retained-input experiment, 22 November 2026

Inputs were recovered from `micro_v7_am_peak`, a reconstructed network with regenerated signal plans and a 25% deterministic route sample. The original native inputs for website run `20261026T215940Z_d673c4` were not found. This is therefore a new diagnostic experiment, not an exact reproduction of that old run or a calibrated demand update.

- Network SHA-256: `24e2505f58d18404e9b690f48300535ef5303cc456c5e9286bbcdbfef92e45f6`.
- Routes SHA-256: `5f820869c687184b1fbbc292a809432517cb2cc70090f8c87557406cfdee91d8`.
- Begin/end: 31680–32400 s; first 120 s are empty-network warmup; seed 42.
- Native baseline: 9 junction collisions, 0 teleports, 2,665 arrived, 201 still running.
- Eight guarded junctions: 0 collisions, 0 teleports, 2,596 arrived, 270 still running; arrivals fell by 2.6%. One emergency-braking warning remains.

Actuated-signal detector warnings remain in both runs. Wider validation, reconstruction of questionable junction geometry and authoritative signal timing are unresolved. Keep this experiment separate from the production publication.

## System validation is a separate gate

`diagnostic_pass` now rejects missing actuated-signal detectors, invalid-route
warnings, emergency stops and discarded vehicles as well as collisions and
teleports. A zero-collision run alone never sets `traffic_system_validated` to
true. The local review exporter rechecks the raw outputs rather than trusting a
previous acceptance flag. Earlier guarded results above therefore do **not**
pass the expanded acceptance gate: their unresolved detector warnings require
review. Do not use them to select a production vehicle count.

A follow-up geometry investigation found a stopped-car footprint intersecting
its recorded opposing movement at internal waiting lane `:4046271950_1_0`,
consistent with two collisions against the same stopped vehicle. It also found
an inter-junction collision involving `1181638635` and `5773834786`, connected by
a 0.86 m external lane. These are investigation findings in the retained
reconstruction, not verified corrections to the website's historical run.
Disabling junction advance alone retained all nine collisions. Removing selected
internal waiting positions reduced collisions to six but introduced two emergency
stops, so that candidate was rejected. No load recommendation or publication is
accepted from these trials.

Once the network has passed geometry, connectivity, signal-conflict and numerical
checks, compare several demand levels and seeds with unchanged vehicle mix and
OD distribution. Report simultaneous occupancy (mean/peak), insertion backlog,
arrival throughput, queue growth, waiting time, collisions and emergency stops.
A total departure count is not a simultaneous vehicle target; area density alone
does not determine an acceptable traffic load. Include a demand-free clearance
period to expose gridlock and report unfinished trips rather than hiding them.

The subsequent network candidate used width-aware waiting-position screening,
joined the overlapping short-link pair, and enabled jam-aware detector use
(`jam-threshold=30`) as documented by SUMO for shared turning lanes. It eliminated
the six detector warnings but still produced three collisions and one emergency
stop. It is rejected, not a replacement production network. The disappearing
warnings alone are not evidence that signal timings match London operation.

The investigation also found external edge `215095634` with lane geometry
lengths approximately 0.2 m, 17.7 m and 0.3 m assigned one common simulated length
of approximately 6 m. SUMO may intentionally normalize lane lengths, so length
inequality alone is not proof of a defect; here the extreme mismatch and the
observed lane-choice emergency stop require checking the upstream reconstruction.
Do not select a network variant merely because one demand trace stops colliding.

For scale only, the baseline's 600 s observation window after warmup had mean
simultaneous occupancy 844.8 and peak occupancy 1,458. The complete 720 s run
inserted 2,866 vehicles. These counts describe a failed diagnostic and are **not**
a recommended or calibrated load. Ten thousand simultaneous vehicles would be
about 6.9 times that observed peak; ten thousand total departures is a different
quantity.
