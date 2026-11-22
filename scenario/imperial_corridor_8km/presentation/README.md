# I-HUB interior presentation

`ihub-interior.json` is the declarative preset for the retained White City I-HUB
concept office v10 (`ihub_office_journey_20261117_v10`). It is enabled by the `london-ihub-interior-20261122` snapshot. The shared viewer inserts its widget directly after
White City campus when the snapshot includes this object as `scene.interior`.

Export the retained source with `model/tools/export_ihub_interior.py`, passing
`run` (the retained v10 directory), `georef` (its retained White City fit),
`scenario/imperial_corridor_8km/scenario.json`, and a new `output`
directory. The exporter verifies source mesh hashes, preserves binary payloads,
and adds a root transform. Validate the result with
`python model/tools/check_contract.py <output>/manifest.json` before retaining it.

The public payloads are lossless gzip copies of the aligned
`building.glb` (684,724 bytes compressed) and `office.glb` (2,801,428 bytes
compressed). No geometry simplification or texture resizing was applied.
Keep the retained originals and provenance bundle; include the aligned hashes,
source hashes and alignment record in the data snapshot’s interior provenance.
Publication requires approval of that snapshot and the website change.

The authored office floor is 32.2677965163 m above the original model datum.
The recorded geographic fit has a 1.58 m median residual and is not a survey.
The office is a concept layout, with its accepted source layout discrepancy
preserved. The viewer approaches from the current exterior camera and reaches the retained
common-room arrival pose at 4 seconds, 1.68 m above the office floor. It then
moves along the clear common-room space and turns to inspect the seating until
30 seconds. These are presentation camera keyframes, not simulated pedestrian
trajectories. It preserves the full building shell and roof, leaves the
office intact, and displays the city using its original flat height datum.
Exiting restores the existing landmark and terrain.

The preset also restores the continuous warm-white ceiling from the retained
v10 layout footprint at local height 3.77 m and thickness 0.10 m. This authored
presentation element was omitted by the source visible-only GLB export. The
full exterior shell and roof remain intact.
