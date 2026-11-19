# Geometry comparison page

An isolated review tool for [lossless London compression](../../asset/docs/geometry-compression-review.md). It does not replace either existing Viewer or add a Scenario template. Production presentation and simulations remain unchanged.

The page provides a synchronized comparison divider, original detail in selected districts, a labeled whole-city overview, building/ground visibility, wireframe inspection, stored-byte measurements and an adjustable shared task queue. It starts with Battersea for a smaller initial selection. Use `?area=b_5_3` for South Kensington and `?concurrency=2` for another task count. Only declared options are accepted.

Use the [builder](../../asset/tools/geometry-review/README.md) to populate an empty output directory; page source alone lacks the generated manifest and assets. The builder copies the production ground subdivision function unchanged. The terrain adapter preserves the production grid interpolation and building-height calculation. Both versions independently decode their geometry. Render on changes, dispose of previous districts, and terminate the ground Worker after loading.

The review manifest is a distribution index, not a scientific Asset or numerical format. Keep selected-region totals separate from whole-package totals. Never label the overview as full landmark detail, or use the session timer as a controlled production benchmark.

The browser check exercises real requests, exact decoded geometry, a pixel comparison, mobile overflow, controls, concurrency selections and scene replacement. Follow the builder's test instructions. Preserve the public Viewer requirements in [CONTRIBUTING.md](../CONTRIBUTING.md).

The owner-private review Site publishes independently through Sites. Production GitHub Pages continues to use reviewed and authorized `main`; this directory is not copied into that artifact automatically. Reproduction and review code follow Canopy's PR workflow.
