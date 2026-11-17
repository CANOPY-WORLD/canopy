# geometry / rasterize_glb 1.0.0

将当前 Scenario 的静态 GLB 三角面采样为计算高度场，保留原始展示 GLB 和节点实体映射。实现：`canopy.models.geometry.RasterizeGLB`，复用 Physics4D `urban_geometry.voxelization.prepare_glb` 的 GLB reader 与最大表面栅格化算法。遍历选定 glTF scene，累积父子节点 matrix/TRS，再从 glTF Y-up 转换为 ENU。

输入端口 `geometry` 必须是当前场景已登记的 geometry asset，包含所选 GLB layer。动画、skin、morph、非三角形和 Meshopt 压缩计算输入会明确拒绝；Draco 解码需要 DracoPy。GLB 几何原点与场景一致，不能用修改坐标标签代替变换。输出是平面基准上的高度柱近似，不是封闭网格、地下结构或悬挑空腔表达。

安装 `python -m pip install -e '.[geometry]'`。纯未压缩 GLB 可用基础 NumPy 环境，Numba 是可选加速；首次编译有额外开销。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `layer_id` | `geometry` | 输入资产中的 GLB layer ID |
| `bounds_xy_m` | 必填 | ENU 米制 `[west, south, east, north]`；必须在 Scenario bounds 内 |
| `cell_m` | 2 | 格距，m；裁剪宽高必须为其整数倍，每维至少 3 cells |
| `max_cells` | 1,000,000 | 分配上限；先用小裁剪验证 |
| `ground_elevation_m` | 0 | 显式平面基准，Scenario ENU 高程 m |
| `uncovered_ground_m` | null | 未被三角形覆盖的采样点：null 报错；数值表示用户明确指定的地面高程 m |
| `obstacle_threshold_m` | 0.05 | 超过平面基准多少米标记为 solid |

```sh
canopy --root . models geometry rasterize_glb
# 编辑 examples/canopy/rasterize_glb.json：scenario_id、真实资产引用、layer_id、裁剪与基准。
canopy --root . run examples/canopy/rasterize_glb.json --dry-run
canopy --root . run examples/canopy/rasterize_glb.json
```

产物：原 GLB、`height.npy` float32、`solid.npy` uint8、`coverage.npy` uint8、`heightfield.json`、`entities.json`。`height` 相对平面基准；coverage=1 表示原三角面覆盖，0 表示明确的填补假设。derived_from 固定输入几何版本。接下来将新 geometry 引用交给 wind/solar/flood 等需要 heightfield 的 Method。

有效性检查：有限坐标、面索引、网格范围、覆盖、非负相对高度与实体 ID 唯一性。建筑 GLB 通常缺少地面；请根据有证据的基准选择填补或完整 terrain 输入，不能把自动填零当作观测。源 GLB 超大时先裁剪；当前每个 primitive 需读入内存，最大输出网格限制不会限制源 mesh 大小。取消在节点边界生效，不支持 resume；每次重新运行创建新资产。复现保留输入 SHA、请求、代码快照及填补假设。
