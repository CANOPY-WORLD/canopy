# Canopy 数据与组织协议 2.0

本协议是 Canopy 新接口的实现规范。Scenario / Asset / Model 是三个主体概念；Running 与 Visualization 是独立共享服务。V2 envelope 复用已验证的 v1.1 layer 编码，不把 v2 JSON 冒充 v1 manifest。

## 归属与目录

```text
src/canopy/
  scenario/          # 场景身份、资产索引、配置
  assets/            # 私有资产解析、校验、导入
  models/            # 共享接口、可信注册表、Physics4D 适配器
    specs/<model>/<method>.json
  running/           # 生命周期、日志、取消、复现、保留
  visualization/     # 固定模板配置与只读服务
src/urban_flow/       # 移植的 Physics4D 数值实现，保留原 import 路径
src/urban_geometry/   # 移植的几何工具实现
src/traffic/         # 移植的交通工具实现
src/visualization/{viewer,widgets,shared,vendor}/
project/<scenario>/scenario.json
<data_root>/project/<scenario>/assets/bundles/<run_id>/
  manifest.json      # v1.1 二进制 payload 描述
  geometry.asset.json / physics.asset.json
  *.glb / *.npy / *.json / provenance/
<cache_root>/<scenario>/<model>/<run_id>/
  request.json / run.json / events.jsonl / diagnostics.json / payload/
```

同一 bundle 可含 geometry 和 physics，但索引为两种独立 Asset；只复制一次 payload，不重复大数组。每个资产引用形如 `asset_id@1`，只在当前 Scenario 内解析。所有文件路径受场景根目录约束，禁止绝对路径、URL、`..` 和逃逸符号链接。不存在跨场景资产引用。

注册资产不可覆盖。新的计算生成新 ID；`derived_from` 固定输入资产版本。文件与 manifest 的 SHA-256 必须一致。原始来源保持原样；不可用当前适配器版本替代未知的历史求解器版本。

## Scenario

`scenario.json` 必须通过 `schemas/scenario-v2.schema.json`：身份、标题、空间定义、资产索引、任务配方、Visualization 配置。JSON 是声明性数据，打开它不执行 Python/Blender/JavaScript。

坐标沿用 ENU，米制，时间秒制。真实场景必须声明真实地理原点、高程基准；合成示例使用 `georeferenced:false`。资产可有较小 bounds，但必须使用同一原点与地理语义。不同坐标数据必须先经过显式转换。

`tasks` 保存完整版本化 request；调用 `canopy run request.json` 执行，场景加载不自动运行任务。展示配置固定为 `template:standard`，preset 是 engineering/city/laboratory，只有可信样式调整；layers 明确选择 asset + layer，camera 使用场景坐标。没有 `latest` 或按目录修改时间猜测结果。

## Geometry

默认展示编码为自包含 glTF 2.0 GLB，Y-up `(east, up, -north)`。公共查看器统一转换，物理向量仍为 ENU。Three.js 是渲染实现，不是持久化标准。Blender 脚本是生成来源，不是场景定义。

计算几何不等于展示几何。heightfield 与 rasterize_glb method 输出 GLB、float32 height、uint8 solid、heightfield.json 与实体映射。高度是相对 origin_m[2] 的米，行向北、列向东、cell_center 采样；该 GLB 是高度场表面，不声称封闭体网格。rasterize_glb 保留原 GLB，显式处理节点变换、采样覆盖与填补假设。其他 geometry tools 应输出对应的显式计算表示；只有视觉 GLB 的输入不能直接交给需要 heightfield 的 method。

## Physics result

统一按 scalar_field/vector_field/trajectories/time_series 分类，不按求解器定制编码。NPY 小端 C-order，dtype/shape/axes/origin/spacing/sample_location/unit 全部明确。当前显示层是 YX/CYX/TYX/TCYX；完整三维风场另保留 TCZYX 数组和 volume.json，温度另保留 TZYX，稳态浓度另保留 ZYX，查看器显示显式选择的水平切片，不声称支持任意三维切片。

缺失/固体数据用显式 mask；不得填零冒充观测。时间严格递增，超出范围显示无数据。线性轨迹插值只连接两帧共同存在的实体。不同运行的绝对时间对齐需要 epoch，relative 必须显式选择。

Geometry 关联分两层：`derived_from` 标明使用的几何版本；layer encoding 标明实际采样域。不能把求解网格索引当作 GLB 顶点索引。非结构网格、Zarr、动态网格是后续扩展，当前读写器未实现时拒绝处理。

## Running

所有注册 method 使用同一生命周期。validate 只读，prepare 写缓存，execute 计算，export 输出自包含 v1.1 payload；框架校验后复制至场景私有资产并登记。失败/取消不得登记半成品。`--no-retain` 保留试跑，随后可 `import-run`。

状态是 preparing/running/exporting/complete/failed/cancelled。数值质量单独写 diagnostics；方法必须抛出收敛/质量失败，不把进程退出 0 等同于物理可信。每个成功结果保留请求、环境、源代码快照、输入校验和、数值诊断、执行日志。

## 兼容

原 Physics4D 导出仍使用 v1.1，可 `canopy import-run SCENARIO DIRECTORY`。旧协议 validator 拒绝 v2 manifest，V2 reader 只接受 2.0.0。原 Canopy 根目录的网页与大型资源继续保持原 URL，作为静态兼容发布；它们不混入 Python package，也不自动转成已验证物理资产。

`storage.local.json` 沿用 data_root/cache_root；元数据在仓库 project，数据在 data_root/project。运行服务器显式映射两个位置，不泄露私有配置和历史记录。

## 已支持的计算表示与耦合

Method 输入除了 asset kind / layer kinds，还可通过 `required_artifacts` 指定计算表示。`heightfield` 定义 shape_yx、spacing_m、origin_m、cell_center、ENU，以及有 hash 的 height/solid 数组。`volume_json` 声明 TCZYX 风场、ENU 分量、m/s、采样时间；`mac_state_json` 另保存正向 cell-face 速度、fluid mask、入口及顶部边界。两种速度表示不能混用。

温度和稳态污染物接口检查风场 `derived_from` 是否包含选定几何的精确版本，并核对原点/格距/shape。输入不匹配需先执行显式转换；未知历史关联保持未知，不能仅凭同一场景自动补上几何依赖。

Imperial Corridor 的历史展示数组保留所有原始 float16 样本、单位与 mask，并转为 `npy_frames`；洪水不等间隔时间逐项复制，太阳时钟不被强行映射为其它物理结果的 epoch。当前视图采用明确的 relative comparison，同一秒值不表示同一个真实事件。
