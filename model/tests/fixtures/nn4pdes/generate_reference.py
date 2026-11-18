"""Generate tiny regression arrays with the upstream standalone timestep loop.

This intentionally imports no Canopy loader or driver. Only case setup and I/O
are replaced; the original stencil initialization, AI4SWE class and complete
torch.no_grad timestep block execute without editing their numerical statements.
"""
import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "src/canopy/models/vendor/nn4pdes/AI4SWE_Linear.py"
REVISION = "be4ccdac6270fb0a27a11856d4fafe44cef2ed9e"
SHA256 = "cb57dd5b9ab69a7c401a1596546699340e67b32fcc2322f58fb1682e5682cf82"


def cases():
    height = np.zeros((16, 16), np.float32)
    solid = np.zeros_like(height, np.uint8)
    height[8:10, 8:10] = 6; solid[8:10, 8:10] = 1
    yield dict(name="dry_buildings", height=height, solid=solid, spacing=2.0,
               dt=0.1, initial_depth=0.0, rain_mm_h=20.0)
    height = np.zeros((14, 18), np.float32)
    height[3:11, 3:15] = np.linspace(.001, .008, 12, dtype=np.float32)[None]
    solid = np.zeros_like(height, np.uint8)
    yield dict(name="wet_slope", height=height, solid=solid, spacing=3.0,
               dt=0.05, initial_depth=0.1, rain_mm_h=35.0)


def reference(case, steps):
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA256
    tree = ast.parse(raw, filename=str(SOURCE))
    # Keep the complete original initialization prefix, including imports except
    # pandas (used only by the omitted Carlisle file reader).
    cut = next(i for i, node in enumerate(tree.body) if isinstance(node, ast.With))
    replacements = {
        "is_gpu": "is_gpu = False", "device": "device = torch.device('cpu')",
        "dt": "dt = torch.tensor([case['dt']], device=device)",
        "dx": "dx = torch.tensor([case['spacing']], device=device)",
        "nx": "nx = case['height'].shape[1]", "ny": "ny = case['height'].shape[0]",
        "ntime": "ntime = reference_steps",
    }
    prefix = []
    for node in tree.body[:cut]:
        if isinstance(node, ast.Import) and any(a.name == "pandas" for a in node.names):
            continue
        name = node.targets[0].id if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) else None
        prefix.append(ast.parse(replacements[name]).body[0] if name in replacements else node)
    setup = ast.parse("""
bed = torch.tensor(case['height'], dtype=torch.float32)[None, None]
mask = torch.tensor(case['solid'], dtype=torch.bool)[None, None]
values_H = -bed
values_h = bed + torch.where(mask, 0.0, case['initial_depth'])
source_h = torch.full_like(bed, case['rain_mm_h'] / 1000 / 3600)
source_h[mask] = 0
def get_source(time):
    pass
""").body
    kernel = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "AI4SWE")
    constructor = next(node for node in tree.body if isinstance(node, ast.Assign)
                       and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "model")
    # The full loop retains two forward passes, timestep accounting and the
    # original convergence check. CSV writes are unreachable before 900 seconds.
    loop = next(node for node in tree.body if isinstance(node, ast.With)
                and isinstance(node.items[0].context_expr, ast.Call)
                and isinstance(node.items[0].context_expr.func, ast.Attribute)
                and node.items[0].context_expr.func.attr == "no_grad")
    start = ast.parse("start = time.time()").body
    namespace = {"case": case, "reference_steps": steps, "print": lambda *a, **k: None}
    module = ast.fix_missing_locations(ast.Module(body=prefix + setup + [kernel, constructor] + start + [loop], type_ignores=[]))
    exec(compile(module, str(SOURCE), "exec"), namespace)
    assert namespace["istep"] == steps, "Original driver terminated early"
    return {"depth": (namespace["values_H"] + namespace["values_h"])[0, 0].numpy().copy(),
            "native_u": namespace["values_u"][0, 0].numpy().copy(),
            "native_v": namespace["values_v"][0, 0].numpy().copy()}


def main():
    torch.set_num_threads(1)
    output = Path(__file__).parent
    records = []
    for case in cases():
        arrays = {"height": case["height"], "solid": case["solid"]}
        for steps in (1, 7, 20):
            for name, array in reference(case, steps).items():
                arrays[f"{name}_{steps}"] = array
        filename = case["name"] + ".npz"
        np.savez_compressed(output / filename, **arrays)
        records.append({k: v for k, v in case.items() if k not in ("height", "solid")} |
                       {"file": filename, "steps": [1, 7, 20],
                        "sha256": hashlib.sha256((output / filename).read_bytes()).hexdigest()})
    record = {"upstream_revision": REVISION, "upstream_sha256": SHA256,
              "generator": "generate_reference.py", "torch": torch.__version__,
              "numpy": np.__version__, "device": "cpu", "cases": records}
    (output / "reference.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
