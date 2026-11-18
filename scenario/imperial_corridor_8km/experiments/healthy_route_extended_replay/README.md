# Healthy-route extended-replay experiment

This profile is exclusively for the healthy-route research model. It is not a replacement for the canonical London Scenario, its physical recordings, its default clocks, or other contributors' experiments. It is not an additional public Scenario or catalog entry.

The common location remains `imperial_corridor_8km`. Experiment identity is `healthy_route_extended_replay_v2`; inputs and results are retained independently in a separate local research workspace. The canonical `scenario.json`, `publication.json` and locked publication manifest remain unchanged.

`profile.json` explicitly opts into repeated pollution, air temperature and recorded traffic across a maximum 13-hour physiological horizon, starting at the scenario clock label 08:50. The underlying recordings are approximately ten minutes; repetition does not create new measured data. Smooth environmental wrap-around, nearest-valid-cell estimates, tracer-derived illustrative PM2.5 and independent modelled pedestrian lights belong only to this experiment. Native traffic trajectories are not altered. Source masks remain retained even where the experiment uses derived fill values.

Solar follows the chosen June/December clear-sky day without repeating. The thermal proxy adds a configurable irradiance term to air temperature; CVAE inputs retain air temperature and historical activity. Walking/running changes travel and exposure timing, not the activity conditioning. These combinations are exploratory, not weather-consistent seasonal forecasts, validated physiology or safety guarantees.

The preparation tool explicitly copies this profile into a private versioned input bundle. It does not activate a task on canonical London or publish data. A future move to newer city assets requires rebuilding/verifying the walking network and field-coordinate mapping, never replacing the receiver's city with this historical snapshot.

See the [model guide](../../../../model/healthy_route/README.md) for setup and execution.
