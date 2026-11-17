# Local physics model inventory

Assessment date: 2026-09-10. Based only on local files, checkpoints and records from that assessment.
This is a historical inventory; paths and run progress describe the source workspace at the recorded dates.

| Model | Type | Local status at assessment |
| --- | --- | --- |
| DIGIT wind | 3D U-Net AI surrogate | `environment-integration/members/yiqi_temperature/models/velocity_calculation` contains code and `assets/digit.pth`; inferred 3 frames each on local core008 geometry at 1 m and 2 m |
| regression1024 wind | VAE + latent U-Net | `wind_temperature_teacher` and `wind_pollution_code` contain code; the corresponding wind and VAE weights are missing and cannot be replaced by DIGIT weights |
| SCALED Tutorial wind | VAE + latent U-Net AI surrogate | Added `/home/yl222/workspace/SCALED-Tutorial/weight/inference.pth` (approximately 831 MiB) and `compression.pth` (approximately 291 MiB); `run_core008_scaled_wind_temperature.py` was integrated with core008 and running in the background. Equivalence to the previously specified regression1024 checkpoints was not verified |
| One-step temperature | 15-channel 3D U-Net | Both the original model and `wind_temperature_teacher/weights/temperature_one_step.pt` were present; network tensors were verified identical, so these count as one model with two wrappers; strict loading passed |
| Rollout temperature | 22-channel 3D U-Net | `environment-integration/members/yiqi_temperature/models/rollout_surrogate/outputs` contains weights; strict loading passed; no temperature inference was performed in this assessment |
| Physical temperature solver | Numerical model | Code in `environment-integration/members/yiqi_temperature/models/physical_model`; a simplified reference thermal solver also exists in `wind_temperature_teacher/code/cloud_workflow.py`. Requires wind, initial temperature and thermal boundary/source parameters |
| Pollutant concentration | DigitUNet3D AI surrogate | Code in `wind_pollution_code/code/vendor/yuhang`; concentration-model and matching encoder weights are missing |
| Pollutant transport | Numerical model | `wind_pollution_code/code/vendor/yuhang/data_generation/physical_transport.py` and related files contain transport and data-generation code |
| Health response and environmental routing | Placeholder directories | `environment-integration/members/ruhang_health_response` and `guanhao_routing` contained only placeholder READMEs |

`pipelines/geometry/mfmu-uwm-integration-preview` is a separate UAV scheduling module, not a wind or temperature solver.

Assessment results and accuracy limits are in `output/core008/physics/digit_smoke/README.md`. Temperature models require temperature history and thermal conditions. Only weight loading was checked; this does not count as completed joint inference for a new area.

The added SCALED job wrote to `output/core008/physics/scaled/` under the project root. At assessment, logs showed 10/40 wind steps completed and no temperature output yet; that directory's `run.log` recorded subsequent progress. The job covered `[64,2944,3136]` (Z,Y,X) at 1 m spacing, spanning the original horizontal building extent with some padding rather than the complete 4096×4096×128 m domain. Buildings above 64 m were truncated. This transfer to new geometry had no CFD or observational ground-truth validation.

## 2026-09-12 additions: flood, solar and temperature

| Model | Type | Local status at assessment |
| --- | --- | --- |
| Shallow-water flooding | Numerical model: PyTorch stencil operations following the NN4PDEs approach in paper S030917082500017X | `pipelines/physics/flood_swe.py` + `run_core008_flood_swe.py` ran rainfall-flooding cases on core008 at 1 m and 4 m; the authors' original code is in `~/workspace/Shallow_Water_Equations_NN4PDEs` (Carlisle case, not used directly) |
| Solar illumination | Numerical model: PyTorch tensor layers, ray sliding-maximum doubling network, horizon layers and ASHRAE clear-sky conditions | `pipelines/physics/solar_np.py` + `run_core008_solar.py` computed summer/winter-solstice shadows, SVF and irradiance on core008 at 1 m (`output/core008/physics/scaled_latent/solar/`) |
| Yi Qi 3-D physical temperature model | Numerical model: surface energy balance + 3-D advection–diffusion | First ran on core008 on 2026-09-12 (`run_core008_temperature3d_solar.py` builds a cache from SCALED wind), coupled to solar (`temperature3d_solar/`); the full-day chain uses `run_core008_temperature3d_diurnal.py` |
