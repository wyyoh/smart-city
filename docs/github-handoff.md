# GitHub 项目交接与证据索引

仓库保存数智选材的完整源代码、创意方案设计、赛题与原始工作簿、案例报告、计算研究、复现记录、测试结果和界面截图。当前定位为创意方案与可演示原型；实物实验是可选拓展，下一阶段创意深化任务仍按原计划登记。

## 克隆与启动

安装Python 3.12以上、Node.js 24和pnpm 11后，在PowerShell执行：

```powershell
git clone https://github.com/wyyoh/smart-city.git
cd smart-city
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1 -Python python
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1 -Demo
```

打开 `http://127.0.0.1:8766/`。`-Demo` 使用交接时已有决策与复核单的演示数据库；不加该参数使用默认本地库。首次安装依赖需要网络，安装后的核心操作可在本地运行。目录没有捆绑Python、Node或依赖缓存。

## 运行资源包

`artifacts/distribution/runtime-assets.zip`保存冻结研究输入库、默认库与演示库快照、四项研究模型、前端构建文件，以及v0.2和v0.3的最终历史交付包。逐文件大小与SHA256在同目录的 `runtime-assets.json` 中。

这些二进制资源以压缩包随仓库提交，避免直接跟踪会持续变动的SQLite运行库。`setup.ps1`自动调用恢复脚本；也可单独运行：

```powershell
python scripts/restore_published_assets.py
```

脚本先核对资源包和每个文件的哈希与路径，再恢复缺失文件。已有用户数据库和前端构建会保留；若已有冻结研究输入或模型与清单不同，脚本报错并保留原文件。恢复操作不会覆盖既有用户数据。

## 证据入口

| 内容 | 位置 |
| --- | --- |
| 当前创意定位与下一轮计划 | `docs/creative-proposal-scope-v6.md`、`planning/creative_proposal_phase_v6.json` |
| 原始赛题、工作簿与调研底稿 | 仓库根目录 |
| 场景需求、候选检索与软件案例对照 | `design/`、`configs/`、`artifacts/next-phase/` |
| 成果复核与历史交付证据 | `artifacts/review-phase/` |
| 模型、配方与计算实验及复现 | `artifacts/research-v04/`、`artifacts/research-workbench/` |
| 创意范围调整、原文页与页面证据 | `artifacts/creative-scope/` |
| GitHub交接的检查记录 | `artifacts/github-publish/` |

运行 `scripts/check.ps1` 可执行Python回归、前端构建和既有计划校验。历史报告与完成回执保留当时版本的事实；当前创意交付范围以 `configs/creative_scope_v6.json` 为准。

历史证据按原始文件字节记录SHA256，仓库通过 `.gitattributes` 保留文件原有换行，避免克隆时自动转换而使证据校验失效。
