# pollution / steady_tracer 1.0.0

冻结一个 wind/mac 末帧速度，求稳态被动标量的守恒对流扩散。使用移植的 `urban_flow.physics.conservative_tracer.SteadyTracer`，包装在 `canopy.models.transport.SteadyPollution`。无化学反应或沉降；模型质量单位约定为 g，输入 g/s，输出 g/m³。

安装 `python -m pip install -e '.[physics]'`。此 Method 运行需要 SciPy，CPU only。输入 `geometry` 提供 heightfield，`wind` 必须明确 derived_from 此几何版本，并同时包含 `volume_json` 和 `mac_state_json`。后者保留正向 cell-face 速度、fluid mask、西侧入口与顶部边界配置；不能用 cell-center 展示向量冒充守恒面通量。旧 wind 资产缺少该表示时需要重新运行支持此输出的 wind/mac。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `slice_index` | 3 | 展示水平切片，完整 ZYX 场另保留 |
| `diffusivity_m2_s` | 0.1 | 严格为正的各向同性扩散，m²/s |
| `sources` | `[{"cell_zyx":[3,4,4],"mass_g_s":1}]` | 非负质量排放；显式 cell 索引必须落在流体内；同 cell 排放相加 |

```sh
canopy --root . demo --physics wind pollution
# 独立执行时以本次 geometry 和 wind 精确版本替换两个占位符：
canopy --root . run examples/canopy/pollution.json --dry-run
canopy --root . run examples/canopy/pollution.json
```

输出静态 YX `concentration` layer、invalid mask、完整 `concentration_zyx.npy` 与 `scalar_volume.json`。time.samples 为空，驱动风快照的时间写入 diagnostics；稳态解不是虚构的时间序列。保留源几何和风场的两个 derived_from 引用。

离散采用守恒有限体积 donor-cell 对流、固体不可穿透，西/东及可选顶面连接零背景；扩散开放边界采用半 cell Dirichlet 距离。小问题用 sparse LU，大问题用 ILU + BiCGSTAB。接受条件：线性相对残差 ≤1e-6、总排放与边界通量误差 ≤1e-6、浓度非负（浮点容差内）；失败明确拒绝登记。

内存随三维流体格点和稀疏分解 fill-in 增长，先小网格验证。封闭不连通空腔可能导致奇异矩阵，不静默改动排放或边界。取消在分解/求解前后生效，单次 SciPy 调用期间不能中断，不支持 resume。源字段非有限、固体内排放、错误面速度表示、输入几何版本不匹配均报错。复现固定输入、代码快照、参数及 SciPy/NumPy 版本。
