# South Kensington

[Canopy](../../README.md) / [Scenario](../README.md) / South Kensington

[scenario.json](scenario.json) defines the spatial frame, indexes this Scenario's recorded geometry, wind and temperature Assets, and selects the standard viewer with the city preset. Model implementations are shared with other Scenarios; payloads and exact Asset references belong to `south_ken`.

The [migration record](migration.json) retains source-run references and import provenance. Geometry relationships that were unknown in the historical results are not inferred from matching scene names. The recorded display slices do not automatically provide native 3D inputs for coupled Methods.

After providing the private payloads through the [recorded-scene import tools](../../model/docs/framework/migration-status.md#importing-recorded-scenes), run:

```sh
canopy --root . validate south_ken
canopy --root . serve --port 8769
```

Open the Scenario catalog at <http://127.0.0.1:8769/>. Loading recorded results does not rerun the original simulations.
