# MAC incompressible wind — wind/mac@1.0.0

## 用途与实现

调用 urban_flow.solvers.mac_torch.MAC；不可压无粘流的交错网格投影，不包含 RANS/LES 湍流闭合。西入口、东压力出口，顶部可选压力出口。

统一适配器：src/canopy/models/methods.py。机器接口：src/canopy/models/specs/wind/mac.json。

## 安装与输入

Python 3.11+；在仓库根执行 `python -m pip install -e '.[physics]'`。几何 method 只需要基础 NumPy/jsonschema。CPU 默认可跑；GPU 使用对应 CUDA 构建的 PyTorch，request execution.device 设为 cuda；不可用时明确报错。无需下载学习权重。

Geometry heightfield 转换成列状 solid 体素。多重网格粗化前各维必须为偶数；必须留有顶部流体。

## 参数

| 参数 | 默认值 | 单位 | 含义与限制 |
| --- | --- | --- | --- |
| `nz` | `8` | 1 | Vertical cells [3, 128] |
| `slice_index` | `3` | 1 | Horizontal slice to visualize; full volume retained [0, 127] |
| `frames` | `2` | 1 | Saved intervals [1, 1000] |
| `frame_seconds` | `0.2` | s | Saved time spacing [0.001, 3600] |
| `dt_max_s` | `0.1` | s | Integration step cap [1e-06, 10] |
| `inlet_m_s` | `1` | m/s | West boundary eastward velocity [0.001, 100] |
| `open_top` | `false` | 见说明 | Pressure outlet at top; otherwise slip lid |
| `pressure_rtol` | `0.0001` | 1 | Projection relative residual target [1e-08, 0.01] |
| `pressure_iterations` | `100` | 1 | PCG iteration cap [1, 1000] |

## 最小运行

```sh
canopy --root . models wind mac
canopy --root . demo --scenario demo --physics wind
canopy --root . validate demo
canopy --root . serve --port 8769
```

浏览器打开 http://127.0.0.1:8769/src/visualization/viewer/?scenario=demo 。
独立请求模板：examples/canopy/wind.json。先 `canopy init demo`，物理请求用几何运行返回的 asset 引用替换 REPLACE_WITH_GEOMETRY_ASSET，再 `canopy run REQUEST --dry-run` 和 `canopy run REQUEST`。不要将占位符作为有效输入。

## 输出与验证

velocity.npy 为选定高度 TCYX；完整 velocity_tczyx.npy + volume.json 保留三维体；invalid.npy 标记切片固体。

原求解器校验压力残差；记录 divergence_rms。小 CPU 示例是实现检验，不是城市 CFD 验证。

每次运行返回 run_id 和 assets。run.json / events.jsonl 位于 cache/demo/wind/RUN_ID/；保留后的资产位于 data_root/project/demo/assets/bundles/RUN_ID/，可删除 cache 而不丢结果。

## 资源、停止与排错

默认 16×16 高度场（wind 为 8×16×16 体网格），单 CPU 线程用于小型检验。资源随网格、帧数和 horizon 方向数增长；不把小示例耗时当成城市性能承诺。当前适配器在内存中收集帧，大规模任务应改成分帧导出后再扩容。

`canopy cancel demo wind RUN_ID` 或 Ctrl-C 请求取消；不支持恢复，重新运行生成新资产。
缺 torch：安装 physics extra；资产不存在：检查同一 Scenario 的确切引用；缺 heightfield：使用兼容 geometry tool，GLB 不能自动替代；计算不收敛：检查边界、网格与时间步，查看 diagnostics/事件日志。错误不应通过隐藏失败状态来处理。

源码快照、输入哈希和完整参数保存在资产 provenance 中。设备浮点差异可能导致不同结果；原始移植文件校验值见 docs/framework/physics4d-import.json。
