"""Run the pinned upstream AI4SWE Linear kernel without its Carlisle file I/O.

The numerical assignments and AI4SWE class are compiled directly from the
byte-identical upstream script. Only the case driver is supplied by Canopy.
Each instance has a separate namespace because the upstream class uses globals.
"""
import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import torch


UPSTREAM_REVISION = "be4ccdac6270fb0a27a11856d4fafe44cef2ed9e"
UPSTREAM_SHA256 = "cb57dd5b9ab69a7c401a1596546699340e67b32fcc2322f58fb1682e5682cf82"
VENDOR = Path(__file__).parent / "vendor" / "nn4pdes"
SOURCE = VENDOR / "AI4SWE_Linear.py"


def source_identity():
    """Verify the installed source and return its redistributable provenance."""
    identity = json.loads((VENDOR / "SOURCE.json").read_text())
    if (identity["revision"] != UPSTREAM_REVISION
            or identity["files"][SOURCE.name]["sha256"] != UPSTREAM_SHA256
            or hashlib.sha256(SOURCE.read_bytes()).hexdigest() != UPSTREAM_SHA256):
        raise ValueError("NN4PDEs source differs from the pinned upstream revision")
    return identity


def _initialize(shape, spacing, dt, device):
    source_identity()
    tree = ast.parse(SOURCE.read_text(), filename=str(SOURCE))
    # The first `with` opens the Carlisle DEM. Nothing from case I/O is executed.
    boundary = next(node.lineno for node in tree.body if isinstance(node, ast.With))
    supplied = {"is_gpu", "device", "dt", "dx", "nx", "ny", "CFL"}
    body = [node for node in tree.body
            if isinstance(node, ast.Assign) and node.lineno < boundary
            and not any(isinstance(target, ast.Name) and target.id in supplied
                        for target in node.targets)]
    classes = [node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == "AI4SWE"]
    if len(classes) != 1:
        raise ValueError("Expected one upstream AI4SWE class")
    namespace = {"torch": torch, "nn": torch.nn, "F": torch.nn.functional,
                 "np": np, "device": torch.device(device),
                 "ny": shape[0], "nx": shape[1],
                 "dt": torch.tensor([dt], dtype=torch.float32, device=device),
                 "dx": torch.tensor([spacing], dtype=torch.float32, device=device)}
    # This is trusted, hash-checked package source, never code from a request.
    exec(compile(ast.Module(body=body + classes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


class UpstreamLinear:
    """Case state around the original collocated-grid AI4SWE.forward method."""

    _arguments = ("values_u", "values_uu", "values_v", "values_vv", "values_H",
                  "values_h", "values_hp", "b_u", "b_uu", "b_v", "b_vv", "dt",
                  "rho", "k1", "k2", "k3", "eta1_p", "source_h", "dif_values_h",
                  "dif_values_hh", "values_hh", "values_hhp")
    _outputs = ("values_u", "values_v", "values_h", "values_hh", "b", "dif_values_h", "sigma_q")

    def __init__(self, height, solid, spacing, dt, initial_depth, rain_mm_h, device="cpu"):
        self.state = state = _initialize(height.shape, spacing, dt, device)
        bed = torch.tensor(height, dtype=torch.float32, device=device)[None, None]
        self.solid = torch.tensor(solid, dtype=torch.bool, device=device)[None, None]
        # Upstream: H = -bed elevation, h = free-surface elevation, H+h = depth.
        state["values_H"] = -bed
        state["values_h"] = bed + torch.where(self.solid, 0.0, initial_depth)
        state["source_h"] = torch.full_like(bed, rain_mm_h / 1000 / 3600)
        state["source_h"][self.solid] = 0
        self.model = state["AI4SWE"]().to(device).eval()
        self.model.requires_grad_(False)
        self.spacing = float(spacing)
        self.dt = float(dt)

    @torch.no_grad()
    def step(self):
        # Preserve the two outer passes and two inner Jacobi sweeps of upstream.
        for _ in range(2):
            result = self.model(*(self.state[name] for name in self._arguments))
            self.state.update(zip(self._outputs, result))

    @property
    def depth(self):
        return self.state["values_H"] + self.state["values_h"]

    def snapshot(self):
        depth = self.depth[0, 0].cpu().numpy().copy()
        # Conv2d is cross-correlation: upstream xadv differentiates towards west,
        # yadv towards increasing rows (north). Never swap the exported axes.
        east = -self.state["values_u"][0, 0]
        north = self.state["values_v"][0, 0]
        velocity = torch.stack((east, north, torch.zeros_like(east))).cpu().numpy().copy()
        return depth, velocity

    def diagnostics(self):
        tensors = [self.state[name] for name in self._outputs]
        if not all(bool(torch.isfinite(value).all()) for value in tensors):
            raise ValueError("NN4PDEs produced a nonfinite state; result not accepted")
        depth = self.depth
        correction = float(self.state["values_hh"].abs().max())
        # Original standalone driver stops when this correction exceeds 10 m.
        if correction > 10.0:
            raise ValueError("NN4PDEs height correction exceeds the upstream 10 m limit")
        minimum = float(depth.min())
        if minimum < -1e-6:
            raise ValueError(f"NN4PDEs negative water depth ({minimum:g} m); result not accepted")
        return {"min_depth_m": minimum, "max_depth_m": float(depth.max()),
                "height_correction_m": correction,
                "volume_m3": float(depth.double().sum()) * self.spacing ** 2}
