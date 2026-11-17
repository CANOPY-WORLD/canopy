# Canopy 重构状态与边界

## 已落地

Scenario / Asset / Model / Running / Visualization 均有实际代码、schema 与 CLI；README 的四张架构图对应这些已实现接口。三个主体独立打包：共享实现与契约进入 Python wheel，场景和私有资产通过 `canopy pack` 导出自包含归档。

| Model | 已注册 Method | 实际实现 / 输入 |
| --- | --- | --- |
| geometry | heightfield | 小型合成高度场与 GLB，用于接口示例 |
| geometry | rasterize_glb | 移植 GLB 读取/栅格化，累积节点变换，显式裁剪与地面假设 |
| solar | shadow | Physics4D ShadowNet / HorizonNet / ground_irradiance；heightfield |
| flood | shallow_water | Physics4D ShallowWater；heightfield / solid |
| wind | mac | Physics4D MAC；heightfield，保留展示切片、完整体场及 native faces |
| temperature | finite_difference_numpy | 提取 Physics4D NumPy 热输运内核；同版本 geometry + wind |
| temperature | finite_difference_torch | 同一热输运契约，PyTorch CPU/CUDA 实现 |
| pollution | steady_tracer | Physics4D 守恒有限体积被动标量；geometry + native MAC faces |

所有八个 Method 均有输入端口、参数 schema、输出类型、依赖、能力、运行指南和示例，统一实现 describe/validate/prepare/execute/export。失败、取消或数值检查未通过的运行不登记结果。输入保持不可覆盖的版本引用、SHA-256 与 derived_from；源代码快照来自实际执行包，不冒充元数据 checkout 的 Git revision。

Visualizer 固定为 standard 模板：engineering/city/laboratory preset 复用相机、图层、选择、时间轴和图例；Scenario 声明默认内容。`canopy serve` 首页提供场景入口，不启动求解。未知的专用面板不是可执行配置，需在共享 widget 接口中显式接入。

## 真实场景与验证边界

- South Kensington / White City：各自保留 GLB、已记录风场与温度；导入到各自 assets，原 Physics4D checkout 未修改。
- Imperial Corridor：保留的 local_viewer_20261102 物理几何及风、温度、夏/冬太阳与阴影、污染物、洪水，导入为 7 个私有资产 / 9 个展示 layer。大型 NPY 按原样拆成逐帧文件；所有 float16 样本、原时间、单位、mask 均保留，无再次空间聚合。
- 另执行一次真实 Imperial Corridor GLB 的 128 m 裁剪 → 32×32 高度场 → solar 链路；未覆盖 cell 的地面 0 m 是 terrain-normalized 基准下明确记录的计算假设，不声称这些格点被 GLB 观测覆盖。
- 小型参考测试检查洪水质量守恒、MAC 压力投影、温度 NumPy/PyTorch 一致性、稳态污染物残差/质量守恒、GLB 父级变换及缺口拒绝。不是长期城市模型校准或实验验证。
- 三个真实场景与耦合示例使用同一查看器，检查全部选定图层、末帧可用性、相机与移动端布局。详细证据见 verification.md。

## 明确保留的兼容部分

Physics4D 共享源码保留原 import 路径及来源清单，历史脚本列于 legacy-entrypoints.json。依赖特定场景、训练检查点、SUMO、OpenFOAM、Blender、Triton 的研究脚本仍是兼容入口，不自动成为正式 Method。它们的专用环境与研究参数不纳入这八个稳定适配器的验证范围。

原 Canopy Imperial Corridor 公开网站继续保留既有 URL、细节 tiles、地形/地图上下文、交通与 UAV 演示。上述物理数据现已能够通过 V2 统一查看器读取；不声称已经在统一模板中重做所有旧网站呈现功能。原始 terrain 与 terrain-normalized 物理几何必须保持区分。

完整三维场可作为 artifact 保留；当前查看器显示明确导出的水平切片。Zarr、任意非结构网格、动态网格、checkpoint resume、分布式调度仍未实现。温度和风场的小型计算适配器在内存中保存全体场；逐帧展示不等于求解器支持无限大小的流式计算。

## 来源与发布

physics4d-import.json 固定来源 revision 和逐文件原始 SHA-256，import-adaptations.json 记录后续改动；temperature-extraction.json 单独记录提取的数值函数。源仓库存在未提交研究工作，因此原移植清单明确是工作树快照。原版权/引用保留，未额外赋予第三方代码授权。

私有资产、cache 和机器配置不进入 Git 或 wheel；场景元数据和迁移工具保留在仓库。实际发布、push 与网站部署未执行。
