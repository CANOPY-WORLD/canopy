# High-resolution single-actuator-disc experiment

An independent rotor axial-force test that leaves the windfarm 8 m scene unchanged. The assumed domain is 128×64×64 m,
with disc centre (32,32,32) m, diameter 16 m, initial/end-boundary inflow 8 m/s, C′T=4/3 and rho=1.225.
Both 1 m and 0.5 m grids advance through 20 seconds; the 0.5 m no-force control also advances every timestep.
The 0.5 m grid is (z,y,x)=(128,128,256), with 4,194,304 cells.

Operators follow AI4Urban. This independent experiment multiplies x/y/z gradient kernels by 2, giving a linear-field gain check of (-1,1,1).
The original half-gain version is retained on the workstation at `visualizer/scenes/actuator_lab_halfgradient`.
The large windfarm solver, parameters and saved data are unchanged. This case uses a free-slip bottom and excludes terrain, towers, nacelles and blades.
Both axial boundaries retain the original fixed u=-8; other velocity and pressure conditions follow the reference. These are not strictly nonreflecting wind-tunnel boundaries.

Actuator-disc reference: https://lesgo.me.jhu.edu/actuator-disk.html :
F = -rho/2 * A * C′T * Ud |Ud| * R(x), with integral R dV=1.
This implementation uses the instantaneous weighted disc velocity, a 2-second startup ramp, an axial Gaussian with sigma=2 m and radial
logistic smoothing of width 1 m. Smoothing widths are identical on both grids. Half-step forces are applied before and after advection/pressure advancement.
Checks cover non-increasing airflow kinetic energy under the force, normalization error and CFL. There is no temporal filtering of disc velocity or coarse-grid correction.
There is no swirl, turbulence model or power model; the experiment does not establish engineering accuracy or resolve actual rotating blades.

Run from the original workstation project directory using the `.venv-region` Python environment:

```sh
python input/actuator_lab/run.py --cell 1
python input/actuator_lab/run.py --cell 0.5
python input/actuator_lab/run.py --cell 0.5 --ct 0
python input/actuator_lab/verify.py
```

Results are in `visualizer/scenes/actuator_lab`: 41 horizontal hub-height slices per case, final 3D velocity,
complete parameters and diagnostics. Verification checks constant uniform wind in the control and compares disc velocities and aligned slices across resolutions.
The joint grid/timestep comparison is not an independent spatial or temporal convergence study, and no measured-data comparison was performed.
Web viewer: `/viewer/actuator-lab/`.
