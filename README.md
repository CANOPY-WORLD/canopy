# Canopy

A framework for geometry, physics simulation and urban visualization. The included case is London’s 8 km × 8 km Imperial Corridor.

**[Open Canopy](https://canopy-world.github.io/canopy/)** · [Architecture and component guide](https://canopy-world.github.io/canopy/guide/) · [CANOPY-WORLD organization](https://github.com/CANOPY-WORLD)

![Canopy architecture: Scenario selects shared Models, owns Geometry and Physics Assets, and configures a Visualizer that reads both asset types.](visualizer/diagrams/architecture.svg)

**Scenario, Model and Asset are the three core concepts.** A Scenario defines a scene, selects shared Models and owns its Assets. Geometry tools produce Geometry; physics simulators consume Geometry and, when needed, previous results to produce Physics Assets. Each Scenario keeps its own geometry and results.

**Visualization is separate from execution.** The Visualizer reads Geometry and Physics Assets through one shared template. Scenario view settings choose the layers, camera and presentation preset; opening a view does not start a simulation.

| Directory | Responsibility | Explore |
| --- | --- | --- |
| [model/](model/README.md) | Shared geometry tools, physics simulators and execution interfaces | Methods, installation and run guides |
| [scenario/](scenario/README.md) | Scene identity, space, task recipes, asset references and view settings | Scene organization and examples |
| [asset/](asset/README.md) | Geometry and physics data contracts, with scenario-owned storage | Formats, provenance and packaging |
| [visualizer/](visualizer/README.md) | One viewer framework with scenario-specific presentation | Loaders, widgets and presets |

Each directory documents its internal structure and interfaces. Start with [Model setup](model/README.md#run-the-small-example) to run an example, or review the [London case](scenario/imperial_corridor_8km/README.md).

For extensions, start with the [contributor and agent standards](model/docs/framework/contributing.md), then follow the relevant component guide. Canopy maintains the shared website and Scenario configuration; each Scenario's public data is hosted independently and selected through a pinned publication reference. See the [publishing standard](visualizer/docs/publishing.md) and [data storage strategy](asset/docs/storage.md).

To build and propose a new Scenario, follow the [Scenario contributor guide](https://github.com/CANOPY-WORLD/canopy-scenario-guide). To review visualization, see the [current structure](visualizer/docs/architecture-review.md) and [unified upgrade plan](visualizer/docs/upgrade-plan.md).

London: **[Open the Scenario](https://canopy-world.github.io/canopy/viewer/3d/?scene=imperial_corridor_8km)** · [Data repository](https://github.com/CANOPY-WORLD/canopy-scenario-imperial-corridor-8km) · [Data website](https://canopy-world.github.io/canopy-scenario-imperial-corridor-8km/) · [Public Scenario index](https://canopy-world.github.io/canopy/scenario-index.json)
