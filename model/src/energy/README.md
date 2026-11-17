# Tower Hamlets energy pilot

Public energy-facility overlays and assumed supply/demand tests for the existing Canary Wharf 4 km scene.
Reuses the shared viewer, coordinates, timeline, JSON scalar/curve data and GLB layers.
This imported guide describes the original Physics4D scene and commands.

## Data and scope

- GLA London Heat Map: downloads existing/planned heat-network routes, energy centres and planned heat-network projects.
  Retains official ArcGIS metadata, complete query URLs, retrieval times, licenses and SHA-256 checksums.
  Existing/planned categories follow the source layers; individual status is recorded in `inventory.json`.
- Electricity facilities and charging stations: reuses the scene's retained 2026-10-07 OSM files, including OSM IDs,
  tags, versions and timestamps. This is not a live operating inventory. The public UKPN catalog requires login;
  restricted records were not retrieved.
- Coordinates: uses the scene's WGS84 AEQD metric frame centred at (-0.0188, 51.5053),
  projecting before clipping to [-2000,2000]². The area crosses administrative boundaries and does not represent borough-wide Tower Hamlets statistics.
- Facility spheres sit above roofs for visibility. Heat-network line widths and display elevations are not measured pipe diameters or burial depths.
  Solid pink lines show existing GLA heat networks, dashed orange lines planned networks, and dashed blue lines assumed electricity connections.
  Original OSM cable/line tags remain in the inputs; a complete feeder topology is neither inferred nor displayed.

## Assumed calculation

Selects nonoverlapping elevated grid regions for six differently named buildings. Uses the 11 retained horizontal rooftop-irradiance frames from
`canary_wharf_sunlight027` (2026-06-21 12:00–12:10 UTC).
The original 600-second window is preserved without inventing full-day data. Roof suitability, slope and actual equipment have not been verified.

The configuration explicitly assumes photovoltaic coverage on 20% of rooftop area, 20% conversion efficiency and a 0.85 performance factor;
120 kW base electricity demand and 60 kW heating demand per building, with heat-pump COP=3;
and test charging demand increasing from 20 to 220 kW at the mapped Canary Wharf charging station.
These are not the station's measured demand or rated equipment capacity.

Net grid import = base electricity + heat-pump electricity + charging electricity - photovoltaic generation.
Heat-pump heat output = heat-pump electricity + environmental heat extraction. Negative net grid import represents export.
This is a supply/demand balance without network losses. It does not solve voltage, AC power flow, line capacity or heat-network hydraulics.
The assumed heat pumps are not necessarily connected to any mapped heat network.

## Rerun

Use a Python environment with the optional dependencies in `src/energy/requirements.txt`:

```bash
PYTHONPATH=src python -m energy.pilot \
  --config project/tower_hamlets/configs/energy_pilot.json --retain
```

Add `--source project/tower_hamlets/input/energy_open_<timestamp_and_id>` to reuse a validated download snapshot.
Each run creates a new directory; `--retain` saves it under runs and registers a separate view without changing the default view.
Inputs live in project/input and trial runs in cache. Retained runs include the required inputs, configuration and source snapshot.
`catalog/*.json` maps scalar-layer array indexes to facility/building names; `inventory.json` retains public attributes.

```bash
PYTHONPATH=src python -m unittest discover -s tests -p 'test_energy_pilot.py' -v
python3 tools/check_contract.py project/tower_hamlets/runs/<run_id>/manifest.json
PUPPETEER_MODULE=<absolute_path_to_puppeteer_core> \
UWM_VIEWER_URL='http://127.0.0.1:8937/src/visualization/viewer/?scene=tower_hamlets&view=<view_id>' \
node tests/browser_energy.cjs
```

Browser checks cover layer loading, the supply/demand balance at 300 seconds, picking, visibility, hiding data outside the time range and resource disposal.
Data and results were retained locally only; they were not published.

### ATES city prototype

`ates_export` connects recorded surrogate cycle energies to two hypothetical wells,
six buildings and an assumed COP=4 heat pump. The cycle view uses MWh per completed
cycle pair, not instantaneous power. It preserves the nine original aggregates and
compares warm recovery with the source simulation. Well placement and demand are
scenario assumptions, not validated Canary Wharf geology or infrastructure.

```sh
PYTHONPATH=src cache/energy_runtime/bin/python -m energy.ates_export \
  --config project/tower_hamlets/configs/ates_demo.json \
  --cycle-source /home/yl222/workspace/geothermal/expout/application_20260930 --retain
```

`stage_ates` can stage the user's Vega checkpoints, upstream implementation and
recorded scenario with hashes after SSH authentication is renewed. `ates --source
<snapshot> --output <recording>` then runs inference with PyTorch. The full-field
export uses `ates_export --inference <recording> --model-source <snapshot>` instead
of `--cycle-source`. This inference path awaits validation with the actual weights;
the cycle-only view deliberately contains no substitute temperature fields.

`thermal_slice` is a presentation adapter for existing JSON scalar-field payloads,
with coplanar regularly spaced samples and physical-size tiles. It performs no
solver computation. The viewer accepts optional model-year presentation metadata;
manifest timestamps stay in seconds. Fixed injection schedules are unchanged by
building demand: the heat-pump calculation is one-way accounting, excluding pump
power and distribution losses.
