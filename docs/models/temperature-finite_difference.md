# temperature / finite_difference_numpy 与 finite_difference_torch 1.0.0

共享温度接口，两个计算后端。复用 Physics4D 的三维上风对流、各向同性扩散、给定地表/屋顶温差及换热实现。可复用内核已从场景脚本提取至 `urban_flow.solvers.temperature`，来源和函数清单见 `docs/framework/temperature-extraction.json`；适配器位于 `canopy.models.transport.Temperature`。

输入 `geometry` 必须有 heightfield；`wind` 必须是**由该几何确切版本生成**的 physics asset，并提供 `volume_json` 声明的 TCZYX float32 ENU m/s 场。当前兼容 wind/mac 产物，统一格距/原点和至少两个等间隔时间样本。历史二维切片不能代替三维速度；不做隐式重采样。每个时间区间采用左端记录速度，输出时间与原风场样本完全一致。

安装 `python -m pip install -e '.[physics]'`；NumPy 后端运行本身仅需基础依赖，PyTorch 后端支持 execution.device=cpu/cuda，CUDA 不可用时报错。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `slice_index` | 3 | 展示的水平 Z cell 索引；完整 TZYX 场另存 artifact |
| `ambient_c` | 20 | 环境与西侧入口基准温度，°C |
| `surface_excess_c` | 5 | 地面和屋顶相对环境温差，K |
| `surface_exchange_per_s` | 0.01 | 底层流体与地表的换热系数，s⁻¹ |
| `max_courant` | 0.15 | 自适应子步的对流 Courant 上限 |
| `diffusivity_m2_s` | 0.01 | 温度扩散系数，m²/s |

```sh
canopy --root . demo --physics wind temperature
# 或先生成风场，再用返回的 geometry / wind 资产引用编辑例子：
canopy --root . run examples/canopy/temperature_numpy.json --dry-run
canopy --root . run examples/canopy/temperature_numpy.json
canopy --root . run examples/canopy/temperature_torch.json
```

输出：degC 标量 TYX 展示切片、固体 invalid mask、完整 `temperature_tzyx.npy`、`scalar_volume.json`、实际 dt/substeps/backend 诊断；如输入有 epoch 则保留。边界继承原方法：西侧入口有 ±0.1°C 垂直变化，顶面环境温度，其余横向边界零梯度；固体屋顶温度被给定。这里不声称求解辐射能量平衡，也不隐式耦合天气或太阳模型。

检查有限值与给定温度范围；回归测试比较两后端的结果。稳定子步兼顾对流/扩散，极大 surface_exchange 或很粗的保存间隔仍可能导致超出范围，这时拒绝结果，应减小间隔或换热系数。内存随 T×Z×Y×X 增长；目前计算保存完整体序列，优先使用小网格，不是大型流式求解器。取消在子步边界检查，不支持 resume。复现要求相同输入 SHA、参数、代码与依赖环境；GPU 与 CPU 可有浮点差异。
