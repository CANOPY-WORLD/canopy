# 验证记录

验证日期：2026-11-17。工作目录是独立 Canopy checkout，Physics4D 源 checkout 保持不变。

- 59 项 Python 检查通过：43 项移植协议回归 + 16 项 Canopy 生命周期、资产归属、校验和、取消、失败、打包及数值检查。
- 5 项 JavaScript 检查通过：坐标转换、时间范围与插值、静态层、路径隔离、稀疏轨迹实体生命周期。
- CPU 完整链路：geometry/heightfield → solar/shadow、flood/shallow_water、wind/mac → 场景私有资产 → 固定 Visualizer。
- 洪水平底封闭盆地测试验证累计降雨与水深/体积一致；MAC 原生投影残差检查生效；太阳与风场数组验证有限值及协议。
- 合成场景浏览器：6/6 层加载，显隐、时间控制、播放暂停、相机操作通过；1440×1000 与 390×844 无水平溢出，无页面/网络错误。
- 真实 South Kensington、White City：各自几何、记录风场与温度的完整 payload/hash 校验通过；同一模板分别 3/3 层加载，无页面错误。
- Python wheel 成功构建，约 1.9 MB；在独立临时安装目录、仓库外工作目录中验证模型发现、几何执行、资产保留及完整校验，schema 不依赖源码路径。
- 场景归档包含 scenario.json、登记资产与来源，排除 cache；重复归档不覆盖已有文件。

详细本机日志和截图在 cache/qa/，属于可重算验证材料；源码及场景归档在 dist/。这些目录不自动发布。

边界：没有重跑长期城市仿真，也没有验证所有历史 compatibility entrypoint 的外部数据/软件环境。检查不证明太阳/风/洪水的城市预测精度。真实城市结果是原始记录的移植，未补造帧或推断未记录的 geometry dependency。
