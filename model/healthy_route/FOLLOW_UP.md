# Private workflow and future publication limits

The participant-free opt-in city preview is now described in [LOCAL_CITY.md](LOCAL_CITY.md). It uses source-aware geometry, exact Asset references, explicit Health-only replay/estimation and recorded-result rendering. Synthetic physiology inputs are labelled and do not reproduce a participant's private run.

Preserved source: branch `preserve/healthy-route-private-20261123` at commit `02024b0` (the maintainer's merge of PR #6). The full source, previous alignment record and 189-file historical hash inventory remain in that immutable history. This follow-up is not a runnable Method in the portable handover branch.

Before proposing a public participant-derived city result:

1. Select an authorized private result and its exact Asset/derived_from chain; do not substitute the fictional preview.
2. Pin the target Geometry, roads and original source terrain/deck data. Resolve the mismatch between preserved terrain/deck Z and metadata declaring ground-relative heights. Record the conversion and control-point residuals; no Viewer-side inferred offsets.
3. Declare the actual health clock and explicit relations to each field. Historical traffic and fields repeat a scenario interval and are not jointly observed UTC data. Identify interpolation, nearest-valid-cell filling and out-of-coverage solar-zero assumptions without relabelling them as measurements.
4. Distinguish modelled pedestrian programs from recorded vehicle-signal states. Display only supported states with explicit labels; absent phase data stays unavailable.
5. Preserve missing masks, show unavailable fields and do not bridge missing trajectory segments. Replace the previous silent omission/filling display path before city integration.
6. Reuse the current city renderer, surrounding buildings, selected-widget clock and declarative Scenario preset. Keep the public layout minimal, scientific details in the supported host, and widget loading recorded-only. Do not activate the retained old UI wholesale.
7. Keep all score/thermal/uncertainty claims experimental. Use an authorized held-out evaluation before any accuracy claim. Source integration alone does not authorize publication of research data/results.

The private personalized optimizer remains outside this PR. Independent geodetic/physiological validation, research-result authorization and hosted publication are still separate requirements.
