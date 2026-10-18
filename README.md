# 数智选材

基于企业提供的再生沥青混合料工作簿，提供场景目标初筛、候选比较、单元格追溯、设计微调、试验审核和方案报告。本地原型面向道路养护选材研究，数值初筛通过后仍需工程适用性审核与试验。

## 运行

当前机器环境已准备好，在项目目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1
```

打开 `http://127.0.0.1:8766/`。后端同时提供本地前端静态资源；启动后核心功能不请求公网服务。API 文档在 `/docs`，完整 OpenAPI 在 `/openapi.json`。交接使用 `docs/api.openapi.json`，无需联网。

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

工作台的五个构造案例由正式导入结果实时计算：C1→R1，C2→R4，C3→R7，C4→R5，C5→空。目标出处在每项规则及报告中保留；演示目标不是区域规范。

试验回流默认“演示”，需审核并确认条件后才能影响相同数据范围的新推荐。正式项目排除演示回流；训练排除全部演示回流和未试验微调版本。审核人是本地声明字段，当前版本无多用户登录、权限和电子签章，适合单人本地演示。

项目说明见 `docs/developer-guide.md`、`docs/data-contracts.json`、`docs/enterprise-questions.md` 与 `docs/demo-script.md`；执行状态记录在 `planning/development_backlog_v1.json`。
