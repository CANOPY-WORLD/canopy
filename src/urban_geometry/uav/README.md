# UAV models

Original generic designs, without association with a specific manufacturer. All use GLB / glTF 2.0 with embedded materials and no external texture dependencies.

| File | Type | Approximate dimensions (width × length × height, metres) |
| --- | --- | --- |
| `quadcopter.glb` | Aerial-photography quadcopter with gimbal camera and landing gear | 0.69 × 0.69 × 0.405 |
| `hexacopter_cargo.glb` | Cargo hexacopter with cargo box, camera and GPS | 1.358 × 1.228 × 0.517 |
| `fixed_wing.glb` | Fixed-wing UAV with front propeller, tail and wheeled landing gear | 2.36 × 1.542 × 0.719 |

Units are metres. GLB uses +Y up and +Z forward; the source Blender scripts use +Z up and -Y forward. Models are centred laterally, with the ground near zero height.

Bodies, rotors and attachments remain separate meshes. Each `Rotor_*` / `Nose_propeller` node is centred on its rotor for future rotation animation. Current files are static and contain no animation, collision bodies or flight-dynamics parameters.

Matching PNG previews were rendered after reimporting the exported GLBs. `validation.json` records file sizes, mesh counts, triangle counts and import validation.

Regenerate from the original source checkout:

```bash
blender --background --python pipelines/geometry/uav/generate_models.py
```

Requires Blender 4.2 or a compatible version. Running the script overwrites models, previews and validation reports with matching names in this directory.
