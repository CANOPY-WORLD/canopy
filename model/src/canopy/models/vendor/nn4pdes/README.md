# Pinned upstream NN4PDEs source

[Source repository](https://github.com/Amin-Nadimy/Shallow_Water_Equations_NN4PDEs) · [Exact revision](https://github.com/Amin-Nadimy/Shallow_Water_Equations_NN4PDEs/tree/be4ccdac6270fb0a27a11856d4fafe44cef2ed9e) · [Source inventory](SOURCE.json) · [MIT license](LICENSE)

`AI4SWE_Linear.py` and `LICENSE` are byte-identical copies from commit `be4ccdac6270fb0a27a11856d4fafe44cef2ed9e`. Preserve the authors' notices. The Canopy adapter uses the Linear variant; it does not claim to implement the upstream Quadratic variant or a distributed backend.

Git attributes preserve these two files' original line endings. The upstream Python file is exempt from whitespace cleanup so its existing trailing spaces do not change the pinned hash; this exemption does not apply to Canopy code.

Do not import the upstream script as a normal module: its top-level code reads Carlisle-specific DEM, boundary, flow-rate and observation files, and starts the full case. `canopy.models.nn4pdes` verifies its SHA-256, then compiles the original numerical/state initialization assignments before the first DEM-reading `with` block and the complete `AI4SWE` class. The only initialization assignments replaced by the driver are device selection, `dt`, `dx`, `nx`, `ny` and the printed CFL calculation. All convolution weights, mass weights, Petrov–Galerkin stabilization, friction, padding and two Jacobi sweeps remain unchanged.

Every solver instance has its own execution namespace. Canopy supplies terrain, initial depth and a rainfall source; calls the original `forward` twice per timestep, as the upstream driver does; exports depth as `values_H + values_h`; and maps native velocities to ENU as `(-values_u, values_v, 0)`. Original Carlisle CSV output aliases are not used as scientific component names.

Upstream hard-codes Manning `0.055`; the Method exposes that value as a schema constant. Buildings are raised terrain in this solver. The Canopy solid mask excludes their rainfall and presentation, but it does not add the old C-grid impermeable-face algorithm. Source terms, local units and boundary assumptions are documented in the Method guide. No dynamic downloads, training or learned weights are required.

For an upstream update, review the numerical changes, replace the source and license from a fixed commit, update `SOURCE.json` and the loader's pinned identity, regenerate the independent upstream-driver fixtures, run the numerical/lifecycle tests, and version the Method according to the changed semantics. Never edit the vendored numerical code to make a test pass.

Citation: Boyang Chen, Amin Nadimy, Claire E. Heaney, Mohammad Kazem Sharifian, Lluis Via Estrem, Ludovico Nicotina, Arno Hilberts and Christopher C. Pain, *Solving the discretised shallow water equations using neural networks*, Advances in Water Resources, 2025, article 104903. Cite the source repository as well as the paper.
