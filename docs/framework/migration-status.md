# Canopy 重构状态与边界

## 已落地

- 独立 Canopy 开发包；Scenario / Asset / Model / Running / Visualization 均有实际代码和 CLI。
- Model 有 model.json，Method 有接口定义、参数 schema、指南、示例及统一运行生命周期。
- 四个已注册 method：geometry/heightfield、solar/shadow、flood/shallow_water、wind/mac。
- 太阳、洪水、风场调用移植的 Physics4D 原算法；几何 method 生成可展示 GLB 和计算高度场。
- 场景私有资产索引、版本引用、校验和、来源保留、缓存隔离、失败与取消记录、只读查看服务。
- 固定 Visualizer 模板，engineering/city/laboratory 三个呈现 preset，共享相机、时间轴、图层、选择和图例。
- South Kensington 与 White City 的原始几何、一个记录风场及温度结果已通过本地迁移工具导入各自私有 assets；数据不混入源代码 wheel，不自动发布。
- 原 Canopy Imperial Corridor 网页保留原路径和数据路由，不覆盖公开部署。

## 兼容保留，不应误报为完成迁移

Physics4D 的共享实现包保留原 import 路径，便于算法代码追踪和后续适配。其所有历史研究脚本并未自动成为可运行的 Canopy Method。完整清单见 legacy-entrypoints.json：依赖外部检查点、SUMO、OpenFOAM、Blender、Triton、特定场景输入的脚本仍需对应环境与输入，不在这次小型 CPU 回归覆盖范围。

现有 Imperial Corridor 网站的数据使用历史分块/远端资源协议；它继续作为兼容入口，尚未全部转换成 V2 场景私有资产。不能从网站坐标标签推断未记录的地理原点。

本次没有重新运行真实城市的长期风场、RANS、交通或耦合热环境模拟。真实场景测试验证已保存数据的读取、协议和展示；小型 solar/flood/MAC 测试验证新执行链路与适用数值性质，两者不能混称。

完整三维风场被保留为 TCZYX artifact，但统一 Visualizer 目前只展示明确选定的水平切片。Zarr、任意非结构网格、动态网格、checkpoint resume、分布式调度属于尚未实现的能力，接口不会声称支持。

## 来源与发布

physics4d-import.json 固定来源 Git revision 和每个移植文件的原始 SHA-256；源仓库有未提交改动，因此记录的是工作树快照，不冒充纯 Git commit。源仓库未修改。原文件版权/引用保留，未发现仓库总许可证，不额外赋予第三方再分发授权。

本地资产路径受 .gitignore 保护；schema、示例配置、模型指南、迁移工具进入代码包。公开网站部署没有执行。
