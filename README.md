# 数智选材

v0.2基于企业提供的再生沥青混合料工作簿，支持场景条件生成带来源需求、工程师确认、全目录候选检索、四态约束、最小冲突证书、完整材料比较、单元格追溯、微调失效和下一步验证计划。数值初筛通过后仍需工程适用性审核与独立试验。

## 运行

当前机器环境已准备好，在项目目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1
```

打开 `http://127.0.0.1:8766/`。后端同时提供本地前端静态资源；启动后核心功能不请求公网服务。API文档在 `/docs`，离线交接使用 `docs/api-v2.openapi.json`。`/v1`与历史初筛保留；新主流程使用`/v2`。

新机器先安装 Python 3.12+、Node.js 24、pnpm 11，再执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1 -Python python
```

首次安装需要网络下载依赖。安装完成后的启动与历史选材可离线进行。依赖锁为 `requirements.lock.txt` 与 `frontend/pnpm-lock.yaml`，尚未捆绑 Python/Node 解释器。

## 数据与模型

原始工作簿、赛题 PDF 和调研底稿保持原样。导入命令接受明确的文件路径，校验表头布局，按文件 SHA256 与导入器版本幂等处理。新导入器会保留旧数据版本和旧报告。

```powershell
$env:PYTHONPATH='backend'
.venv\Scripts\python.exe -X utf8 -m app.importer '再生沥青混合料实验数据表.xlsx'
.venv\Scripts\python.exe -X utf8 -m app.ml.train
.venv\Scripts\python.exe -X utf8 scripts/replay_test_selection.py
```

模型使用设计前输入，按来源代码与完整非零原料曲线族阻断，外层5折、内层3折。四个自动选择流程的首轮外层 MAE 均未优于均值基线，保留研究模式。区间采用独立训练、12个校准组和8个测试组，实验覆盖率不构成工程保证。完整结果在 `artifacts/models/model_cards.json`。

RAP名义质量基准尚待确认，自动配方优化禁用。微调会生成未试验版本，清空父方案性能依据。没有价格、碳因子或路面寿命实测数据，不显示这些效果。

## 验证与演示

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check.ps1
```

主流程从当前180个历史操作键检索。五个构造案例在相同AC-13完整目录范围（84条，包含缺测）比较时，B1与V2数值可行数分别为2、2、5、1、0。C5在此范围为证据不足；明确选择35条完整数值子池时才有四组最小冲突。三类场景规则与C4/C5明确选择的附加要求模板分开标注，均非区域规范。

历史初筛保留原固定小池回归：C1→R1、C2→R4、C3→R7、C4→R5、C5→空；这些小池不是V2主流程的候选范围。完整比较报告在`artifacts/next-phase/case-reports`，冻结快照以`.json.gz`无损保存。

```powershell
.venv\Scripts\python.exe -X utf8 scripts/compare_cases_v2.py
.venv\Scripts\python.exe -X utf8 scripts/rehearse_v2.py --run-id local-rehearsal
.venv\Scripts\python.exe -X utf8 scripts/mock_upstream_v2.py
```

试验回流默认“演示”，需审核并确认条件后才能影响相同数据范围的新推荐。正式项目排除演示回流；训练排除全部演示回流和未试验微调版本。审核人是本地声明字段，当前版本无多用户登录、权限和电子签章，适合单人本地演示。

v0.2执行证据见`artifacts/next-phase/execution_progress.json`。旧计划和验收历史保持原样。规则、适用性、反馈、交互与应用价值口径分别见`docs/scene-rule-cards.md`、`docs/evidence-applicability-policy.md`、`docs/feedback-contract-v2.json`、`docs/interaction-checklist-v2.md`、`docs/value-evaluation-notes.md`。本地上游模拟不等于企业真实联调；软件代理时延不等于真人节时。条件研究按每周15–20小时的选择延后。
