# London website asset size review

[Asset standard](../CONTRIBUTING.md) · [London profile](../../scenario/imperial_corridor_8km/website.json)

This review measures stored public payload bytes from `london-public-20261118`, whose locked manifest SHA-256 is `77320e4684ce7a63c0a9a8a45b99329e085ea7dfa45991cc32b345d112d3f97c`. Decimal MB means 1,000,000 bytes. Stored bytes, network transfer, decoded JavaScript arrays and GPU allocation are different measurements.

| Payload group | Stored MB |
| --- | ---: |
| Building overview, detail tiles, landmarks and textures | 159.62 |
| Ground, roads, terrain and associated source material | 121.58 |
| Physics fields | 166.79 |
| Bird replay and metadata | 46.80 |
| Four UAV export variants and metadata | 51.51 |
| Vehicle replay and metadata | 11.57 |
| Other metadata and small actor models | 0.21 |

The exact total is 558,073,283 bytes. The website profile disables bird and vehicle replay, excluding 58,364,419 bytes from the download list. Enabled data totals 499,708,864 bytes, with frontend files counted separately. Original bytes, publication pins, geometry and scientific results remain intact. The current change reuses frame-streaming work from PR #7 without adopting its reduced display assets or balanced geometry mode.

## Opening and preparation

Normal homepage entry opens the existing Viewer without verifying/downloading the complete package first. `?download=all` retains explicit complete caching of the enabled presentation. This changes which resources are needed to enter the view; it does not reduce asset precision or dataset size.

Original detail meshes load in groups of three, prioritizing tiles in the current camera view and near its focus. The queue yields to a browser frame between meshes. Every source tile/landmark is still loaded in the background and retained; camera-based eviction is not implemented. This improves preparation order but does not bound total geometry/GPU memory or guarantee a particular device's frame rate.

Ground triangle subdivision, elevation sampling and flat/terrain normal construction run in one module Worker. Input and output array buffers transfer ownership; the rendered attributes preserve the original computations. The worker is terminated after preparation. Browsers without Workers use the same calculation on the main thread. Vehicle lane-matching indexes are built only when a vehicle asks for a match, so disabled traffic does not allocate or prepare that index. Geometry, trees and GPU uploads still have a substantial cost.

Solar/flood playback no longer decodes an entire sequence on selection. Visible fields read the current sample and two look-ahead samples, with an LRU cache capped at 64 MiB, or 32 MiB on reported low-memory devices. Switching to a geometry view releases field-cache ownership and invalidates stale frame results. The cap applies to this cache, not total browser memory. Original timestamps, quantized values, masks and numerical samples stay unchanged.

## Buildings

Keep the full original assets and produce independently versioned display derivatives. The current snapshot contains a 9.76 MB gzip overview plus 149.86 MB of detail tiles, landmark meshes, textures and their index. Compressing only the overview cannot eliminate the detail collection's cost.

