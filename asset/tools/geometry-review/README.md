# Reproduce the geometry compression review

This offline distribution tool reads the public London snapshot and writes a separate review directory. It does not run a simulator, modify sources or register an Asset. Read the [measurements and constraints](../../docs/geometry-compression-review.md).

Requirements: Node.js 18+, npm and a local copy of the exact public snapshot pinned by Canopy. From the repository root:

```sh
npm ci --prefix asset/tools/geometry-review --ignore-scripts
npm test --prefix asset/tools/geometry-review
node asset/tools/geometry-review/build.mjs \
  /absolute/path/to/canopy-scenario-imperial-corridor-8km/snapshots/london-public-20261118 \
  cache/geometry-review
python3 -m http.server 8824 --directory cache/geometry-review
```

Open `http://localhost:8824/`. The browser needs HTTPS or localhost for Workers/checksums, WebGL, WebAssembly and `DecompressionStream`. The original side reads the public snapshot URL; the candidate side reads generated local files. Do not repoint production publication metadata to this experiment.

The builder rejects an existing completed output, source/output overlap, changed input hashes, compressed source GLBs, external source buffers and unsupported buffer-view extensions. Use a fresh output directory to rebuild. Legacy external image references retain their paths. Failed builds are disposable; source snapshots are not.

Outputs: `manifest.json`, per-buffer `verification.json`, candidate `data/`, review page, existing Three.js modules and source notices. The manifest records tool hashes, source identity, gzip settings, codec version and every file hash. Large outputs stay outside Git. A retained review deployment must contain the generated distribution, not point to a local cache.

For browser QA, set `PUPPETEER_MODULE` to an installed Puppeteer ESM entry and optionally `CHROME_PATH`, then run:

```sh
node visualizer/tests/browser_geometry_review.mjs http://127.0.0.1:8824/
```

This verifies rendering/data behavior, not device-independent speed. Production adoption requires a separate reviewed change to loaders, immutable data publication, references and checks. Preserve all originals and these losslessness guarantees.
