# Physics model: environmental fields

| Domain | Implementation and entrypoints |
| --- | --- |
| Solar radiation | solar/model.py; run_core008_solar.py |
| Flood | flood/model.py; run_core008_flood_swe.py |
| Wind | wind_temperature_teacher/code/wind_core.py; run_core008_scaled_latent*.py |
| Multiscenario latent wind | wind/scaled_latent.py; ../scene_scaled_latent.py (called by run_scene) |
| Temperature | environment-integration/members/yiqi_temperature/; run_core008_temperature*.py |
| Pollution | wind_pollution_code/code/vendor/yuhang/; run_core008_pollution*.py |
| Coupling | wind_temperature_teacher/code/cloud_workflow.py, wind_pollution_code/code/workflow.py and scenario scripts |

Solar and flood cores are packaged by domain; solar_np.py and flood_swe.py retain compatibility imports.
Other delivered packages retain their locations, internal dependencies and provenance records.
The legacy integration entrypoint recorded by this module is python -m pipelines.core008 --dry-run --stage all, run from the original project root.
[MODEL_INVENTORY.md](MODEL_INVENTORY.md) is a historical assessment and does not represent the current task status.