An earlier local overview candidate reduced the gzip file to 3.50 MB, with triangle count changing from 1,599,944 to 1,592,492. Its compression ratio is not a measure of geometric error or browser memory. It does not replace nearby landmark detail, and the candidate is not published. That work belongs to [PR #7](https://github.com/CANOPY-WORLD/canopy/pull/7).

The current requirement is no new downsampling. Preserve building footprints, rooflines, elevations and important landmarks, and validate near and distant camera views. Geometry priority changes preparation order only; camera-based detail selection and eviction still require separate work. The full source meshes remain the display inputs.

## Ground and terrain

The 121.58 MB group includes source JSON and a historical HTML export as well as runtime geometry. Audit runtime dependencies before removing anything from the display distribution; keep original source material in the immutable snapshot. In particular, `vector_landscape/source/scene-meta.json` is used for tree and furniture placements, and `terrain/road-network.json.gz` supports elevated roads. They cannot simply be dropped as unused source data.

Many geometry arrays are already gzip-compressed. Options compatible with the current requirement include lossless compression of remaining JSON, preparing the existing runtime geometry ahead of loading, and moving heavy preparation off the main thread. Preserve coastlines, water levels, bridge elevations and building bases. No new terrain approximation, resampling or quantization is selected here.

## UAV lossless compression measurement

Measured with Python `gzip.compress(source, compresslevel=9, mtime=0)` on 19 November 2026. Every candidate was decompressed and compared byte-for-byte with its source. No route points, numerical values, clocks, audit fields or identifiers were changed.

| Export directory | JSON bytes | gzip bytes | Reduction |
| --- | ---: | ---: | ---: |
| `uav-low-altitude-20261111` | 3,613,613 | 1,101,141 | 69.53% |
| `uav-wavepde-20261111` | 7,375,764 | 2,665,514 | 63.86% |
| `uav-wavepde-30m-20261111` | 21,128,898 | 7,773,436 | 63.21% |
| `uav-wavepde-4m-20261111` | 18,667,341 | 6,709,645 | 64.06% |

The current scene selects the 4 m export: 1,383 successful routes between 100 synthetic stations. Other export variants are still in the snapshot and default download list. Selecting only the active export and retaining earlier exports separately is another possible reduction, subject to a dependency audit.

The gzip measurements are stored-file comparisons; HTTP content encoding and cache state affect actual network savings. Decompressed JSON and parsed object memory remain the same. Binary trajectories or loading individual routes could reduce parse/memory cost, but require a format/loader change. The existing displayed routes already have a documented maximum 0.25 m simplification deviation and collision checks; do not further simplify them without rechecking those guarantees. The compressed candidates are measurements only and have not been deployed or substituted into routing.

To reproduce on a local copy of the public snapshot:

```python
from pathlib import Path
import gzip

snapshot = Path('/path/to/snapshots/london-public-20261118')
for path in sorted(snapshot.glob('assets/uav*/routes.json')):
    source = path.read_bytes()
    compressed = gzip.compress(source, compresslevel=9, mtime=0)
    assert gzip.decompress(compressed) == source
    print(path.relative_to(snapshot), len(source), len(compressed))
```

## Physics fields

Several displayed fields already use 8-bit quantization, reserved invalid codes, spatial aggregation and gzip chunks. Temperature uses float16; shadow and invalid masks use byte encodings. These are already reduced display representations, not a demonstrated compression limit.

Further precision reduction requires physical error checks, especially for extrema, inundation boundaries, concentration peaks and vectors, and is outside the current no-downsampling scope. The frame-loading changes preserve the present values, masks and time samples while reducing resident cached data. Full retained scientific Assets remain distinct from this website distribution.

## Validation and limits

Checked on 19 November 2026:

- 77 Model tests, 20 JavaScript tests, 11 publication tests, the protocol fixture and the repository checker passed.
- All 18 ground layers retained identical SHA-256 values across 108 position, height and normal arrays, compared with the build before the Worker change. The Worker and main-thread fallback both matched.
- The full original geometry loaded all 331 detail/landmark files. The actual field reader decoded first and final samples for 18 field/mask resources.
- Normal entry requested no complete download list. Selecting Sunlight requested three solar chunks; 18 field switches respected the 64 MiB cache limit. Disabled bird/traffic payloads were not requested, including through their old shot links.
- Explicit complete caching verified all 1,565 selected files, totaling 504,230,945 bytes including the frontend. The Viewer reloaded offline. Widget playback, seeking, final samples, restart, and the minimal layout passed at 1440 px and 390 px widths.
- Self-review identified and fixed stale frontend selection from older complete caches. Online code/configuration now refreshes while immutable payloads can reuse the cache.

Browser checks used software WebGL, with continuous drawing paused during loading/control checks and explicit frames rendered for visual review. They establish data equality, resource demand and functionality, not hardware GPU throughput or a guaranteed first-frame time. Full detail remains resident after loading; geometry/texture memory and GPU upload cost remain substantial. The immutable snapshot and its source revision have not changed.
