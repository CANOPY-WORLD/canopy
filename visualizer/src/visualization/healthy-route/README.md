# Local healthy-route presentation components

These modules preserve the V2 research presentation (route plots, health contributions, walker following, walking/running controls, solar sampling and shared journey timing). They are not imported by the public website or its catalog. No saved-journey demo data is included.

The compatibility installer accepts an existing viewer and a supplied `currentTerrain` provider; it never creates a second renderer. It expects the private local `/api/pedestrian/meta` and `/api/pedestrian/plan` service contract. It is retained for local research integration, not registered as a read-only standard Asset widget. The current standard viewer can inspect the Method's exported time-series layer; `route.json` contains the complete detailed result. Enabling the interactive installer in the shared public shell is deferred with the web demo and requires an explicit execution-service design.
