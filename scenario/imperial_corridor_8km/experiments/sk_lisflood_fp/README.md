# South Kensington LISFLOOD-FP recorded experiment

This independent experiment contributes a 1 m rainfall result and a rerunnable frozen-input case within the London Scenario. It does not change the active Scenario tasks, Asset selection, publication pin or existing neural shallow-water Method.

The companion data repository contains snapshot `sk-lisflood-fp-20261123`: a report page, illustrated workflow, terrain/startup/result diagnostics, MP4/GIF, selected GeoTIFFs, and a native input/source/dependency ZIP. [data-reference.json](data-reference.json) locks its manifest and ZIP hashes. The report is intended for the [Scenario data site](https://canopy-world.github.io/canopy-scenario-imperial-corridor-8km/snapshots/sk-lisflood-fp-20261123/); this URL is pending companion data deployment. Review the companion data PR first and verify its deployed manifest before advertising the link as available. This reference is an experiment download lock, not a replacement `publication.json`.

## What is reproduced

[Run guide](../../../../model/flood/lisflood_fp/README.md): verify inputs, build the pinned LISFLOOD-FP 8.3 GPU ACC FP64 solver with the included experimental conservation patch, run in a new directory, and independently audit the water balance. The ZIP starts from the accepted modified terrain and warmed lake state. Raw-data terrain reconstruction, six-hour initialization rerun and exact media regeneration are not included in that command.

The source is pinned to commit `78dda58284701f99a24ec982dab0de8a28a00246`; the three patched files, original and patched hashes, GPL licence, environment locks, case parameters and source notices accompany the archive. An unmodified official binary does not reproduce this corrected numerical configuration.

## Physical meaning

The 3200 × 3200 grid covers E 525000–528200 and N 177800–181000 in EPSG:27700 at 1 m. Elevations use ODN; water depth is relative to the modified bed. The displayed SK focus is not an official campus polygon. A 90-minute synthetic uniform storm applies 49.95 mm over the complete domain; the recorded solver run continues for another 90 minutes. No infiltration, sewer drainage, roof redistribution or fixed-stage water source is enabled. Rain is applied to land, roofs and lakes; ground-flood metrics exclude roof/initial-water cells using the provided masks.

Preparation used depression-filled DTM plus DSM heights within OSM buildings, then estimated lake beds and a six-hour static check. The final normal-water reference uses DSM surface levels (14.98 m ODN for Long Water/Serpentine, 24.54 m for Round Pond); depths remain trial estimates. Earlier terrain-stage metadata is historical and superseded by the normal-water setup where it differs. Large terrain corrections and deep building-edge cells remain review flags.

The recorded 3-hour run reached 10800.069185625774 s, with a maximum sampled absolute water-balance residual of 4.7630130097786605e-6 m³. The deepest land cell is 5.277 m, an isolated building-edge location needing terrain review. These are synthetic model results, not measured flood validation.

The video/GIF shows only 0–105 minutes in seven seconds (70 display frames). It interpolates approximately 15-minute native snapshots for display, retains existing water in teal and buildings in grey, and uses the flood-depth scale for land. The maximum-depth GeoTIFF covers the full 180-minute run and is not a simultaneous inundation extent. Float32 presentation fields retain their CRS and nodata masks; volume audits use native float64 depths.

## Integration boundary

A complete Canopy Method adapter, V2 Asset registration, exact input/output ports, local 3D transform and shared Viewer playback are future work. The current London spatial conventions must not be inferred from these ODN GeoTIFFs. Keep the report as an independent experiment until those interfaces are implemented and tested. The companion snapshot retains EA, OpenStreetMap/ODbL, UKCEH and solver source notices.
