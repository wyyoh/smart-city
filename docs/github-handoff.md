# GitHub 项目交接与证据索引

仓库保存数智选材的完整源代码、创意方案、赛题与原始工作簿、案例报告、计算研究及复现证据。2026年10月25日上传 v10 材料，应用版本仍为0.4.0。当前技术正文为 `docs/submission-final-v10.md`，50页论文及其源稿分别位于 `output/submission-v10/07_作品论文/` 和 `docs/paper-v10/`。全部21个附件位于 `output/submission-v10/`，完整下载包为 `output/数智选材_参赛材料_v10.zip`。历史报告保留原版。

## 克隆与启动

安装Python 3.12以上、Node.js 24和pnpm 11后，在PowerShell执行：

```powershell
git clone https://github.com/wyyoh/smart-city.git
cd smart-city
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1 -Python python
powershell -ExecutionPolicy Bypass -File scripts/start-creative-demo.ps1
```

打开 `http://127.0.0.1:8766/?view=design`。首次建立独立案例演示库，后续保留本地操作记录。首次安装依赖需要网络，安装后的核心操作可在本地运行。目录没有捆绑Python、Node或依赖缓存。`start-local.ps1 -Demo`仍可查看旧复核单演示库。

## 运行资源包

`artifacts/distribution/runtime-assets.zip`已重新构建，保存冻结研究输入库、默认库与历史演示库快照、四项研究模型、当前前端，以及v0.2和v0.3历史交付包。逐文件大小、SHA256和前端源文件指纹在同目录 `runtime-assets.json` 中。独立Git导出验证会恢复资源并实际执行五案例、偏好与配方草案；验证限于本机准备好的依赖环境。

这些二进制资源以压缩包随仓库提交，避免直接跟踪会持续变动的SQLite运行库。`setup.ps1`自动调用恢复脚本；也可单独运行：

```powershell
python scripts/restore_published_assets.py
```

脚本先核对资源包和每个文件的哈希与路径，再恢复缺失文件。已有用户数据库和前端构建会保留；若已有冻结研究输入或模型与清单不同，脚本报错并保留原文件。恢复操作不会覆盖既有用户数据。

## 证据入口

| 内容 | 位置 |
| --- | --- |
| 当前技术说明与50页论文源稿 | `docs/submission-final-v10.md`、`docs/paper-v10/` |
| 全套参赛附件与上传说明 | `output/submission-v10/`、`docs/submission-materials-v10.txt` |
| v10材料、版式、视频与解压运行核验 | `artifacts/editorial-v10/` |
| 当前五案机制、操作与证据 | `docs/creative-demo-v7.md`、`artifacts/polish-v7/` |
| v10操作视频及字幕 | `artifacts/editorial-v10/demo/` |
| 原始赛题、工作簿与调研底稿 | 仓库根目录 |
| 场景需求、候选检索与软件案例对照 | `design/`、`configs/`、`artifacts/next-phase/` |
| 成果复核与历史交付证据 | `artifacts/review-phase/` |
| 模型、配方与计算实验及复现 | `artifacts/research-v04/`、`artifacts/research-workbench/` |
| 创意范围调整、原文页与页面证据 | `artifacts/creative-scope/` |
| GitHub交接的检查记录 | `artifacts/github-publish/` |

运行 `scripts/check.ps1` 可执行Python回归、前端构建和既有计划校验。历史报告与完成回执保留当时版本的事实；当前创意交付范围以 `configs/creative_scope_v6.json` 为准。

公开研发仓库与匿名提交包分别生成。v10的“原型源码与证据.zip”收录683个文件，其中656个原型运行文件与冻结版本逐字节一致，另附本轮说明、论文源稿及核验资料。压缩包附有逐文件清单，并已解压验证五个案例、偏好切换和配方草案。简表的队伍与联系字段按匿名要求留空；登记信息仍以参赛者报名后台为准。

历史证据按原始文件字节记录SHA256，仓库通过 `.gitattributes` 保留文件原有换行，避免克隆时自动转换而使证据校验失效。
