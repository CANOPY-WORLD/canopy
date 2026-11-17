# CANOPY

Canopy is a physics simulation framework for urban environments. Build geometry, run physical models and explore recorded results through a shared visualizer.

The framework is organized around **Scenario / Asset / Model**. A Scenario describes a scene and owns its assets; Models are computational tools shared by all scenarios; Assets store geometry and physics results. **Running executes computations, and Visualization reads and presents results**, using the same data contract.

## Architecture

```mermaid
flowchart TB
    S["Scenario · Declarative JSON<br/>Space / assets / tasks / view"]
    subgraph M["Model · Code shared by all Scenarios"]
        G["Geometry tools<br/>Generate or process geometry"]
        P["Physics simulators<br/>Versioned Methods"]
    end
    subgraph A["Asset · Owned by the current Scenario"]
        GA["Geometry Asset<br/>GLB + computational representation"]
        PA["Physics Asset<br/>Physical data + metadata"]
    end
    R["Running<br/>Invoke the shared Method lifecycle"]
    V["Visualization<br/>Shared template + Scenario configuration"]
    S -->|Fixed inputs and parameters| R
    R -->|Invoke Method| G
    R -->|Invoke Method| P
    G -->|Produce| GA
    GA -->|Computational input| P
    P -->|Produce| PA
    PA -.->|Input to subsequent computation| P
    S -->|Versioned index| A
    GA -->|Read directly| V
    PA -->|Read directly| V
    S -->|Select layers and preset| V
```

Geometry can go directly to the Visualizer. Physics can depend on geometry or on existing physics results. The Visualizer reads exported, validated results; opening the current viewer does not start a computation. Model adapters convert native solver data into standard assets, while solver logic stays in shared code.

## Scenarios and assets

```mermaid
flowchart LR
    subgraph SA["Scenario A · south_ken"]
        CA["scenario.json<br/>Origin / bounds / tasks / visualization"]
        AA["A's Geometry and Physics Assets<br/>Immutable versions + derived_from"]
        CA -->|Index| AA
    end
    M["Shared Model / Method registry<br/>Common interface, different implementations"]
    subgraph SB["Scenario B · white_city"]
        CB["scenario.json<br/>Origin / bounds / tasks / visualization"]
        AB["B's Geometry and Physics Assets<br/>Immutable versions + derived_from"]
        CB -->|Index| AB
    end
    CA -->|Task request| M
    CB -->|Task request| M
    AA -->|A's inputs| M
    AB -->|B's inputs| M
    M -->|Register A's outputs only in A| AA
    M -->|Register B's outputs only in B| AB
```

Asset references such as `asset_id@1` resolve only within the current Scenario. `derived_from` pins input asset versions, and cross-scenario references are rejected. Adding a scenario primarily adds declarative configuration and private scene data; reusing a tool does not require copying its solver.

| Module | Required content / inputs | Outputs / responsibility |
| --- | --- | --- |
| **Scenario** | `scenario_id`, title, ENU origin and vertical datum, bounds, asset index, tasks, visualization | `project/<scenario>/scenario.json`; declares tasks and views without executing scripts |
| **Geometry Asset** | Provenance and coordinates, GLB display geometry, and computational representations such as a heightfield or mask as required by the Method | `*.asset.json` + `manifest.json` + `.glb` / `.npy` / `.json` |
| **Physics Asset** | Owning scenario, input versions, layer kind, array shape / axes / dtype, units, spatial sampling, time, missing-data mask | Scalar fields, vector fields, trajectories or time series, with provenance and checksums |
| **Model / Method** | Model identity; Method version, input ports, parameter schema, dependencies, output types, capabilities, run guide and example | `describe / validate / prepare / execute / export`; produces self-contained results |
| **Running** | Scenario ID, Model / Method / version, exact asset references, parameters, execution device | Status, logs, numerical diagnostics and source snapshot; registers assets after success |
| **Visualization** | `template: standard`, preset, asset and layer selection, visibility, camera and time mode | Shared scene, layer controls, camera, timeline, picking and legends |

