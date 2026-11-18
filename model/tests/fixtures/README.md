# Development fixtures

[Canopy](../../../README.md) / [Model](../../README.md) / Fixtures

These are small protocol examples and request templates, not curated Scenario entries. London remains the only case under `scenario/`.

| Directory | Contents |
| --- | --- |
| [canopy/](canopy/) | V2 request templates for all eight registered Methods and a synthetic Scenario example |
| [contract-v1/](contract-v1/) | Small JSON mesh, scalar/vector, trajectory and time-series payloads |
| [contract-v1.1/](contract-v1.1/) | Small binary frame arrays, height grid, mask and sparse trajectories |
| [nn4pdes/](nn4pdes/) | Synthetic upstream-driver numerical reference arrays and their reproducible generator |

```sh
python model/tools/check_contract.py model/tests/fixtures/contract-v1/manifest.json
python model/tools/check_contract.py model/tests/fixtures/contract-v1.1/manifest.json
python model/tools/run_example.py --physics solar flood wind temperature pollution
```

The example tool prints a disposable metadata workspace. Use `canopy --root /path/to/that-workspace ...` for later commands. Replace request placeholders with the exact references returned by your runs. Follow the [Method guides](../../README.md#registered-methods) for assumptions and parameters; never use fixture results as observations of London.
