# 数智选材：性能预测与新配方设计调研及实验报告

## Material Passport

- Origin Skill：academic-research-suite；文献检索、实验执行与验证内联完成。
- Origin Mode：research / run / validate。
- Origin Date：2026-10-19T08:28:15.730714+00:00。
- Version Label：research_v04_report_1。
- Verification Status：VERIFIED，仅指两轮主模型计算逐值复现、数据划分与历史保护检查；材料、工程效用和新配方实测仍未验证。
- 用户约束：每周15–20小时；暂时没有实验室，先完成计算实验与送检方案。

## 1. 本轮回答了什么

本轮完成两条线的方案与实际计算：四项性能的小样本预测，以及受约束配方假设生成和下一步试验选择。81组首轮配置与33组第二轮配置共108个不同配置，含6组重复对照；每轮25个外层折、每折3个内层折。两轮主模型合计14,200次模型/管线训练调用，包含内层选模，并非这么多个独立数据集或材料试验。

最值得保留的结果是低温应变的保守集成信号，以及在有限历史池中先覆盖设计空间的选点策略。当前证据仍不足以把四项预测作为工程判定器，也不足以宣布某个新配方性能更优。原产品版本仍为v0.3，研究模块独立存放。

## 2. 数据审计改变了研究重点

180个历史操作键中，本轮至少有一个可用目标标签且设计基础字段合格的操作键为100个，合并成37个来源/原料曲线族代理组；四指标完整者为59条。DS、应变、TSR、残留比的可用数分别为85、72、81、79，不能把缺失指标补成实测标签。27条记录的组分曲线待复核，35条不满足本轮完整组分描述符所要求的全部核对条件。

存在15组相同已知设计输入的碰撞，其中一组DS标签跨度8402次/mm。这是当前输入表达的不可识别性证据：同一个X无法唯一解释这些结果。原料真实身份、改性/再生剂、旧结合料与试验条件等可能解释差异，但这些解释尚待原始证据，不能当成已经发现的因果因素。未因预测误差大而删掉不利记录，也未把来源代码当特征。

标签相关性也不支持无条件共享：DS与低温应变约-0.08，应变与残留比约0.52，TSR与残留比约0.37。它们只是当前选择性历史记录的描述相关，任务迁移是否有用必须由共同分组验证决定。

## 3. 调研后采用的技术路线

