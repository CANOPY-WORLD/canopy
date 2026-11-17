# Geometry model: scenes and dynamic entities

This imported layout record retains paths from the original integration workspace.

| Logical module | Recorded implementation |
| --- | --- |
| Static city: buildings, roads and trees | ../expansion/src/ |
| Scene merging | geometry/south_kensington_core008_merge.py |
| Voxelization | geometry/voxelize_core008.py, validate_padded_voxels.py |
| Draco GLB scene adaptation | voxelization/prepare_glb.py; supports scenes with baked transforms and 1/2/4 m cell-centre sampling |
| Birds | birds/, geometry/birds/ |
| Traffic | traffic/, geometry/traffic/ |
| UAV shapes, stations and scheduling | uav/, geometry/uav/, mfmu-uwm-integration-preview/ |
| Original integration entrypoint | integrate.py |

Static modeling belongs to geometry; expansion retained its physical location to preserve Blender project and snapshot references.
The geometry/ directory still mixed input assets and adapter scripts, with separation planned item by item.
Original integration instructions are in [README.md](README.md), run from pipelines/geometry/ in that layout.
Birds, traffic and UAVs are dynamic entities, but a shared directory does not establish coordinate alignment.
