# Cropped comparison experiment with all 23 turbines

Outputs are independent; the original region data and solver are unchanged. Paths below refer to the original workstation project.

- All turbine positions and approximate rotor radii come from hub and blade vertices in the original GLB; these are not manufacturer measurements.
- Minimum margins are 5D upstream, 8D downstream and 3D laterally, padded to multigrid-compatible dimensions.
- Domain: 4096×2048×512 m; origin (-1776,-992,0); uniform 4 m grid (128,512,1024), with 67,108,864 cells.
- Terrain is rerasterized from the original GLB, retaining towers, nacelles and other static geometry while removing 69 blades and 23 hubs/spinners.
- The source terrain DSM is approximately 30 m. A 4 m computational grid adds no measured terrain information. Original coverage is 93.75%; uncovered margins use nearest-edge extension.
- Assumes +x inflow and rotors facing the wind, U0=8 m/s, and the above-ground profile 8*(1-exp(-h/12)), without meteorological calibration.
- C′T=4/3 (zero for the control), rho=1.225, axial smoothing sigma=8 m, radial edge width 4 m and a 5-second force ramp.
- Force follows the normalized axial-drag formulation at https://lesgo.me.jhu.edu/actuator-disk.html , using instantaneous weighted disc velocity, without temporal filtering, rotational torque or power prediction.
- Uses AI4Urban reference operators. This independent experiment doubles spatial gradients to correct half-gain on a linear field; 10 MG iterations, zero-gradient outlet velocity, zero outlet pressure and a prescribed inlet profile.
- Control and actuator cases share initial conditions: 400 steps each, dt=0.025 s, 10 seconds total, one saved frame every 20 steps, 21 frames.
- The initial dt=0.1 s trial exceeded the CFL threshold at step 60. It was stopped and retained in `control_dt01_stopped`, excluded from the final comparison.

Run in the workstation UrbanWorldModel project with `.venv-region/bin/python`.

```sh
python input/windfarm_crop/prepare.py --plan-only
python input/windfarm_crop/prepare.py
python input/windfarm_crop/run.py --case control --steps 400
python input/windfarm_crop/run.py --case actuator --steps 400
python input/windfarm_crop/verify.py
```

Outputs are in `output/region_crop/geometry` and `visualizer/scenes/windfarm_crop`.
Displays native 4 m terrain-following slices, control/actuator fields on the same colour scale, control-minus-actuator velocity differences, and whole-farm and individual-turbine views.
This is a startup simulation without fully developed wakes across the domain. It does not establish steady-state behavior, engineering accuracy or electricity generation.
Pressure-projection residuals, boundary placement, grid/time convergence and the turbulence model still require validation.
