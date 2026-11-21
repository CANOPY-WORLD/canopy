# Compact London publication rollout

The candidate `london-compact-20261122` in [data PR #1](https://github.com/CANOPY-WORLD/canopy-scenario-imperial-corridor-8km/pull/1) contains 1,297 payloads and 228,692,784 bytes, compared with 558,073,283 bytes in `london-public-20261118` (59.0% smaller). This is the selected snapshot size, not the size of Git history or all retained publications. Both snapshots together contain 786,766,067 payload bytes.

The candidate retains all building geometry, uses lossless Meshopt transport for detail models, halves ordinary texture dimensions and keeps landmark textures. Summer shadows retain source frames 26:73 (47 frames); winter retains all 47. Spatial resolution remains 8 m and sampling interval 600 s. Irradiance, static wind, bird replay and unused context copies are excluded; wind history and required terrain context remain. Original samples, masks and timestamps are retained. The candidate manifest and `derivation.json` record hashes and transformations. OSM zebra crossing paths include attribution and approximate coordinate conversion; stripe dimensions are illustrative.

The active `publication.json` intentionally continues to reference the deployed original snapshot. Follow the publication standard in this order:

1. Review and explicitly approve the data PR, merge it and verify the new Pages manifest and payload hashes.
2. Update `publication.json` to the deployed data commit and `london-compact-20261122`, copy its exact manifest to `data/manifest.json`, and regenerate Pages indexes. Candidate manifest SHA-256: `28c533575c8d849fed1df7a51384b41044b3dd9c49cc0c663f6082c9c0271ce4`.
3. Run the remote publication verifier, repository checks and browser playback/offline checks, then review the final code PR diff before requesting its merge approval.

Local verification uses the compact payloads with the tracked viewer sources. It does not establish remote availability, offline caching correctness or a frame-rate benchmark. Preserve the original published snapshot and retained local originals throughout this rollout.
