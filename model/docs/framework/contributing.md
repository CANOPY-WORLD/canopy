# Contributor and agent entrypoint

Start with the component you are changing. The root `AGENTS.md` and component `AGENTS.md` files point agents to these standards; each component README links to the same canonical guide.

| Change | Standard | Main files |
| --- | --- | --- |
| Model or Method | [Model standard](../../CONTRIBUTING.md) | Shared adapters, specs, solver code, request fixtures and Method README |
| Geometry or physics data | [Asset standard](../../../asset/CONTRIBUTING.md) | Descriptors, payloads, schema mirrors and integrity checks |
| Layer rendering or presentation | [Visualizer standard](../../../visualizer/CONTRIBUTING.md) | Loaders, widgets, shared shell and Scenario presets |
| London configuration | [Scenario standard](../../../scenario/CONTRIBUTING.md) | `scenario/imperial_corridor_8km/scenario.json` and its review metadata |
| Storage or delivery | [Storage strategy](../../../asset/docs/storage.md) | Private storage configuration and immutable data locations |

The repository has one curated London Scenario, shared Models, Scenario-owned Assets and a separate Visualizer. Running a Model is explicit; reading a view never triggers computation. Keep tests synthetic and isolated from retained research data. All documentation and user-facing guide text is English.

A cross-component feature must update both sides of its interface. For example, a new array representation needs a schema, writer, validator and loader; a new preset needs schema/API/viewer agreement. Treat unsupported representations as errors. Do not claim a planned implementation is already available.

Before finishing, run the checks required by the affected standards, regenerate the guide inventory when its source changes, and run `python model/tools/check_repository.py`. Report actual behavior and verification limits. Keep original source hashes, history, units, missing masks and recorded timestamps intact.

The [data protocol](protocol-v2.md) and [Method lifecycle](method-guide.md) specify the contracts. The [component inventory](../../../visualizer/guide/inventory.json) is generated review data; the Python registry and runtime manifests remain authoritative.
