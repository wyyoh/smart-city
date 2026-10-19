# 数智选材

v0.4基于企业提供的再生沥青混合料工作簿，支持场景需求确认、全目录候选检索、四态约束、最小冲突证书、材料比较、单元格追溯、微调失效和验证计划。在v0.3成果复核流程上新增“配方研究”：查看未试验配方的具体改动、模型实验的完整结果、原表待复核问题，并保存可打印的试验安排。数值初筛通过后仍需工程适用性审核与独立试验。

## 运行

当前机器环境已准备好，在项目目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1
```

打开 `http://127.0.0.1:8766/`。后端同时提供本地前端静态资源；启动后核心功能不请求公网服务。API文档在 `/docs`，离线交接使用 `docs/api-v2.openapi.json`。`/v1`与历史初筛保留；新主流程使用`/v2`。

默认进入“成果与验证”，可按C5冲突、C1证据、C2验证行动三条路径进入场景选材。该入口逐条列出五项基本成果、十项详细技术要求及七项拆分的加分方向，并显示证据文件当前指纹；这些状态是团队登记，不代表官方验收。

生成材料决策后可“生成选材复核单”。复核内容追加保存于本地库，打印版与JSON使用同一条保存记录，保留生成时间、决策哈希、复核哈希和生成时的当前性检查。后续数据变化时应重新生成；历史复核单保留原内容。新接口契约见`docs/api-v3.openapi.json`。

“依据与阈值”登记交通运输部官方公告版本，不据公告自动补造项目验收值。“外部核验”提供JSON空白模板和只读字段检查，未填真人记录时参与数为0；通过字段校验不意味着证据真实性、工程批准或行业效益已验证。校验不会将数据导入选材或训练库。

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

RAP名义质量基准尚待确认，工程自动配方优化仍未启用。微调会生成未试验版本，清空父方案性能依据。“配方研究”中的计算假设供设计试验使用。没有价格、碳因子或路面寿命实测数据，不显示这些效果。

## 配方研究

侧栏选择“配方研究”，或打开 `http://127.0.0.1:8766/?view=research`。默认保留“成果与验证”入口。

目录提供1098个未试验假设，其中731个同时处于既定设计距离与同公称最大粒径观测曲线范围内。可按来源代码、改动类型、产品与编号筛选，查看组分份额前后变化。观测范围内不表示性能合格；父方案历史实测与新配方研究预测分开展示。

选取1至8种待测配方，可手动加入候选，再按来源代理组分散和设计空间覆盖补齐计划。保存内容绑定生成时的数据版本、研究证据和筛选条件，JSON与打印版来自同一条追加记录。重复相同请求复用原记录；数据或证据过期时拒绝新建计划。数量指配方数，实际试件数、方法、质量基准、费用和工期由后续送检确认。

“模型实验”同时保留改善与退步；新一轮10次分组与上一轮5次分组独立列出。原始结果有1250次拟合和逐值复现记录，未替换正式模型。“原表复核”列出15组已知输入别名，其中11组有标签差异、5组涉及曲线遮蔽，181条源单元格引用可查；这些问题尚待原始资料确认。

新接口使用 `/v4/research`；完整接口契约为 `docs/api-research-v4.openapi.json`，本轮设计、实验和下一步安排见 `docs/research-workbench-v5.md`。五配方送检资料包保留上一轮冻结内容，当前没有新增独立材料试验。

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

v0.3计划为`planning/review_phase_plan_v3.json`，实际执行与验收记录在`artifacts/review-phase`。评审手册可从`/v2/review/handbook.html`打开。核验空白模板为`docs/external-validation-template-v3.json`；填写后可用下述命令检查字段、试验条件及真人三任务三流程配对。该检查不认证文件真实性。

```powershell
.venv\Scripts\python.exe -X utf8 scripts/check_external_validation_v3.py <已填写的JSON路径>
```
