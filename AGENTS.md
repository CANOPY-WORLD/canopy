# Canopy development contract
Read docs/framework/protocol-v2.md and docs/framework/method-guide.md before adding a method, asset or scenario.
Shared implementation: src/. Scenario metadata: project/<scenario>/scenario.json.
Assets are private to their scenario, stored under the configured data_root/project/<scenario>/assets/.
Only model code is shared. Scratch runs live in cache/ and are not retained assets.
All registered methods implement describe/validate/prepare/execute/export, ship a schema, example and guide.
Visualization consumes assets through the fixed standard template. No solver code in widgets.
Existing root viewer/scenes/assets are a preserved static deployment, not the new model package.
Do not upload private datasets or remove original histories. Publication is a separate operation.
Keep imported Physics4D source notices and docs/framework/physics4d-import.json provenance.
Use python -m unittest discover -s tests and node --test tests/test_viewer.mjs for contract regressions.
