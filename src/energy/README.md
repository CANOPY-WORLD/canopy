# Tower Hamlets energy pilot

已有 Canary Wharf 4 km 场景上的公开能源设施叠加与假设供需测试。
复用统一查看器、坐标、时间轴、JSON 标量/曲线和 GLB 图层。

## 数据与边界

- GLA London Heat Map：下载现有/规划热网线位、能源中心及热网规划项目。
  保存官方 ArcGIS 元数据、完整查询 URL、获取时间、许可和 SHA-256。
  按原图层保留现有/规划类别，逐项状态见 `inventory.json`。
- 电力设施和充电站：复用场景已保留的 2026-10-07 OSM 文件，保留 OSM ID、
  tags、版本和时间。不是实时运营清单。UKPN 公开目录要求登录，未获取受限记录。
- 坐标：沿用场景以 (-0.0188, 51.5053) 为原点的 WGS84 AEQD 米制坐标，
  先投影再裁剪到 [-2000,2000]²。范围跨行政边界，不代表塔村区全区统计。
- 设施球体位于屋顶上方以便辨认；热网线宽、显示高度不是实测管径或埋深。
  粉色实线是 GLA 现有热网，橙色虚线是规划热网，蓝色虚线是假设电连接。
  OSM 原始电缆/线路标签保存在输入中，未推断或展示完整馈线拓扑。

## 假设计算

选取六个不同名称建筑的互不重复高位栅格区域。使用已保存的
`canary_wharf_sunlight027` 11 帧水平顶面辐照（2026-06-21 12:00–12:10 UTC）。
保留原来的 600 秒窗口，不补全天数据。屋顶适用性、坡度、实际设备均未核实。

配置明确假设：20% 顶面面积铺光伏、20% 转换效率、0.85 性能系数；
每栋建筑基础用电 120 kW、供热 60 kW、热泵 COP=3；
Canary Wharf 已标注充电站的测试用电从 20 增至 220 kW。
这不是该站真实负荷或设备额定容量。

电网净取电 = 基础用电 + 热泵用电 + 充电用电 - 光伏。
热泵供热 = 热泵用电 + 环境取热。允许电网净取电为负表示反送。
这是无网络损耗的供需平衡测试，没有求解电压、交流潮流、线路容量或热网水力。
假设热泵不代表已连接地图中的任一供热网络。

## 重跑

在含 `src/energy/requirements.txt` 可选依赖的 Python 环境中：

```bash
PYTHONPATH=src python -m energy.pilot \
  --config project/tower_hamlets/configs/energy_pilot.json --retain
```

添加 `--source project/tower_hamlets/input/energy_open_<时间与标识>` 可以复用校验后的
下载快照。每次运行创建新目录；`--retain` 保留到 runs 并注册独立视图，不改默认视图。
输入位于 project/input，试跑位于 cache，所需输入、配置与源码快照随正式运行保留。
`catalog/*.json` 把标量图层的数组索引映射到设施/建筑名称；`inventory.json` 保存公开属性。

```bash
PYTHONPATH=src python -m unittest discover -s tests -p 'test_energy_pilot.py' -v
python3 tools/check_contract.py project/tower_hamlets/runs/<run_id>/manifest.json
PUPPETEER_MODULE=<puppeteer-core入口绝对路径> \
UWM_VIEWER_URL='http://127.0.0.1:8937/src/visualization/viewer/?scene=tower_hamlets&view=<view_id>' \
node tests/browser_energy.cjs
```

浏览器检查图层加载、300 秒供需平衡、点击取值、显隐、时间越界隐藏和资源释放。
只在本地保留数据与结果；未发布。

### ATES city prototype

`ates_export` connects recorded surrogate cycle energies to two hypothetical wells,
six buildings and an assumed COP=4 heat pump. The cycle view uses MWh per completed
cycle pair, not instantaneous power. It preserves the nine original aggregates and
compares warm recovery with the source simulation. Well placement and demand are
scenario assumptions, not validated Canary Wharf geology or infrastructure.

```sh
PYTHONPATH=src cache/energy_runtime/bin/python -m energy.ates_export \
  --config project/tower_hamlets/configs/ates_demo.json \
  --cycle-source /home/yl222/workspace/geothermal/expout/application_20260930 --retain
```

`stage_ates` can stage the user's Vega checkpoints, upstream implementation and
recorded scenario with hashes after SSH authentication is renewed. `ates --source
<snapshot> --output <recording>` then runs inference with PyTorch. The full-field
export uses `ates_export --inference <recording> --model-source <snapshot>` instead
of `--cycle-source`. This inference path awaits validation with the actual weights;
the cycle-only view deliberately contains no substitute temperature fields.

`thermal_slice` is a presentation adapter for existing JSON scalar-field payloads,
with coplanar regularly spaced samples and physical-size tiles. It performs no
solver computation. The viewer accepts optional model-year presentation metadata;
manifest timestamps stay in seconds. Fixed injection schedules are unchanged by
building demand: the heat-pump calculation is one-way accounting, excluding pump
power and distribution losses.
