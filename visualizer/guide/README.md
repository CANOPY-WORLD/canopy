# Architecture and contributor website

This buildless, English-language guide explains Canopy's architecture, current Model/Asset/Visualizer inventory, London case, storage choices and component contribution standards. It contains only documentation and safe summary metadata. The only curated Scenario is `imperial_corridor_8km`.

Open the [private hosted guide](https://canopy-architecture-guide.yueyan.chatgpt.site).

## Preview

After [installing Canopy](../../model/README.md), run from the repository root:

```sh
python model/tools/build_review_inventory.py
canopy --root . serve --port 8769
```

Open `http://127.0.0.1:8769/guide/`. This guide also works on a plain static HTTP server. The dynamic catalog links to it. The London simulation viewer is a separate presentation.

## Sources and update rules

- `inventory.json` is generated from registered Method specs, the London Scenario and its [Asset review catalog](../../scenario/imperial_corridor_8km/asset-catalog.json).
- `architecture.svg` is a generated copy of the [root overview diagram](../diagrams/architecture.svg).
- `index.html`, `style.css` and `app.js` provide the narrative and interactive inventory.
- [Component standards](../../model/docs/framework/contributing.md) remain authoritative; this page links to them instead of duplicating parameter manuals.
- [Storage decisions](../../asset/docs/storage.md) distinguish implemented codecs and local loading from proposed remote storage and Zarr support.

After a Method or component change, regenerate the inventory. After a London data change, validate local payloads and refresh the safe catalog first:

```sh
python model/tools/build_review_inventory.py --refresh-assets
python model/tools/check_repository.py
node visualizer/tests/browser_guide.cjs http://127.0.0.1:8769/guide/
```

Asset refresh requires local retained data; ordinary generation and repository checks use tracked summaries. Do not copy raw fields, credentials, private filesystem paths or detailed provenance into the website. The Site's inventory is a build snapshot; it does not synchronize itself with GitHub at runtime.

## Hosting

The private review Site uses project ID `appgprj_6afca7a8e7c88191884ff2849100b45a`. Its identity is retained in [.openai/hosting.json](.openai/hosting.json). Reuse that ID when updating; preserve owner-only access.

Use the Sites source workflow in a separate ignored checkout under `cache/sites/`, copying this directory's source and identity. Serve `index.html`, `style.css`, `app.js`, `inventory.json` and `architecture.svg` from `dist/`. The source helper commits, pushes and packages the exact source before private deployment. Credentials belong only in the helper's hidden stdin, never in Git or build output.

This Site does not change the repository's existing GitHub Pages deployment.
