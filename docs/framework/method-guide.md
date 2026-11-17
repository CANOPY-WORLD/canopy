# Model / Method 开发与运行标准

共享 Model 下的每个注册 Method 都必须有 JSON 契约、参数 schema、例子和运行指南。可信注册表在 canopy.models.registry；场景文件不能指定任意 import 或 shell 命令。

## 接入步骤

1. 将可复用求解代码放在 src 中，保留来源与许可证；禁止把场景数据、模型权重和本机路径嵌入代码。
2. 在 src/canopy/models/specs/<model>/<method>.json 声明版本、输入类型、输出 layer kind、依赖、能力及文档路径。参数 schema 禁止额外属性，每个参数有描述、类型、范围、默认值、单位（适用时）。
3. 实现 canopy.models.interface.Method 的 describe / validate / prepare / execute / export。注册可信 adapter，不动态执行 JSON 代码。
4. 输入从 context.inputs 读取，使用精确资产版本；输出只写 context.workspace，不修改输入。不依赖 cwd 或全局环境中的场景身份。
5. execute 在安全步检查 context.checkpoint()；进度 emit('progress',completed=...,total=...)。不支持 resume 时必须明确 false，不能伪造进度百分比。
6. export 返回 manifest.json 所在目录。必须保留坐标、单位、真实时间和缺失掩码；运行框架添加来源快照并校验、登记资产。
7. 编写最小 CPU 示例和适用的数值检验。登记输出之后应能删除 cache 并继续验证和展示。

## 接口

```python
class Method:
    def describe(self): ...
    def validate(self, request, context): ...  # 失败抛出明确错误，无副作用
    def prepare(self, request, context): ...   # 缓存内原生输入
    def execute(self, prepared, context): ...  # 结果及 diagnostics
    def export(self, result, context): ...    # 自包含 payload 路径
```

框架 `canopy.running.runner.run(storage, request, retain=True)` 统一调用这些阶段。request 的 inputs 是场景内引用；parameters 是物理/算法参数；execution 是 cpu/cuda 和线程数。未知字段和 method version 会被拒绝；默认值在保存 request 前补齐。运行状态与数值诊断是不同概念。

## 每份指南必须包含

用途和假设；精确实现路径；环境安装；输入资产要求；全部参数说明；最小运行命令；预期输出；数值有效性检查；资源与停止方式；常见错误；复现边界。外部权重/数据不存在时明确报错，不能静默合成替代结果。

## 常用命令（在 Canopy checkout）

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[physics]'
.venv/bin/canopy --root . models
.venv/bin/canopy --root . models flood shallow_water
.venv/bin/canopy --root . init demo
.venv/bin/canopy --root . run examples/canopy/geometry.json --dry-run
.venv/bin/canopy --root . run examples/canopy/geometry.json
# 用打印出的 geometry asset 引用替换 physics request 中的占位符。
.venv/bin/canopy --root . run examples/canopy/flood.json --dry-run
.venv/bin/canopy --root . run examples/canopy/flood.json
.venv/bin/canopy --root . validate demo
.venv/bin/canopy --root . view demo GEOMETRY_REF PHYSICS_REF --preset laboratory
.venv/bin/canopy --root . serve
```

直接跑完整小示例可用 `canopy --root . demo`，它自动填充真实资产引用。`demo --physics` 只生成几何，`demo --physics flood` 只追加洪水计算。真实研究情景不要使用合成 demo 代替数据准备。

`canopy cancel SCENARIO MODEL RUN_ID` 请求合作式取消；Ctrl-C 也记录取消状态。取消响应在检查点发生，正在执行的单次 GPU kernel 不会被强杀。当前四个 method 不提供 checkpoint resume，重新运行会产生新版本，不覆盖旧资产。

移植的其他 Physics4D 源代码属于 compatibility 实现目录，不代表其所有历史脚本已经注册到统一接口。见 migration-status.md 和 legacy-entrypoints.json；扩展时按本指南逐个升级，不把实验脚本自动暴露为稳定工具。

## 场景打包

`canopy pack demo /absolute/output/demo.tar.gz` 校验并打包完整场景索引、全部已登记资产和 provenance；不包含 cache，不下载未知依赖，不发布任何内容。输出路径不得位于场景资产目录内，已有归档拒绝覆盖。归档内采用 project/<scenario>/... 布局；恢复到新的本地数据根之后，scenario.json 放仓库 metadata 根，其余资产放配置 data_root 对应位置。

`canopy run-task SCENARIO TASK --dry-run` 检查 Scenario.tasks 中保存的请求；去掉 --dry-run 执行同一固定版本输入。demo 自动保存 geometry/solar/flood/wind 对应任务，物理任务引用生成时的确切几何资产，而非以后生成的 latest。
