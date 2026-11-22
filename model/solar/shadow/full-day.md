# Full-day solar experiment

`model/tools/run_solar_day.py` streams a new clear-sky computation through the imported ShadowNet, HorizonNet and ASHRAE kernels. It is a reproducible experiment entrypoint, not the registered `solar/shadow@1.0.0` Method, whose interface accepts prescribed directions. No website load starts a solver.

Use Python 3.11+, NumPy and PyTorch (the `physics` extra). CPU is supported; city-scale runs should use a compatible CUDA installation. The run refuses existing output directories. Ctrl-C cancels without a complete inventory; partial output cannot be exported. Resume is unsupported. Native inputs and retained outputs belong in private scene storage, not Git or the public snapshot.

```sh
python model/tools/run_solar_day.py --terrain /absolute/private/terrain \
  --output /absolute/private/runs/solar_day_UNIQUE_ID \
  --day 2026-06-21 --timezone Europe/London --frames 100 --device cuda
python model/tools/export_solar_day.py /absolute/private/runs/solar_day_UNIQUE_ID \
  /absolute/private/exports/solar_day_UNIQUE_ID \
  --scenario scenario/imperial_corridor_8km/scenario.json
python model/tools/check_contract.py /absolute/private/exports/solar_day_UNIQUE_ID/manifest.json
canopy --root . import-run imperial_corridor_8km /absolute/private/exports/solar_day_UNIQUE_ID
```

Inputs are the real, aligned `bed_4m_yx.npy`, `footprint_4m_yx.npy`, `canopy_4m_yx.npy` and `metadata.json`. Metadata declares the grid dimensions, spacing, ENU lower corner and geographic origin. The bed includes DTM plus building heights in ODN. Rows point north and columns east. Missing or nonfinite geometry is rejected. Input copies and hashes, executed source, dependency versions and parameters are retained. No substitute geometry is generated.

The date and IANA timezone define midnight to the following midnight. Exactly `--frames` samples include both endpoints; 100 samples on a 24-hour day have 872.727-second intervals. Actual UTC dates are passed to the NOAA solar-position calculation, including the previous UTC date at British summer midnight. DST days use their actual duration. Every sample is freshly computed, including zero irradiance at night. See [NOAA calculation details](https://www.gml.noaa.gov/grad/solcalc/calcdetails.html).

Sky view uses 16 azimuths and altitudes 2, 7, …, 87 degrees. Albedo is 0.2 and canopy direct-beam transmittance is 0.3. Roof cells exclude the ground-reflection term. Native float32 irradiance and binary shadow frames are losslessly compressed incrementally; GPU memory does not scale with the number of frames. Daily energy uses trapezoidal integration at actual sample times. Runtime and output size depend on geometry and compression.

The 8 m browser derivation averages valid non-building ground cells in each 2×2 block. All-building blocks are explicitly masked. Shadows use a majority with ties shaded; irradiance is retained as float16. This is a spatial display approximation, never temporal interpolation. Scientific exports preserve these exact values in `npy_frames`, with epoch, coordinates, masks and source provenance. Their surface height is zero relative to local ground, matching the Scenario; original absolute ODN geometry remains explicitly identified in provenance. No registered geometry dependency is invented.

Acceptance checks cover finite nonnegative irradiance, nighttime zeros, 100 increasing times, coordinate conventions and source checksums. Tests cover the London summer UTC offset, DST duration, noon timing, obstacle shadow direction and masked aggregation. Clear sky is not observed weather. Limitations include 2.5D horizontal surfaces, no facades, no off-domain obstacles, coarse horizon integration and canopy-cell-only tree attenuation. Numerical checks do not establish observational accuracy.
