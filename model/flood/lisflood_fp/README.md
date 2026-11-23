# Recorded LISFLOOD-FP case utility

This standalone helper verifies, builds and reruns the [SK recorded experiment](../../../scenario/imperial_corridor_8km/experiments/sk_lisflood_fp/README.md) from its frozen accepted inputs. It is not a registered Canopy Method and does not create a Scenario task or scientific Asset. The existing `flood.shallow_water@2.0.0` interface remains unchanged.

## Install and obtain the case

Use Python 3.11 or newer (reference: Python 3.12). From the Canopy repository root:

```sh
python -m pip install -e '.[lisflood-case]'
```

The companion data repository contains an immutable ZIP, with the exact native terrain, warmed initial-depth grid, rainfall, boundaries, parameters, masks, dependency locks and patched solver source. Its [data reference](../../../scenario/imperial_corridor_8km/experiments/sk_lisflood_fp/data-reference.json) pins the archive and manifest SHA-256. Obtain the named snapshot from the companion data PR/checkout before deployment; public download links become available only after that data is merged and deployed. Check the archive checksum before extraction. Keep the extracted directory immutable and create build/run directories beside it.

For native compilation, use the bundled environment and README: Linux x86-64, a supported NVIDIA GPU/driver, CUDA, a CUDA-compatible host C/C++ compiler, CMake, Git, NetCDF and NUMA. The reference is RTX 5090, CUDA 12.8 and GCC 13. No CPU implementation parity or cross-GPU validation is claimed. The case's explicit package lock records actual dependencies; it is not a solver binary.

## Commands

The commands below run from a directory containing the extracted `sk-lisflood-fp-20261123/`. `LF_ENV` is the absolute path of the created dependency environment. Its `bin` directory must be on `PATH`, and its `lib` directory on the runtime library search path. Set `CC`/`CXX` to compatible host compilers. GPU architecture `120` is specific to the reference hardware.

```sh
python -m urban_flow.lisflood_case verify --case sk-lisflood-fp-20261123
python -m urban_flow.lisflood_case build --case sk-lisflood-fp-20261123 --work-dir solver-build --cuda-arch 120 --dependency-prefix "$LF_ENV" --jobs 4
python -m urban_flow.lisflood_case run --case sk-lisflood-fp-20261123 --output rain-run --binary solver-build/build/lisflood --build-record solver-build/build-record.json
python -m urban_flow.lisflood_case audit --case sk-lisflood-fp-20261123 --output rain-run
```

The archive's `reproduce.py` is the same standalone helper and can be used without installing Canopy. `build` fetches pinned upstream commit `78dda58284701f99a24ec982dab0de8a28a00246`, verifies the original source hashes, normalizes the three modified source files from CRLF to LF as in the recorded patch, applies the correction, verifies patched hashes and the FP64 configuration, and writes `build-record.json`. Other source bytes are unchanged. `--upstream-checkout` permits a local checkout at the pinned commit. A build record provides reproducibility evidence, not cryptographic authentication of an arbitrary third-party binary.

`run --dry-run` checks the invocation without starting it. `--seconds 1800` runs a 30-minute bounded check; omitting it runs the complete 10800-second event. Existing output directories are rejected, native inputs are copied, and the input archive is not mutated. Ctrl-C interrupts the process; no resume support is implemented. Retry in a new directory. The reference full run takes about 26 minutes and needs several GB of GPU memory; allow at least 15 GB free disk for native outputs and build files.

## Outputs and numerical acceptance

`rain-run/` contains copied inputs, generated `rain.par`, `run-record.json`, `rain.log`, and `results/`. Native outputs include saved water-depth grids, per-step maxima, staggered face velocities, probes and a cumulative external-boundary budget. The runner preserves actual solver times; output times can exceed nominal intervals slightly.

Process completion is recorded separately from numerical acceptance. `audit` checks the completed run identity and input/log hashes, integrates the uniform dynamic rainfall using the recorded ACC update order (previous timestep; zero at the first increment), and compares saved float64 water volumes with initial storage, rain and actual boundary fluxes. It requires finite nonnegative depths and an absolute residual below 0.1 m³ at every checked snapshot, and writes `verification.json`. Native GPU `.mass` does not supply the full independent budget for this case. Field calibration, survey quality and physical model validity are not established by this check.

The public media and float32 GeoTIFFs are recorded presentation products; the distributed command regenerates native solver outputs and volume diagnostics, not a byte-identical rendering of every figure/video. Full raw-download terrain processing and the prior lake-startup recipe are outside this frozen-input reproduction boundary. Future integration must implement the Method lifecycle, scientific Asset contract and explicit EPSG:27700/ODN conversion before selecting this field in the shared 3D Viewer.