**The storage standard is JSON + GLB + NPY.** Three.js implements the viewer; Blender / Python generate data. GLB describes display geometry and does not automatically replace a solver's computational grid. Large display sequences support loading NPY frames on demand. Full 3D fields can be retained as artifacts; the current viewer displays explicitly exported horizontal slices. See [Protocol v2](docs/framework/protocol-v2.md).

## Model execution

```mermaid
flowchart LR
    D["describe<br/>Version / ports / schema / guide"]
    Q["Run request<br/>Scenario + input references<br/>parameters + execution"]
    C["validate<br/>Version / parameters / input compatibility"]
    P["prepare<br/>Prepare native inputs in cache"]
    X["execute<br/>Solve + progress + cancellation checks"]
    E["export<br/>manifest + payload<br/>Coordinates / units / time / provenance"]
    K["Framework validation<br/>Files / hashes / encoding / ownership"]
    A["Scenario-owned Assets<br/>Register immutable versions"]
    F["failed / cancelled<br/>Retain status and logs"]
    D -.-> Q
    Q --> C --> P --> X --> E --> K --> A
    P -.->|Failure or cancellation| F
    X -.->|Failure or cancellation| F
    E -.->|Failure or cancellation| F
    K -.->|Validation failure| F
```

Failed or cancelled runs do not register assets. `--dry-run` validates a request; `--no-retain` leaves trial results in cache. Each Method's diagnostics and acceptance checks assess numerical validity; file-format validation alone cannot establish physical accuracy. See the [Method guide](docs/framework/method-guide.md) for integration requirements and commands.

## Visualization

```mermaid
flowchart TB
    C["Scenario.visualization<br/>template / preset / layers / camera / time_alignment"]
    A["Geometry + Physics Assets<br/>GLB / NPY / JSON / recorded trajectories"]
    subgraph T["One shared Standard Visualizer"]
        L["Manifest and layer loaders<br/>mesh / scalar / vector / trajectories / time_series"]
        W["Presentation widgets<br/>Read standard layers, render and dispose"]
        U["Shared framework<br/>Scene selection / layer controls / camera<br/>Timeline / picking / legends"]
        L --> W --> U
    end
    C -->|Select preset and defaults| U
    A --> L
    P["Available presets<br/>engineering / city / laboratory"] -->|Presentation settings for the shared layout| U
    N["Future specialized panels<br/>Register interface and capabilities first"] -.-> W
```

Each Scenario selects assets and layers, a default camera and a time mode. All three presets reuse the same layout and controls. Configuration does not accept arbitrary scene scripts or page components. Specialized panels must extend the shared widget interface and preserve common loading, time, picking and disposal conventions. See [Supported capabilities](docs/framework/migration-status.md) for model and viewer coverage.

## Quick start

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[physics,geometry]'
.venv/bin/canopy --root . models
.venv/bin/canopy --root . demo
.venv/bin/canopy --root . serve --port 8769
```

Open `http://127.0.0.1:8769/` to select a scenario, or go directly to `http://127.0.0.1:8769/src/visualization/viewer/?scenario=demo`. Run `canopy --root . demo --physics temperature pollution` for an automatic geometry → wind → temperature / pollution example. This small CPU example uses the imported Physics4D solvers, creates scenario-owned assets and displays them in the shared viewer. Real city inputs and research validation require separate preparation.

```text
src/canopy/
  scenario/           Scenario definitions and indexes
  assets/             Asset validation, import and packaging
  models/specs/       Model / Method contracts and trusted registration
  running/            Shared execution lifecycle
  visualization/      Shared viewer service and scenario profiles
src/urban_flow/       Physics4D physics implementations
src/urban_geometry/   Physics4D geometry tools
src/visualization/    Shared viewer / widgets / loaders
project/<scenario>/  scenario.json and scenario configuration
<data_root>/project/<scenario>/assets/  Scenario-owned results
<cache_root>/        Disposable run intermediates
```

