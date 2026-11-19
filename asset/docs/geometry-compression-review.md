# Lossless London geometry review

[Asset standard](../CONTRIBUTING.md) · [Review page](../../visualizer/geometry-review/README.md) · [Reproduce](../tools/geometry-review/README.md)

This experiment creates a separate distribution from the already-public London snapshot. It does not replace the production Viewer, change the Scenario publication pin, register a scientific Asset, or merge another performance PR. Original payloads remain untouched in the independent Scenario repository.

## Stored sizes

Decimal MB means 1,000,000 bytes. Both columns include existing gzip where present; the baseline is not an inflated uncompressed GLB.

| Scope | Original MB | Candidate MB | Reduction |
| --- | ---: | ---: | ---: |
| Complete building distribution, including textures and metadata | 159.62 | 74.20 | 53.51% |
| Ground/road review distribution | 82.59 | 36.21 | 56.16% |
| Building overview GLB, gzip | 9.76 | 2.92 | 70.10% |
| Road GLB, gzip | 10.02 | 5.35 | 46.55% |

Exact package totals: buildings 159,621,401 → 74,204,161 bytes; ground/roads 82,587,217 → 36,210,063 bytes. The ground review includes vector surfaces, terrain, road files and original placement/source metadata. Historical authoring exports are outside both columns. Therefore this 82.59 MB scope is smaller than the previous 121.58 MB group, which also counted those exports. This is not a measurement of the complete physics/UAV website.

The overview retains all 1,599,944 triangles. There is no new quantization, decimation, welding, texture resize, vertex reordering or index reordering. Original data may already contain historical quantization; lossless means preserving that existing source exactly.

## Encoding and provenance

GLB buffer views use `EXT_meshopt_compression`, `filter:NONE`, and `INDICES` to preserve the exact index sequence. Scene/node/accessor/primitive/material/image descriptors remain unchanged. The converter serializes and reads the new GLB, then compares every reconstructed buffer view. Gzip follows encoding. When a candidate is larger, retain the original. JSON and float arrays use gzip with byte-exact decompression checks. Textures retain their original pixels.

The build verifies the locked source manifest SHA-256 `77320e4684ce7a63c0a9a8a45b99329e085ea7dfa45991cc32b345d112d3f97c`, pinned to source revision `196bbaca475148c968fe384a09b1c26507123191`. Its review manifest records input/output sizes and hashes, tool hashes, codec version, and a checksummed verification file. This is a distribution experiment, not a new numerical protocol. Legacy display GLBs with external texture references retain those dependencies; this process does not make them self-contained scientific Assets.

See the [Khronos extension](https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Vendor/EXT_meshopt_compression/README.md) and [meshoptimizer API](https://github.com/zeux/meshoptimizer/blob/master/js/README.md). The encoder is pinned to 0.24.0. The page uses Canopy's existing Three.js loader and decoder.

## Review and concurrency

Both versions load independently and share one camera/renderer. Districts load the selected original tile and all its landmarks. Ground display selects complete source triangles intersecting that district, without resampling. The whole-city option explicitly uses the existing overview mesh; it does not load all 331 detail files. Switching districts disposes of previous geometries, materials and textures.

One shared queue defaults to three geometry tasks across both versions, with 1/2/3/4/6 available for experiments. Preparation is serialized; ground subdivision and normals use one Worker. Downloaded geometry inputs are bounded by the task count. GLTF texture requests and browser-internal threads are outside that limit. Geometry and terrain fetches verify SHA-256 and have timeouts and a retry path.

Elapsed time covers **both** versions, including checksums/preparation. It is not a fair original-versus-optimized speed benchmark: originals and candidates use different hosts, and device/cache conditions vary. Production concurrency is unchanged. Before changing it, measure first usable frame, long tasks, peak decoded memory and frame time on target hardware under controlled network/cache conditions.

## Checks and limits

- All 333 GLBs and 25,299 serialized buffer views round-trip exactly. Non-GLB transformations decompress byte-for-byte.
- Converter tests cover deterministic output, source immutability, descriptors, exact indices/negative zero, and rejected unsupported/out-of-range inputs.
- Browser checks compare decoded attributes in Battersea, South Kensington and the 8 km overview. A 600 × 400 Battersea comparison frame produced zero differing RGBA bytes.
- Desktop/mobile layouts, layer/wireframe/divider controls, concurrency selections, district changes and resource replacement are exercised against real published source URLs.
- The existing 77 Model tests, five core Viewer tests and protocol fixture pass. The repository checker validates the catalog, schema mirrors and documentation.

Browser QA uses software WebGL: repeated drawing is paused for loading/data checks, with explicit comparison frames rendered. Timings are diagnostics, not hardware performance claims. Decoded geometry and GPU memory remain essentially unchanged. Spatial delivery and bounded residency of original detail are the next independent optimizations, followed by decode/preparation/GPU upload profiling. Physics, UAV data and the production UI are outside this change.
