# Examples

[Canopy](../../README.md) / [Scenario](../README.md) / Examples

| Directory | Contents |
| --- | --- |
| [canopy/](canopy/) | V2 Scenario and Method requests, including geometry, solar, flood, wind, temperature and tracer |
| [contract-v1/](contract-v1/) | Small JSON mesh, scalar, vector, trajectory and time-series payloads |
| [contract-v1.1/](contract-v1.1/) | Binary frame arrays, a height grid, mask and sparse trajectories |

Run commands from the repository root after [installation](../../model/README.md#run-the-small-example):

```sh
python model/tools/check_contract.py scenario/examples/contract-v1/manifest.json
python model/tools/check_contract.py scenario/examples/contract-v1.1/manifest.json
canopy --root . init demo
canopy --root . run scenario/examples/canopy/geometry.json --dry-run
canopy --root . run scenario/examples/canopy/geometry.json
```

Physics requests contain explicit input placeholders. Replace them with the exact Asset references returned by your own geometry/wind runs, and set `scenario_id` consistently. Use `canopy demo` for a complete example that fills these references automatically. Per-Method assumptions, parameters and run commands are documented under [Model](../../model/README.md#registered-methods).
