# 验证记录

验证日期：2026-11-17。修改目录为独立 Canopy checkout；Physics4D 源 checkout 未修改。

| 检查 | 结果与实际范围 |
| --- | --- |
| Python | 63 项通过：43 项移植协议检查 + 20 项 Canopy 生命周期、归属、校验和、取消、失败、归档、GLB 变换、计算耦合及数值检查 |
| JavaScript | 5 项通过：ENU 转换、时间范围/插值、静态层、路径隔离、稀疏轨迹实体生命周期 |
| V1 示例 | `python3 tools/check_contract.py examples/contract-v1/manifest.json` 通过，5 layers |
| README 图 | 4 张 Mermaid 图均通过浏览器实际渲染；截图与 SVG 在 cache/qa/readme-diagrams |
| 合成查看器 | 6/6 layers；图层显隐、时间、播放/暂停、相机；1440×1000 与 390×844 无水平溢出、页面/网络错误 |
| 场景入口页 | 真实和合成场景使用同一入口；1440×1000 / 390×844 布局通过；仅提供只读数据加载 |
| 真实场景查看器 | South Kensington 3/3、White City 3/3、Imperial Corridor 9/9；全部记录末帧可用，无页面或 HTTP 错误 |
| 耦合查看器 | geometry → wind → temperature / pollution，4/4 layers；温度沿用风场时间，稳态污染物为 static layer |
| Imperial 数据保留 | 7 个历史资产的 GLB、8 组数组、806 个逐帧 NPY 与来源比较：数值、dtype、时间及 mask 完全相同；无空间重采样 |
| 真实几何计算 | Imperial GLB 节点变换 → 128×128 m 裁剪、4 m 格距、32×32 高度场 → solar，两个运行完整成功；458 个未覆盖采样点显式采用已记录的 0 m 平面基准假设 |
| 安装包 | wheel 构建成功，约 1.9 MB；从独立安装目录、仓库外 cwd 发现全部 8 个 Method，执行几何与五类物理模型、校验 6 个资产；schema 从 wheel 加载 |
| 场景包 | 独立 wheel 运行产物打包为 dist/canopy-demo-scenario-v2.tar.gz，74 文件、约 8.3 MB；包含 Scenario、全部 Asset、请求与 provenance，排除 cache |
| 来源 | physics4d-import.json 的移植文件无缺失；修改清单已更新；两份 V2 schema 完全同步 |

数值检查包括平底封闭盆地降雨质量守恒、MAC 原生压力投影验收、温度 NumPy/PyTorch 一致性、稳态污染物的非负性/线性残差/质量守恒。来源测试确认运行快照包含解释器实际解析的包，即使 metadata workspace 没有源码也可完整记录。

可重算日志和截图在 `cache/qa/`：`python-tests.log`、`javascript-tests.log`、`scenarios-browser.json`、`corridor-preservation.json`、`real-glb-run.json`、`wheel-smoke.json`。构建产物在 `dist/`，均不自动发布。

没有重跑长期城市风场、RANS、交通或研究耦合热环境模拟，也未验证全部 historical compatibility entrypoint 的外部软件和数据。测试验证实现和所列数值性质，不能证明城市预测精度。完整三维场仍作为 artifact 保留；当前统一查看器展示导出的水平切片。原网站的细节地图、交通和 UAV 呈现保留兼容入口，详见 migration-status.md。
