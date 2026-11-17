# Model contribution standard

[Component overview](README.md) · [All component standards](docs/framework/contributing.md)

This standard applies to new Methods and changes to registered implementations. The [Method guide](docs/framework/method-guide.md) defines the full lifecycle; the [data protocol](docs/framework/protocol-v2.md) defines exported data semantics.

## Required interface

| Stage | Responsibility | Permitted writes |
| --- | --- | --- |
| `describe()` | Return the versioned spec: ports, parameters, outputs, dependencies and capabilities | None |
| `validate(request, context)` | Check physical assumptions, exact input versions and required computational artifacts | None |
| `prepare(request, context)` | Build native inputs inside `context.workspace` | The current run's workspace |
| `execute(prepared, context)` | Compute, emit progress, check cancellation and record numerical diagnostics | The current run's workspace |
| `export(result, context)` | Return a self-contained V1.1 payload directory with a valid manifest | The current run's workspace |

The shared runner validates and retains exports, then registers Assets. A Method must never register partial results itself, modify an input Asset, infer inputs from the newest directory, or write directly to the London dataset. A successful process exit is separate from numerical acceptance.

## Files required for a Method

1. Add or adapt reusable code under `model/src/`. Preserve imported notices and provenance.
2. Add `model/src/canopy/models/specs/<model>/<method>.json` and update that Model's `model.json`.
3. Register a trusted adapter in `canopy.models.registry`; JSON cannot provide Python imports or shell commands.
4. Supply an example request under `model/tests/fixtures/canopy/` and a guide under `model/<model>/<method>/README.md` (a shared guide is allowed for equivalent backends).
5. Declare exact port kinds and `required_artifacts`. A GLB mesh, a heightfield, a cell-center velocity volume and native MAC faces are different interfaces.
6. Give every parameter a type, description, default or required status, valid range and units where applicable. Reject unknown properties.

The guide must include installation, Python and dependency requirements, CPU/CUDA support, input preparation, complete commands, expected files, numerical acceptance, resource use, cancellation and known limits. State required external data or weights explicitly. Do not silently substitute synthetic data.

## Execution and reproducibility

Use `context.inputs` for exact-version inputs, `context.emit` for measured progress, and `context.checkpoint()` at safe boundaries. Preserve real sample times, masks, units, spatial transforms and `derived_from`. Report errors that make a result invalid; do not weaken acceptance thresholds to make a test pass. Keep requests, dependency versions, source identity and diagnostics in the retained provenance.

Declare unsupported capabilities honestly. Resume and distributed execution are not implemented by the current Methods. Compatibility research scripts are not registered merely because their source is present.

## Verify the change

Run from the repository root after installation:

```sh
python -m unittest discover -s model/tests -v
python model/tools/check_contract.py model/tests/fixtures/contract-v1/manifest.json
python model/tools/check_repository.py
# Optional numerical smoke run, isolated from the London Scenario:
python model/tools/run_example.py --physics solar flood wind temperature pollution
```

Add a behavioral or numerical check when changing solver behavior or an interface invariant. Reuse small fixtures; the only curated Scenario is `imperial_corridor_8km`. The example tool creates a disposable metadata workspace under cache and prints its location. Run subsequent `canopy` commands with `--root` pointing to that workspace.

After changing a spec, update its guide and regenerate the explanation site's inventory with `python model/tools/build_review_inventory.py`. Do not claim that a newly exposed Method has reproduced a historical full-domain London run unless that run was actually executed and validated.
