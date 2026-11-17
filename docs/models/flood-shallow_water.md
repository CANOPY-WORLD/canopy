# Shallow-water flooding — flood/shallow_water@1.0.0

## 用途与实现

调用 urban_flow.physics.flood.model.ShallowWater；半隐式 C-grid、Manning 摩擦、封闭边界。降雨仅落在非 solid 格，不重分配屋顶雨量。

统一适配器：src/canopy/models/methods.py。机器接口：src/canopy/models/specs/flood/shallow_water.json。

## 安装与输入

Python 3.11+；在仓库根执行 `python -m pip install -e '.[physics]'`。几何 method 只需要基础 NumPy/jsonschema。CPU 默认可跑；GPU 使用对应 CUDA 构建的 PyTorch，request execution.device 设为 cuda；不可用时明确报错。无需下载学习权重。

Geometry asset 必须包含 heightfield 和 solid。默认干地开始。非均匀 Manning、开边界等尚未在该 method 暴露。

## 参数

| 参数 | 默认值 | 单位 | 含义与限制 |
| --- | --- | --- | --- |
| `frames` | `4` | 1 | Saved intervals after initial state [1, 10000] |
| `frame_seconds` | `1` | s | Physical time between saved frames [0.001, 3600] |
| `dt_max_s` | `0.1` | s | Maximum integration step; velocity CFL may shorten it [1e-06, 10] |
| `rain_mm_h` | `20` | mm/h | Uniform rain on non-solid cells [0, 1000] |
| `initial_depth_m` | `0` | m | Initial water depth [0, 100] |
| `manning` | `0.03` | s/m^(1/3) | Uniform Manning roughness [0, 1] |
| `cg_max` | `400` | 1 | Surface linear-solver iteration limit [1, 10000] |

## 最小运行

```sh
canopy --root . models flood shallow_water
canopy --root . demo --scenario demo --physics flood
canopy --root . validate demo
canopy --root . serve --port 8769
```

浏览器打开 http://127.0.0.1:8769/src/visualization/viewer/?scenario=demo 。
独立请求模板：examples/canopy/flood.json。先 `canopy init demo`，物理请求用几何运行返回的 asset 引用替换 REPLACE_WITH_GEOMETRY_ASSET，再 `canopy run REQUEST --dry-run` 和 `canopy run REQUEST`。不要将占位符作为有效输入。

## 输出与验证

water_depth.npy (TYX, m)、velocity.npy (TCYX, m/s)、height.npy；初始帧包含在输出内。

检查质量守恒、有限值和 CG 迭代上限；超过上限/质量误差阈值直接失败，不登记资产。强激波行为受原求解器限制。

每次运行返回 run_id 和 assets。run.json / events.jsonl 位于 cache/demo/flood/RUN_ID/；保留后的资产位于 data_root/project/demo/assets/bundles/RUN_ID/，可删除 cache 而不丢结果。

## 资源、停止与排错

默认 16×16 高度场（wind 为 8×16×16 体网格），单 CPU 线程用于小型检验。资源随网格、帧数和 horizon 方向数增长；不把小示例耗时当成城市性能承诺。当前适配器在内存中收集帧，大规模任务应改成分帧导出后再扩容。

`canopy cancel demo flood RUN_ID` 或 Ctrl-C 请求取消；不支持恢复，重新运行生成新资产。
缺 torch：安装 physics extra；资产不存在：检查同一 Scenario 的确切引用；缺 heightfield：使用兼容 geometry tool，GLB 不能自动替代；计算不收敛：检查边界、网格与时间步，查看 diagnostics/事件日志。错误不应通过隐藏失败状态来处理。

源码快照、输入哈希和完整参数保存在资产 provenance 中。设备浮点差异可能导致不同结果；原始移植文件校验值见 docs/framework/physics4d-import.json。
