# Portable preview alignment

The intended demo is the fictional `breathing_cvae` example, not a private personalized route. The selected recorded Asset, payload hash and input identity will be pinned in `DEMO_RESULT.json` after generation on this branch. No city Geometry, road, signal or environmental Asset is a dependency: `derived_from` is empty and all exposures/positions are explicit request parameters. The actual retained request and runtime/model provenance accompany the record.

Coordinates are right-handed local ENU metres with `georeferenced:false`. Origin longitude/latitude/height zeros are placeholders. The fixture travels from `[0,0,0]` to `[120,0,0]`; Z is an arbitrary synthetic plane, not road elevation or height above measured terrain. Rendering applies only `[E,N,U] -> [E,U,-N]`. There is no road snapping, translation, height conversion or city control-point residual to claim.

Time is relative 0–3600 seconds, sampled every 300 seconds, without a UTC epoch. Each feature row drives one five-minute update. Initial breathing is at zero; predictions appear at subsequent boundaries. Exposure rows hold through their intervals and the last row holds at the final boundary. Supplied irradiance is 400 W/m² throughout this fictional fixture. The trajectory interpolates between complete boundary positions. No traffic, pedestrian signals, repeated city fields, live sensors or city clock are displayed.

Missing values are not accepted by this complete-grid demonstration. An absent internal segment must be a separate run, never a deleted row joined by interpolation. Out-of-range values are unavailable. The experimental score and thermal proxy and the uncalibrated latent spread are labelled visibly in the Viewer; they are not clinical risk or health advice.

The prior private terrain-datum and common-observation-clock limitations remain unresolved, documented in the preserved historical alignment record and [FOLLOW_UP.md](FOLLOW_UP.md). This selected synthetic result does not resolve them. Keep this preview standalone and do not publish it as a London-integrated result.