Configure absolute `data_root` / `cache_root` paths in the Git-ignored `storage.local.json`. The Python wheel packages shared implementations and schemas. Package scenarios separately with `canopy pack SCENARIO /absolute/path/scenario.tar.gz`. After installing the wheel, use `canopy --root /path/to/checkout ...`; the checkout supplies scenario metadata, documentation and the static viewer.

Recorded Physics4D scenes can be imported with their original samples, coordinates and provenance. See [Scene import](docs/framework/migration-status.md#importing-recorded-scenes) for commands and input requirements.

## Documentation

- [Data and ownership standard](docs/framework/protocol-v2.md)
- [Method interfaces and run guides](docs/framework/method-guide.md)
- [Supported models, scenarios and compatibility](docs/framework/migration-status.md)
- [Geometry](docs/models/geometry-heightfield.md), [GLB → Heightfield](docs/models/geometry-rasterize_glb.md), [Solar](docs/models/solar-shadow.md), [Flood](docs/models/flood-shallow_water.md), [Wind](docs/models/wind-mac.md), [Temperature](docs/models/temperature-finite_difference.md), [Pollution](docs/models/pollution-steady_tracer.md)

## Validation

Check the interfaces and viewer:

```sh
python -m unittest discover -s tests -v
node --test tests/test_viewer.mjs
# Start canopy serve first; set PUPPETEER_MODULE and CHROME_PATH if needed.
node tests/browser_canopy.cjs http://127.0.0.1:8769
```

`canopy models` is the authoritative interface catalog. Each registered Method describes its accepted inputs, parameters, outputs, dependencies and run guide. [Verification records](docs/framework/verification.md) document the checks performed and their scope.

## Imperial Corridor, London

Physics Urban World — Imperial Corridor, London.

GitHub Pages serves the viewer and local vector assets. Original and compact physical data are stored in the upstream GitHub Release. A service worker routes large-asset requests through the existing CANOPY read-only data gateway for CORS compatibility. No full-dataset download or installation is required before entering Overview.

Open via HTTPS or a localhost server. Full building geometry is retained. Compact fields retain original sampled timestamps; spatial averaging smooths local extrema. Source provenance is included under scenes/imperial_corridor_8km/compact-provenance/.

The loading illustration is a stylized pixel-art campus, not a measured building model.

### Low-altitude UAV demo

Open `?shot=uavs` for 1,383 validated original WavePDE routes between 100 irregular synthetic stations, all shown in pale gold. **All routes** toggles the network; **100 stations** frames the domain; **At building** follows a selected avoidance example.

The solver grid is 4 × 4 × 4 m, with a 25 m AGL ceiling and 12 m takeoff/landing gates. Each station targets its nearest 30 destinations (3,000 directed attempts). Of these, 1,383 passed endpoint, original closed-voxel and independent 2 m terrain/building/tree-column checks. The displayed maximum is 22.95 m AGL. The 1,617 failed attempts remain in the retained run: 928 cycles, 264 blocked steps and 425 missing arrivals. The successful network connects all 100 stations. Station positions use seeded irregular sampling with at least 450 m separation, excluding buildings, trees, water and roads.

The original solver uses `gaussian_short`, a 0.1 s timestep, 4,000 steps, adaptive local crops and plain characteristic tracing. Native 8 m frozen wind at 7,500 s is interpolated onto the 4 m planner and transferred by height above terrain. This is not a new 4 m CFD simulation or a real flight validation. Kinematic replay time is separate from raw PDE first-peak time.

Browser paths are simplified for display with a maximum 0.25 m deviation and independently rechecked against the obstacle columns every 0.5 m. Full-resolution paths, arrival fields, failed attempts, source snapshot and provenance are retained on `ese-yl222` in `uav_wavepde_4m_20261111`. See `assets/uav-wavepde-4m-20261111/evidence.json`. Earlier exports remain archived in their original directories.
