# Local Health input and result Assets

Health does not replace shared London fields. Inputs are exact-version same-Scenario Assets resolved by the standard runner; all derived outputs have new identities. Preparation and calculation write only into a new workspace and retained storage, never into source city payloads.

## Input bundles

The city Geometry and Physics references share a verified public snapshot bundle. `city-inputs.json` declares immutable file hashes, field encodings, masks, times, origin, coordinate/vertical transformations and source identities. Connector-aware preparation retains a new bundle derived from both preceding city Assets, with pinned Overture segment/connector source hashes and mapping/exclusion audit. It does not add these bulky resources to Git.

The physiology Physics Asset declares artifact `physiology_inputs` at `physiology.json`, plus a `model_identity` artifact containing packaged weight/scaler hashes. Import with `model/tools/prepare_health_physiology.py --workspace WORKSPACE --profile PROFILE.json`. The public fixture is `model/tests/fixtures/canopy/city_physiology_inputs.json`; it is explicitly synthetic.

The profile has exactly `format: canopy-health-physiology-v1`, `input_kind: synthetic` or `authorized_history`, an explicit timezone-bearing `start_utc`, `features`, `initial_breathing_bpm`, and `reference`. Features are one explicitly constant row or 289 five-minute rows, each ordered as PM2.5, air temperature, humidity, activity, steps, walking, hour sine and hour cosine. Time-of-day features are recalculated from the supplied template clock in Europe/London; this is not a common city observation epoch. The reference contains positive `q10`, `q90`, `scale` values in breaths/min, with q90 at least q10.

Optional `history` contains twelve complete past five-minute rows of those eight features followed by breathing. Authorized-history mode requires it. With history, the packaged model warms its recurrent state using those supplied past values; without history it starts from zero recurrent memory and the explicit initial breathing. A constant template is an intentional scenario assumption, never an implicit missing-data fill. Missing/nonfinite history or features fail validation. Authorized inputs and their derived results remain private and are not served as static web files.

## Results and provenance

`city_walk` derives from exact `geometry`, `city`, and `physiology` references. `city_breathing` derives from an aligned exposure, its exact city input and a physiology input. `city_exposure` derives from exact Geometry/city/source-route references. Each chain is retained by the standard runner together with request, environment, runtime source/weights, checksums and diagnostics. No real-city result is committed as the public example.

`recording.json` retains raw native samples separately from estimated Health inputs, including masks represented by null, donor cells/distances/weights and replay source times/cycle numbers. Repeating fields does not create observations. The standard time-series encoding has no null representation, so incomplete series remain in the declared recording artifact and are not zero-filled into a misleading complete layer. Missing trajectory segments are rejected before inference and shown as gaps if encountered by the viewer.

Trajectory Z is height above the pinned local terrain. `scene_m` retains the explicit display transform to [east, ground+height, -north]. Control-point residuals check internal reconstruction, not survey accuracy. Signal metadata distinguishes assumed pedestrian programs from recorded vehicle states; signal placement offsets are Scenario display assumptions only.

The packaged weights remain model resources under `model/src/healthy_route/assets/`, with checksum enforcement. They are not copied into Scenario defaults or public city field files. The only public result already included is the separate fictional portable inference fixture described in `model/healthy_route/ALIGNMENT.md`.
