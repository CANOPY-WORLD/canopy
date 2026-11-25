# Widget model cards

Draft English copy for model information cards in the London viewer. This document is editable review material; it does not add cards to the website. Model guides describe reusable methods, while the published Scenario records identify the results actually displayed. Keep both aligned when implementing the cards.

Each card should show a model name, a short description, a model or paper link and a link to its Canopy guide. Authors and additional references can be added during review.

## Card copy and references

| Widget | Model or project | Proposed description | Canopy guide and remaining alignment |
| --- | --- | --- | --- |
| Overview | Urban Geometry | A shared 3D representation of the London corridor, providing spatial context for urban simulation and scenario exploration. | [Geometry](../../model/src/urban_geometry/README.md). Add geometry sources and authors. |
| White City campus | White City Campus Geometry | A detailed campus scene connecting landmark buildings, surrounding urban geometry and indoor environments. | [Geometry](../../model/src/urban_geometry/README.md). Add campus-specific source attribution. |
| I-HUB Interior | [LiteReality-Agent](https://litereality.github.io/agent/) | An authored concept office inside the White City I-HUB building, connected to the surrounding city through an outdoor-to-indoor camera journey. | [Interior presentation](../../scenario/imperial_corridor_8km/presentation/README.md). LiteReality-Agent is the requested project reference; retain the concept-layout qualification and verify the asset-generation provenance before claiming it reconstructed this building. |
| London Tube | Underground Network and Station Geometry | Explore London's underground network and 53 representative station environments, with timetable-based train movement in the network view. | [Visualizer](../README.md). Interiors and depths include assumptions; train positions are scheduled, not live. A dedicated Model guide is still needed. |
| Traffic | SUMO Microscopic Traffic Simulation | Recorded vehicle trajectories and signal states from a SUMO simulation, using an OSM-derived road network and synthetic traffic demand. | [Native traffic demo](../../model/traffic/demo/README.md). Add contributor and upstream citation. |
| UAVs | [WavePDE](https://github.com/RAMU-5/WavePde-UAV-Path-Model) | Wave-equation-based UAV route planning through urban geometry. | [UAV routing](../../model/src/uav_routing/README.md). The city plays precomputed routes; upstream fleet scheduling is not claimed as integrated. The guide's historical 30-station run differs from the published 100-station configuration. |
| Wind | [SCALED](https://github.com/acse-yl222/SCALED-Scalable-Generative-Foundational-Model-for-Computational-Physics) | A scalable generative model for computational physics, used to generate urban wind fields conditioned on building geometry. | [Wind implementation](../../model/src/urban_flow/physics/wind/scaled_latent.py). Retain the exact recorded run attribution; do not label these historical results as the separate registered wind/mac method. |
| Temperature | GPU-based PyTorch Temperature Solver | A GPU-based PyTorch solver for temperature transport through wind advection, diffusion and surface heat exchange. | [Temperature](../../model/temperature/README.md). Verify the published historical run's backend before treating this method description as its exact provenance. |
| Sunlight | GPU-based PyTorch Solar Solver | A GPU-based PyTorch solver for clear-sky solar irradiance and building shadows throughout the day. | [Solar](../../model/solar/shadow/README.md) and [full-day experiment](../../model/solar/shadow/full-day.md). Describe the full-day run separately from the prescribed-direction registered example. |
| Pollution | GPU-based PyTorch Pollution Solver | A GPU-based PyTorch solver for traffic-emission transport and dispersion through urban wind fields. | [Transient traffic pollution](../../model/pollution/traffic_transient/README.md). Shows conditional SUMO exhaust PMx concentration increments, not observed total PM2.5; preserve incomplete-source qualifications from the run. |
| Flooding | LISFLOOD-FP · [Xuan et al., 2026](https://www.nature.com/articles/s44304-026-00186-8) | Surface-water depth during a three-hour rainfall scenario, simulated with LISFLOOD-FP. | [London Scenario](../../scenario/imperial_corridor_8km/README.md). The linked paper is related methodology, not the London experiment. Add a LISFLOOD-FP guide; the registered Flood guide currently describes NN4PDEs. |
| Cosmos3-Super: Video generation | Generative Scene Rendering | Cosmos3-Super transforms Canopy-derived visual inputs into illustrative rendered videos. | [Demo provenance](../site/viewer/demos/provenance.json). Pre-generated imagery is not a quantitative physics result. |
| Cosmos3-Super: Text modification | Language-Guided Scene Editing | Natural-language instructions are translated into validated scene-editing code to modify building geometry and appearance. | [Demo provenance](../site/viewer/demos/provenance.json). Recorded edits and undo; physics is not recomputed. |

## Published data to describe separately

Checked against the `london-complete-tube53-20261125` publication referenced by [publication.json](../../scenario/imperial_corridor_8km/publication.json):

| Widget | Current presentation |
| --- | --- |
| Wind | 100 sampled frames; 16 m grid; wind-speed magnitude |
| Temperature | 11 frames; 32 m grid; slice at 8 m height |
| Sunlight | 21 June; 100 frames; 8 m grid; daylight playback by default |
| Pollution | 100 frames; 8 m grid; PMx increment |
| Flooding | 100 frames over three hours; 8 m pooled display grid; LISFLOOD-FP |

These are presentation settings, not universal model capabilities. Recheck them when the publication changes.

## Differentiability wording

The requested positioning for Temperature, Sunlight and Pollution is **differentiable, GPU-based PyTorch solvers**. The proposed copy above retains the GPU/PyTorch description while differentiability remains an explicit verification item. PyTorch alone does not establish end-to-end differentiability: the temperature execution path uses `torch.no_grad()`, and solar shadow visibility includes hard comparisons. Specify supported differentiable inputs and operations and validate gradients before adding an unqualified differentiability claim. Keep this verification separate from the published run's actual execution backend.

## Reserved Health card

| Widget | Model | Proposed description | Guide |
| --- | --- | --- | --- |
| Health | Conditional Breathing Response Model | A conditional variational autoencoder estimates breathing responses along a supplied trajectory using environmental and activity inputs. | [Health](../../model/healthy_route/README.md). Evaluates a supplied route; the health score is experimental. |

Health is not enabled in the checked main-city publication. Auto is a playback control rather than a model. Birds, Day cycle and Traffic map are not enabled in that configuration.

## Paper reference

Dingyu Xuan et al. (2026). *Climate extremes and urbanization drive flood tipping points at the city–river interface*. npj Natural Hazards. https://doi.org/10.1038/s44304-026-00186-8.