小样本下，模型选择带来的乐观偏差与估计方差都需要控制。因此将整条选模流程置于外层评估，所有填补、缩放、标签标准化、任务相关矩阵和集成权重只使用训练组；重复划分用于检查稳定性，不能增加独立样本量。依据：[Bias in error estimation when using cross-validation for model selection](https://link.springer.com/article/10.1186/1471-2105-7-91)、[Cross-validation failure: small sample sizes lead to large error bars](https://arxiv.org/abs/1706.07581)、[Cross-validation: evaluating estimator performance](https://scikit-learn.org/stable/modules/cross_validation.html)。

协同预测采用两种可核对实现：任务核及降秩岭回归。任务核形式为 `K((x,t),(x',t')) = k(x,x') B[t,t']`，B由训练内可观测成对标签估计、投影为半正定并收缩；对角B作为不迁移对照。缺失标签不进入核的观测向量。降秩回归只在训练内部迭代填补缺失目标并收缩共享系数。它们是本项目小样本研究实现，未声称完整复现原论文优化器。方法依据：[Multi-task Gaussian Process Prediction](https://proceedings.neurips.cc/paper_files/paper/2007/hash/66368270ffd51418ec58bd793f2d9b1b-Abstract.html)。

首轮比较基础设计、完整可用级配及紧凑级配/交互表达；覆盖均值、中位数、岭、贝叶斯岭、弹性网、SVR、核岭、GPR、极端随机树、直方图提升、任务核与降秩模型，并对DS测试对数变换。第二轮加入12个由已披露组分份额与原料密度构造的名义描述符。未核对的组分保留缺失，不将名义密度代理误称为确认后的物理配比。

第二轮明确属于看过首轮结果后的探索：冻结33组配置，使用同一外层折作配对比较。增加固定半均值集成、保守内层筛选和非负凸权重共享。它不是新的独立测试集，不能据此宣布确认性胜出。

## 4. 预测结果：改善和退步同时保留

下表每项使用相同来源划分和对应原始标签；MAE越低越好。

| 指标 | 同划分均值基线 MAE | 原选模流程 MAE | 新保守集成 MAE | 相对均值变化 | 改善轮数 |
|---|---:|---:|---:|---:|---:|
| 动稳定度 DS（次/mm） | 1565.867 | 1681.512 | 1545.025 | 下降1.33% | 4/5 |
| 最大弯拉应变（με） | 286.594 | 313.601 | 273.002 | 下降4.74% | 5/5 |
| 冻融劈裂比 TSR（百分点） | 3.540 | 3.782 | 3.494 | 下降1.30% | 4/5 |
| 残留稳定度比（百分点） | 2.889 | 3.170 | 2.963 | 上升2.58% | 0/5 |

保守集成相对于旧自动选模流程四项均下降，但强均值对照仍然重要：对均值只有前三项小幅改善，残留比退步。应变5/5轮改善，均值误差差的来源组聚类描述性95%分位范围约[-26.10,-1.32]με；这只是该历史数据条件下的稳定性描述。第二轮具有适应性研究过程，不能将这个区间当独立新材料的确认性显著性。

事先登记的内部候选要求为MAE下降至少5%、至少4/5轮改善、误差差上界为负。保守集成的应变下降约4.74%，仍未达到5%门槛；不因接近门槛而事后修改规则。当前没有模型升格为正式工程判定模型。

以下是首轮在全部外层结果中事后挑出的最优固定配置，仅作为后续研究线索：

| 指标 | 事后最优固定配置 | MAE | 相对均值下降 |
|---|---|---:|---:|
| 动稳定度 DS（次/mm） | `compact:reduced_rank:alpha=100,rank=1` | 1460.471 | 6.73% |
| 最大弯拉应变（με） | `compact:svr:C=0.5` | 259.697 | 9.39% |
| 冻融劈裂比 TSR（百分点） | `basic:task_kernel:factor=3,noise=0.5,strength=0` | 3.375 | 4.65% |
| 残留稳定度比（百分点） | `basic:reduced_rank:alpha=100,rank=2` | 2.772 | 4.05% |

不能把四行各自挑出的最好值拼成一个已经验证的四任务系统。嵌套自动选择总体仍未稳定战胜均值，说明小样本选模方差是实际问题。任务共享和新增密度描述符没有带来一致的四指标提升，原料信息仍需补齐。

## 5. 不确定性与负对照

完成100组学习曲线、40组训练标签向量随机化负对照，以及15次联合最大残差校准试验。负对照只随机训练标签，不改变测试真实值；未用这些诊断制造显著性p值。

联合校准按来源组划分训练、10组校准、7组测试，分数为组内各条记录各可观测任务的最大标准化残差，同时报告四指标完整测试记录的覆盖分母。覆盖大致达到研究目标时，区间往往极宽：任务核平均DS宽度约15128次/mm、TSR约32.44个百分点，工程区分度有限。未观测指标不能验证覆盖，组交换性尚未确认。

GPR标准差、统计覆盖和工程验收是不同证据。相关依据：[Gaussian Processes](https://scikit-learn.org/stable/modules/gaussian_process.html)、[A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification](https://arxiv.org/html/2107.07511v6)。本轮未对外发布多指标工程通过概率。

## 6. 新配方的反向设计已经计算到哪一步

从可核对组分的历史配方出发，完成1098个局部未试验假设：油石比±0.1/0.2个百分点，或在已披露且活跃的新集料料堆之间转移名义2%份额。固定基质名义牌号与名义RAP，不发明未披露的改性剂、再生剂或其用量。

生成时检查非负份额、名义和为1、原表混合曲线与分量重算一致、级配通过率0–100且随筛孔递减。731个通过当前基础设计距离与同公称粒径观测曲线包络检查。这个包络不是规范包络，距离支持不代表性能准确；所有1098个方案均无新实测、无父配方性能继承，工程放行数为0。

保存候选、预测、模型不确定性、父方案预测差、名义组分与原表行号，并用第二个保守集成对10个候选作交叉检查。预测Pareto只在代理模型下成立，不是实测最优或稳健最优配方。

长期采用“硬约束候选生成→可靠性检查→试验选点→真实回流→冻结后验证”的结构。贝叶斯多目标优化与输入噪声研究提供方法方向，但当前未声称实现qLogNEHVI或在未知噪声下找到稳健最优。依据：[Constrained multi-objective optimization with qNEHVI and qParEGO](https://botorch.org/docs/tutorials/constrained_multi_objective_bo)、[Robust Multi-Objective Bayesian Optimization Under Input Noise](https://proceedings.mlr.press/v162/daulton22a.html)。

## 7. 如何选择更值得检测的材料

先在59条四指标完整记录、32个来源代理组上隐藏目标标签，比较6种策略、10种初始划分，共60次顺序回放；一次查询揭示整个来源组，避免同组记录暗中泄漏。再补做180次按配方记录数量限制的回放，防止大来源组获得更多标签却被算成同样一次检测。

最后在同一历史池上进行100种初始化×3种预算×3种策略，共900次随机基线敏感性回放。目标固定为研究演示值DS>6000、应变>2200、TSR>85、残留比>85；不等同于真实项目要求。表中为新增找到满足四项数值目标的历史记录数均值：

| 新增历史配方记录预算 | 按来源组随机 | 按配方随机 | 空间覆盖 |
|---:|---:|---:|---:|
| 10 | 0.43 | 0.98 | 2.45 |
| 20 | 1.09 | 2.01 | 2.85 |
| 30 | 1.77 | 2.92 | 3.23 |

三种策略在上述预算下平均实际消耗均恰好达到10/20/30条记录；组内多条记录全部计费。空间覆盖在此有限池较早发现可行记录，表明预测薄弱时先覆盖设计差异值得优先研究。按组随机和按配方随机的差异同时保留，避免依靠较弱随机口径夸大效果。

这些是同一完整案例池上的初始化敏感性，不是900个独立材料数据集，不是1098个新配方已被验证，也不能换算成节省了多少实际试件、工时或经费。材料选点的比较原则参考[Benchmarking the performance of Bayesian optimization across multiple experimental materials science domains](https://www.nature.com/articles/s41524-021-00656-9)。

## 8. 没有实验室时已经准备好的送检方案

先导选用来源代码H的AC-13-110#家族作为待确认材料体系，代码不等于实际供应商身份。拟5种配方：重新制备的原配方、油石比低/高各一档、名义集料比例双向微调各一档。每种拟独立制备3批，共15个制备批次、60个批次指标结果；不是60个试件，也不是已经执行的检测数量。

送检之前需要确认材料/批次、RAP计量分母、含水与旧/有效结合料、工程目标条款、级配包络、方法版本、温度/荷载/老化或冻融条件、实际试件数、施工适用性。未知项在交接表中保持为空。

在同原料批次与制备日内随机安排原配方和新方案，尽量盲化检测身份。原配方必须同期重新制备，不能拿历史极端结果作对照。三批仅用于先导估计波动；根据实际重要差异与先导方差另行计算确认性复验数量。选优后的同一批数据不能再次被称为独立验证。

平衡开裂、车辙和其他指标、记录压实及老化条件的工程思路参考[Development of Balanced Mixture Design Index Parameters and the Flex Suite of Performance Analysis Tools for Asphalt Pavements](https://highways.dot.gov/sites/fhwa.dot.gov/files/FHWA-HRT-24-113.pdf)；该来源不授权本项目的中国工程阈值。当前没有实验室，不执行或虚构新试验，不代填实验室报价，也没有向外发送资料。

## 9. 外部数据能否直接增加样本

检查到的沥青断裂研究含物理代理目标及体积/力学试后特征，其任务与我们的设计前四指标不一致，不能直接搬用其高分或把VV、稳定度、流值放进设计前预测。见[An integrated physics-guided machine learning approach for predicting asphalt concrete fracture parameters](https://www.nature.com/articles/s41598-025-32041-7)。

另找到再生防水材料的公开实验仓储，记录了流变、TSRST及水敏感性等，但本轮只检查明确V1元数据，尚未证明方法、单位、材料体系和授权兼容，未下载后混入官方训练表。见[Laboratory data on mechanical and rheological properties of binders, mixtures, and asphalt concretes with content of recycled asphalt waterproofing material](https://zenodo.org/records/21675682)。下一步先建立材料、指标、方法、条件、独立批次和授权的兼容矩阵，不能仅凭字段名字相似就合并数据。

## 10. 下一步投入顺序与完成边界

优先补料源和试验口径、核对同输入异标签记录，再将当前5配方先导交接表完善为确认后的实际称料/送检表。取得新独立批次后，先盲测已冻结的保守集成与均值对照，再决定是否重训练。真实数据足够时再做ARD任务核、局部/异方差区间和带噪约束多目标优化，不继续在同一外层结果上堆叠调参来充当新证据。

本轮计算、研究方案、可复用候选模型和送检资料已完成；新配方实测优效、真实料源泛化及工程验收仍待外部条件。新模型没有替换v0.3判定逻辑，独立材料试验数为0。

## 11. 复核入口

- [研究协议](C:/Users/Lenovo/Desktop/智慧城市/artifacts/research-v04/protocol.json)、[第二轮协议](C:/Users/Lenovo/Desktop/智慧城市/artifacts/research-v04/advanced-protocol.json)、[全部模型结果](C:/Users/Lenovo/Desktop/智慧城市/artifacts/research-v04/benchmark.json)、[集成结果](C:/Users/Lenovo/Desktop/智慧城市/artifacts/research-v04/advanced.json)。
- [候选模型卡](C:/Users/Lenovo/Desktop/智慧城市/artifacts/research-v04/candidate-model-cards.json)、[全部未试验配方](C:/Users/Lenovo/Desktop/智慧城市/artifacts/research-v04/formulation-search.json)、[100初始化回放](C:/Users/Lenovo/Desktop/智慧城市/artifacts/research-v04/baseline-sensitivity.json)。
- [可打印送检方案](C:/Users/Lenovo/Desktop/智慧城市/docs/research-v04-lab-handoff.html)、[结构化交接与空白结果](C:/Users/Lenovo/Desktop/智慧城市/artifacts/research-v04/laboratory-handoff.json)。
- [最终验证](C:/Users/Lenovo/Desktop/智慧城市/artifacts/research-v04/final-verification.json)：两轮全部OOF预测逐值复现；82项Python检查通过；原84个保护文件、6张原表和v0.2/v0.3归档保持不变。11/11项统计误用扫描含选择偏差和因果边界。

复现命令在项目根目录执行，默认拒绝覆盖已有结果；重跑应指定新的输出目录。`freeze`先登记协议，`benchmark`执行首轮，随后依次执行`advanced`、`diagnostics`、`replay`、`cost-replay`、`baselines`、`search`、`fit-candidates`。完整逐值验证另见`reproduction`目录。

```powershell
.venv\Scripts\python.exe -X utf8 scripts/research_v04.py freeze --output artifacts/new-research-run
.venv\Scripts\python.exe -X utf8 scripts/research_v04.py benchmark --output artifacts/new-research-run
```

## 12. 定向调研来源登记

检索日期2026-10-19。仅列原始研究、作者材料、官方文档和原始数据仓储；本报告不是系统综述。存在性及使用范围按实际访问页面登记；未宣称全文人工阅读、全面撤稿核验或跨模型专家评审。完整字段见`docs/research-v04-sources.json`。

| 编号 | 来源与实际读取范围 | 对本项目的作用 |
|---|---|---|
| R01 | [Bias in error estimation when using cross-validation for model selection](https://link.springer.com/article/10.1186/1471-2105-7-91)；出版方正文中嵌套交叉验证结果与结论 | 外层只评估完整选模流程；训练内部选参。发布全部配置，明确区分固定配置事后最好成绩。 |
| R02 | [Cross-validation failure: small sample sizes lead to large error bars](https://arxiv.org/abs/1706.07581)；作者预印本元数据与摘要 | 五次分组划分、来源组聚类误差诊断；不将重复预测当成新增独立样本。 |
| R03 | [Multi-task Gaussian Process Prediction](https://proceedings.neurips.cc/paper_files/paper/2007/hash/66368270ffd51418ec58bd793f2d9b1b-Abstract.html)；会议官方摘要 | 实现缺失标签可用的任务核及对角核消融。使用训练内经验相关矩阵收缩，不冒充原论文的完整优化模型复现。 |
| R04 | [Cross-validation: evaluating estimator performance](https://scikit-learn.org/stable/modules/cross_validation.html)；1.9.1 GroupKFold与分组验证章节 | 四个指标共用操作键和来源族划分，逐折记录组与样本ID，保留不平衡。 |
| R05 | [Gaussian Processes](https://scikit-learn.org/stable/modules/gaussian_process.html)；1.9.1 GPR、核函数与噪声说明 | 保留独立GPR对照，明确任务核返回的标准差未经工程校准，不将其直接称为可靠性。 |
| R06 | [Constrained multi-objective optimization with qNEHVI and qParEGO](https://botorch.org/docs/tutorials/constrained_multi_objective_bo)；约束多目标闭环结构与数值警告 | 当前采用可审计有限候选与局部扰动，未宣称实现qLogNEHVI。具有可靠实测回流后再评估相应优化器。 |
| R07 | [Robust Multi-Objective Bayesian Optimization Under Input Noise](https://proceedings.mlr.press/v162/daulton22a.html)；PMLR官方元数据与摘要 | 将称量、批次与制备波动纳入后续送检设计，当前不虚构噪声分布或稳健最优结论。 |
| R08 | [Benchmarking the performance of Bayesian optimization across multiple experimental materials science domains](https://www.nature.com/articles/s41524-021-00656-9)；出版方摘要与数据代码可用性章节 | 同初始数据、同预算比较多种选点策略；增加两种随机基线与100种初始化。未把论文其他材料的收益迁移成我们的收益。 |
| R09 | [A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification](https://arxiv.org/html/2107.07511v6)；校准集规模、覆盖率检查及交换性相关正文 | 研究性联合最大残差校准同时报告覆盖分母与区间宽度，不提供跨料源或工程验收保证。 |
| R10 | [Development of Balanced Mixture Design Index Parameters and the Flex Suite of Performance Analysis Tools for Asphalt Pavements](https://highways.dot.gov/sites/fhwa.dot.gov/files/FHWA-HRT-24-113.pdf)；报告引言、平衡设计指标、材料因素与不确定性相关段落 | 送检保留多指标与施工条件；该美国报告不作为中国项目阈值或试验方法授权。 |
| R11 | [An integrated physics-guided machine learning approach for predicting asphalt concrete fracture parameters](https://www.nature.com/articles/s41598-025-32041-7)；特征清单、代理目标说明与数据可用性章节 | 不直接套用其性能数值、不加入我们的试后VV/稳定度/流值作设计前特征，也不把代理断裂目标当实测四指标。 |
| R12 | [Laboratory data on mechanical and rheological properties of binders, mixtures, and asphalt concretes with content of recycled asphalt waterproofing material](https://zenodo.org/records/21675682)；明确版本V1的仓储描述与文件清单，未下载或逐行核验数据 | 列为后续跨域方法研究候选，指标定义和材料体系未证明兼容，本轮未并入官方数据或充作独立配方验证。 |
