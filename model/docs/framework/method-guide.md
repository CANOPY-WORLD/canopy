# Model / Method development and execution standard

Every registered Method under a shared Model must provide a JSON contract, parameter schema, example and run guide. Input ports can also declare `required_artifacts` to distinguish display layers from computational representations required by the solver. The trusted registry is canopy.models.registry; scenario files cannot specify arbitrary imports or shell commands.

## Integration steps

1. Put reusable solver code in model/src, preserving provenance and licenses. Do not embed scene data, model weights or machine-specific paths in the code.
2. Declare the version, input types, output layer kinds, dependencies, capabilities and documentation paths in model/src/canopy/models/specs/<model>/<method>.json. Parameter schemas must reject extra properties; each parameter needs a description, type, range, default and unit where applicable.
3. Implement describe / validate / prepare / execute / export from canopy.models.interface.Method. Register a trusted adapter; do not execute code supplied in JSON.
4. Read exact-version assets through context.inputs. Write outputs only to context.workspace, leaving inputs unchanged. Do not infer scenario identity from cwd or global environment state.
5. Call context.checkpoint() at safe execution boundaries. Report progress with emit('progress',completed=...,total=...). Declare resume as false when unsupported, and do not invent progress percentages.
6. Return the directory containing manifest.json from export. Preserve coordinates, units, actual times and missing-data masks. The runtime adds a source snapshot, validates the output and registers the assets.
7. Provide a minimal CPU example and appropriate numerical checks. Registered results must remain valid and viewable after cache is deleted.

## Interface

```python
class Method:
    def describe(self): ...
    def validate(self, request, context): ...  # Clear errors, no side effects
    def prepare(self, request, context): ...   # Native inputs within cache
    def execute(self, prepared, context): ...  # Results and diagnostics
    def export(self, result, context): ...    # Self-contained payload directory
```

The framework calls these stages through `canopy.running.runner.run(storage, request, retain=True)`. Request inputs are references within a scenario; parameters describe the physics or algorithm; execution specifies cpu/cuda and thread count. Unknown fields and Method versions are rejected. Defaults are filled before saving the request. Execution status and numerical diagnostics are separate concepts.

## Required guide contents

Purpose and assumptions; exact implementation paths; environment installation; input asset requirements; every parameter; minimal commands; expected outputs; numerical validity checks; resources and cancellation; common errors; and limits on reproducibility. Missing external weights or data must produce an explicit error, without silently substituting synthetic results.

## Common commands, from a Canopy checkout

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[physics]'
.venv/bin/canopy --root . models
.venv/bin/canopy --root . models flood shallow_water
.venv/bin/canopy --root . init demo
.venv/bin/canopy --root . run scenario/examples/canopy/geometry.json --dry-run
.venv/bin/canopy --root . run scenario/examples/canopy/geometry.json
# Replace the physics request's placeholder with the printed geometry asset reference.
.venv/bin/canopy --root . run scenario/examples/canopy/flood.json --dry-run
.venv/bin/canopy --root . run scenario/examples/canopy/flood.json
.venv/bin/canopy --root . validate demo
.venv/bin/canopy --root . view demo GEOMETRY_REF PHYSICS_REF --preset laboratory
.venv/bin/canopy --root . serve
```

Use `canopy --root . demo` to run the complete small example with actual asset references filled automatically. `demo --physics` generates geometry only; `demo --physics flood` adds only flood computation. Prepare real inputs separately for research scenarios.

`canopy cancel SCENARIO MODEL RUN_ID` requests cooperative cancellation; Ctrl-C also records a cancelled state. Cancellation takes effect at checkpoints and does not forcibly terminate an active GPU kernel. Current registered methods do not support checkpoint resume. Rerunning creates a new asset version without overwriting an existing asset.

Other imported Physics4D sources remain compatibility implementations; their historical scripts are not all registered in the shared interface. See migration-status.md and legacy-entrypoints.json. Upgrade integrations individually using this guide, rather than automatically exposing experimental scripts as stable tools.

## Scenario packaging

`canopy pack demo /absolute/output/demo.tar.gz` validates and packages the complete scenario index, all registered assets and provenance. It excludes cache, does not download unknown dependencies and does not publish anything. The output must be outside the scenario asset directory; existing archives cannot be overwritten. Archives use project/<scenario>/... paths. When restoring to a new local data root, place scenario.json in the checkout's metadata root and other assets under the configured data_root.

`canopy run-task SCENARIO TASK --dry-run` checks the request stored in Scenario.tasks. Remove --dry-run to execute the same pinned inputs. The demo saves geometry/solar/flood/wind tasks automatically; physics tasks reference the exact geometry generated for that run, with no later `latest` lookup.

## Physics results as model inputs

`canopy demo --physics temperature pollution` first generates geometry and wind, then passes their exact versions to both coupled models. The two temperature methods share a port and parameter contract; NumPy and PyTorch are separately versioned methods. Pollution requires the native MAC face artifact, which cannot be replaced by a cell-center display slice. Inspect all methods with `canopy models`; each spec includes its guide path.

`source_snapshot.tar.gz` records the Canopy and imported packages actually resolved by the running Python interpreter, including a per-file SHA-256 inventory. `code_revision` identifies that content by hash; the metadata checkout selected by `--root` is not assumed to contain the executed code. Third-party dependency versions are saved separately in environment.json.
