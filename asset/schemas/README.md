# Schemas

[Canopy](../../README.md) / [Asset](../README.md) / Schemas

JSON Schema defines each interface independently. The runtime additionally checks ownership, checksums, physical coordinates and cross-document references.

| Schema | Document and responsibility |
| --- | --- |
| [scenario-v2](scenario-v2.schema.json) | Scene identity, space, Asset index, task recipes and view settings |
| [asset-v2](asset-v2.schema.json) | Geometry/Physics descriptor, provenance and selected payload layers |
| [model-v2](model-v2.schema.json) | Shared Model identity and Method catalog |
| [method-v2](method-v2.schema.json) | Method inputs, parameters, outputs, capabilities and documentation |
| [request-v2](request-v2.schema.json) | Pinned Method invocation within a Scenario |
| [run-manifest-v1](run-manifest-v1.schema.json) | V1/V1.1 payload layers, encoding, coordinates, times and artifacts |
| [project-v1](project-v1.schema.json) | Original Physics4D scene metadata, retained for import compatibility |
| [view-v1](view-v1.schema.json) | Original multi-run view, retained for import compatibility |

The [data protocol](../../model/docs/framework/protocol-v2.md) specifies semantic requirements. Schemas are mirrored in [the Python package](../../model/src/canopy/schemas/) so installed wheels validate the same documents; regression checks require both copies to match.
