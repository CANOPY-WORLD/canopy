"""Canopy Method adapter for the original NN4PDEs Linear shallow-water solver."""
import math

from .methods import Fields, geometry_grid


class Flood(Fields):
    def validate(self, request, context):
        _, height, solid = geometry_grid(context)
        from .nn4pdes import source_identity
        source_identity()
        if solid.all():
            raise ValueError("NN4PDEs requires at least one non-solid terrain cell")
        # A solid bit alone is not an impermeable wall in the original solver.
        if (height[solid.astype(bool)] <= 0).any():
            raise ValueError("NN4PDEs building cells require positive raised terrain heights")

    def execute(self, prepared, context):
        import torch
        from .nn4pdes import UpstreamLinear, source_identity
        grid, height, solid, parameters, device = prepared
        # Use one fixed dt, as upstream does; every requested sample lands exactly
        # on a whole number of steps. No adaptive alteration of the original loop.
        steps_per_frame = math.ceil(parameters["frame_seconds"] / parameters["dt_max_s"])
        dt = parameters["frame_seconds"] / steps_per_frame
        solver = UpstreamLinear(height, solid, grid["spacing_m"], dt,
                                parameters["initial_depth_m"], parameters["rain_mm_h"], device)
        first = solver.diagnostics()
        depth, velocity = solver.snapshot()
        depths, velocities, times = [depth], [velocity], [0.0]
        diagnostics = [dict(time_s=0.0, **first)]
        source_rate = float(solver.state["source_h"].double().sum()) * grid["spacing_m"] ** 2
        max_correction = 0.0
        total_steps = parameters["frames"] * steps_per_frame
        with torch.no_grad():
            for frame in range(1, parameters["frames"] + 1):
                for step in range(steps_per_frame):
                    context.checkpoint()
                    solver.step()
                    current = solver.diagnostics()
                    max_correction = max(max_correction, current["height_correction_m"])
                    completed = (frame - 1) * steps_per_frame + step + 1
                    # Bound log volume while keeping long frames observable.
                    if completed % 100 == 0:
                        context.emit("progress", completed=completed, total=total_steps)
                time = frame * parameters["frame_seconds"]
                depth, velocity = solver.snapshot()
                depths.append(depth); velocities.append(velocity); times.append(time)
                diagnostics.append(dict(time_s=time, **current,
                                        rainfall_volume_m3=source_rate * time,
                                        volume_change_minus_rain_m3=current["volume_m3"] - first["volume_m3"] - source_rate * time))
                context.emit("progress", completed=frame * steps_per_frame, total=total_steps)
        return {"grid": grid, "height": height, "invalid": solid, "times": times,
                "fields": {"water_depth": (depths, "m", False), "velocity": (velocities, "m/s", True)},
                "diagnostics": {
                    "quality": "upstream_correction_finite_and_depth_checks_passed",
                    "solver": "NN4PDEs AI4SWE Linear", "upstream": source_identity(),
                    "dt_s": dt, "steps": total_steps, "outer_passes_per_step": 2,
                    "jacobi_sweeps_per_pass": 2, "manning": 0.055,
                    "max_height_correction_m": max_correction, "samples": diagnostics,
                    "assumptions": "Original velocity/free-surface padding; rain on non-solid cells; buildings represented by raised terrain, not C-grid solid walls; no drainage or roof redistribution",
                    "mass_balance": "Reported volume change minus rainfall includes boundary exchange and numerical error; it is not a closed-basin conservation certificate",
                    "validation_scope": "Pinned upstream numerical kernel with a Canopy case driver; no claim of a reproduced full-domain London run"}}
