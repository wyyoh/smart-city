"""Generate and validate the single-developer, six-week work breakdown."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
tasks = []


def task(code, week, hours, priority, title, dependencies, artifacts, acceptance, *, condition=None, fallback=None, optional_inputs=None):
    tasks.append({
        'id': code, 'week': week, 'estimate_hours': hours, 'priority': priority,
        'title': title, 'owner': 'single_developer', 'status': 'ready' if code == 'ENG-01' else 'planned',
        'dependencies': dependencies, 'optional_inputs': optional_inputs or [],
        'artifacts': artifacts, 'acceptance': acceptance,
        'condition': condition, 'fallback': fallback,
    })


task('ENG-01',1,4,'P0','建立可运行工程和依赖锁定',[],
     ['Python项目与React应用骨架','依赖锁文件','本地健康检查'],
     ['独立项目环境能够启动健康检查和空白工作台','记录Python、Node和依赖版本，原始资料不被改写'])
task('DAT-01',1,3,'P0','冻结数据字典与单位身份契约',['ENG-01'],
     ['字段字典','枚举和数据版本规则'],
     ['区分原值、标准值、参考值和派生值','约定来源、完整级配、局部产品、油石比、试验组和来源单元格'])
task('DAT-02',1,6,'P0','将原始工作簿解析固化为导入器',['DAT-01'],
     ['显式输入路径的导入命令','工作表布局配置','导入结果清单'],
     ['重现当前文件的9表、68级配块和2052明细基线，定义一致','仅在真实合并区域展开身份，保留原单元格、公式和文件哈希','重复导入同一文件不产生重复记录'])
task('DAT-03',1,5,'P0','建立身份关联与字段质量隔离',['DAT-02'],
     ['关联状态表','质量问题清单','可用标签与特征清单'],
     ['保留exact、confirmed_alias、conditional、unresolved关联状态','疑似均值、曲线差异、用油异常不自动修正','可靠性能与不可靠输入按字段处理，分别统计可用覆盖'])
task('DAT-04',1,4,'P0','建立SQLite存储和版本化候选目录',['DAT-03'],
     ['数据库模型与建库脚本','目录查询','数据快照'],
     ['记录原始观察、候选版本、规则版本和证据来源','完整关联候选与部分观测候选分开保存','重启后数据仍可查询，同一快照可重建'])
task('TST-01',1,2,'P0','验证导入和数据转换边界',['DAT-04'],
     ['导入回归与异常样例','首轮核验记录'],
     ['TSR小数转百分数仅转换一次，零值与缺测可区分','合并单元格、错误公式、重复导入和未关联记录有明确处理'])
task('BIZ-01',1,2,'P0','形成企业数据核验单与响应登记',['DAT-03'],
     ['问题定位与影响说明','回应和待确认事项登记'],
     ['定位配方别名、疑似均值、曲线与用油问题','未获得回应时明确保留状态及受影响功能，不阻塞基础流程'])

task('RUL-01',2,4,'P0','建立三类场景与规则卡',['DAT-01','DAT-04'],
     ['高温、温缩、水损害场景模式','规则JSON和适用条件'],
     ['企业流程参考、项目目标、演示假设分别标注','规则保存出处、单位、运算符、方法和条件，不将构造值标成规范值'])
task('CAL-01',2,3,'P0','实现组成与用油一致性计算',['DAT-04'],
     ['比例、级配、油量计算模块','可计算与待确认状态'],
     ['在确认的质量基准下检验比例和、加权曲线与油石比转换','质量口径或原料关联未知时返回待确认，不输出伪精确配方'])
task('RUL-02',2,4,'P0','实现候选筛选与排除解释',['RUL-01','CAL-01'],
     ['规则推荐服务','逐指标判定与证据状态'],
     ['严格大于与至少等运算符按规则执行','缺测不视为通过，失败与缺测同时保留','先筛硬约束，再按偏好排序，不用综合分抵消失败'])
task('API-01',2,5,'P0','提供场景和推荐核心接口',['RUL-02','DAT-04'],
     ['场景解析、材料查询、推荐与详情API','OpenAPI与错误样例'],
     ['输出包含输入快照、方案和规则版本、每项数值来源','数据问题与系统异常可区分，空候选是有效结果','API成为判定的唯一计算来源'])
task('WEB-01',2,4,'P0','搭建工作台和场景确认流程',['API-01'],
     ['应用壳层','场景输入与目标确认'],
     ['能选择构造案例并修改结构化场景','缺失必填或规则冲突在提交前后均可见，不静默采用默认气候'])
task('WEB-02',2,3,'P0','展示材料目录与基础依据',['WEB-01'],
     ['候选目录','产品和级配基础信息'],
     ['从正式API展示可关联目录，9候选仅作为固定样例集','局部产品、名义RAP口径和未确认字段可见'])
task('TST-02',2,3,'P0','打通五案例的API和页面流程',['WEB-02','API-01'],
     ['场景到推荐的集成检查','第二周演示版本'],
     ['五场景的数值筛选结果与固定回放基线一致','C5正确返回空候选，确认状态不被解释成工程验收通过'])

task('WEB-03',3,4,'P0','完善多方案比较和空结果处理',['TST-02'],
     ['性能与目标差距比较','候选选择和排除视图'],
     ['切换场景会改变目标、候选和排除理由','缺测维度留空，未知成本和碳排不显示虚构数值'])
task('WEB-04',3,4,'P0','展开单元格证据和数据问题',['WEB-03'],
     ['来源详情面板','试验记录分布与质量说明'],
     ['能定位文件版本、表名、单元格及单位转换','记录极差不显示为预测区间，记录条数不等于独立批次数'])
task('REC-01',3,4,'P0','实现方案版本与人工微调',['WEB-03','CAL-01','API-01'],
     ['方案变体接口','输入差异与状态失效'],
     ['修改产品、比例或用油后生成新版本','旧方案实测结果不自动继承为新方案实测值','无法计算的修改给出具体待确认项'])
task('OBS-01',3,5,'P0','实现试验录入与审核回流',['DAT-04','API-01','WEB-04'],
     ['观察录入与审核接口','验证记录页面','幂等与更正版本'],
     ['保存试验组、条件、单位、数值和来源，未经审核不进入训练视图','重复提交不重复计数，更正保留旧记录','审核后可更新相应候选依据，合成演示记录与正式数据分开'])
task('OUT-01',3,4,'P0','生成可追溯的推荐报告',['WEB-04','REC-01'],
     ['HTML报告','结构化JSON快照'],
     ['包含场景、目标出处、候选、未满足事项、证据与版本','保存报告不会改变审核状态，缺失指标和模型缺席保持原状'])
task('TST-03',3,3,'P0','验收核心业务闭环',['REC-01','OBS-01','OUT-01'],
     ['闭环端到端检查','第三周核心版本'],
     ['场景、推荐、比较、微调、录入、审核、报告全流程可演示','同一输入和版本能重放同一规则结果'])
task('DEM-01',3,2,'P0','整理五案例与首次演示脚本',['TST-03'],
     ['五案例说明与基准对照','3至5分钟操作路线'],
     ['至少覆盖三类养护需求，明确构造场景与历史记录身份','同时演示成功初筛、数据待确认和无可行候选'])

task('ML-01',4,4,'P0','冻结按方案和材料族的评估划分',['DAT-03','DAT-04'],
     ['两类划分清单','去泄漏核验','评价协议'],
     ['平行试件、疑似汇总和同方案不跨训练测试','材料族按完整证据确认，不以单一通用矿粉曲线合并所有来源','记录每指标实际有效组数，关联不明部分隔离'])
task('ML-02',4,4,'P0','构建设计前特征和标签视图',['ML-01','CAL-01'],
     ['逐指标数据构建器','训练期变换流水线'],
     ['首轮预测只用设计前已知特征','填补、缩放与特征选择在允许训练部分拟合','不将未确认参考属性或生成标签当作实测数据'])
task('ML-03',4,7,'P0','运行近邻与传统模型基准',['ML-02'],
     ['均值、近邻、岭回归和随机森林对照','四指标逐组预测结果'],
     ['相同外层划分下报告MAE、RMSE、R²与阈值误判','调参仅在内层且设计算时间上限','数据不足或目标不满足建模条件时如实形成能力边界报告'])
task('ML-04',4,3,'P1','比较GPR小样本分支',['ML-03'],
     ['固定配置的GPR对照','失败与数值稳定性记录'],
     ['使用同一输入、划分和评价口径','不把GPR后验标准差直接标为已校准工程置信度'],
     condition='核心基准能重跑且剩余工时满足周预算',fallback='保留已完成传统模型，记录未进入的分支')
task('ML-05',4,4,'P0','完成模型选择记录与模型卡',['ML-03'],
     ['逐指标评价报告','模型卡和版本清单'],
     ['区分训练内表现、外层预测与独立料源表现','采用预先声明的模型选择口径，不按演示案例挑模型','没有可靠改进的指标保留案例参考或研究模式'],optional_inputs=['ML-04'])
task('ML-06',4,2,'P0','接入预测服务和能力声明',['ML-05','API-01'],
     ['预测API','模型版本与适用范围输出'],
     ['数值区分历史观测和模型预测','不可用模型、未见产品和不支持指标返回明确状态，不伪造数值'])
task('TST-04',4,2,'P0','核验评估隔离与模型装载',['ML-06','ML-01'],
     ['模型集成与泄漏回归记录'],
     ['更换模型版本能准确显示对应数据和特征版本','部署结果与保存的离线预测在容差内一致，缺失模型时规则流程可运行'])

task('UQ-01',5,6,'P1','开展区间校准与适用性判断',['ML-05','ML-06'],
     ['适用性检查','有数据支持时的区间校准','覆盖与宽度报告'],
     ['校准组独立于训练和调参，目标对应组均值或明确的观测粒度','报告校准组数、覆盖与区间宽度，不将边际覆盖说成联合达标','不足时返回区间不可用及具体原因'],
     condition='有效样本和分组允许相应校准，模型基准通过核验',fallback='保留数值预测的研究状态与历史证据，不填充固定百分比区间')
task('UQ-02',5,4,'P0','统一依据状态与待补测交互',['ML-06','WEB-04'],
     ['有依据核验、待补测、排除状态','模型和规则结果统一展示'],
     ['关键指标缺测、身份不明、区间不可用与阈值冲突分别展示','即使增强区间未实现，仍能完整说明当前证据缺口'],optional_inputs=['UQ-01'])
task('OPT-01',5,6,'P1','实现有边界的局部候选搜索',['UQ-01','CAL-01','REC-01'],
     ['受约束的有限候选搜索','Pareto候选与来源说明'],
     ['只调整已确认质量基准与范围内的少量变量','先核验组成，再评价模型适用性和性能，搜索设置有上限','新候选标为未实测，不用代理自评分证明性能提升'],
     condition='组成口径、训练支持范围与适用性处理已清楚',fallback='维持历史方案枚举、硬筛选和比较，保留搜索接口说明')
task('EXP-01',5,4,'P1','实现下一项试验的规则建议与小池回放',['UQ-02','OBS-01','ML-05'],
     ['方案与试验项目建议','规则与随机的候选池比较'],
     ['建议指出影响的选型歧义与缺测指标','回放只揭示真实历史标签，不使用预测器作为真值','无真实成本时报告查询次数及假设'],
     condition='核心工作台稳定，剩余工时足够',fallback='仅在报告中列出人工可读的待测项目和理由')
task('TST-05',5,3,'P0','核验风险状态和启用的增强功能',['UQ-02'],
     ['阈值、缺测和适用性回归','增强功能开关清单'],
     ['未实现或未满足条件的增强在界面明确不可用','已启用搜索和选试验功能经过相应集成检查','候选为空不自动降低要求'],optional_inputs=['OPT-01','EXP-01'])
task('BIZ-02',5,3,'P2','准备专家评议或独立试验方案',['DEM-01','ML-05'],
     ['专家评议表或预注册试验清单','资源、条件与反馈状态'],
     ['列出有区分力的对照和需要核验的参数','收到评议或实测时单独附证据，未取得时保持计划状态'],
     condition='企业或实验室资源已可用，核心交付不受影响',fallback='保留评议与试验设计，不将等待外部结果列为发布阻塞')

task('TST-06',6,4,'P0','完成发布回归与离线验收',['TST-03','TST-04','TST-05'],
     ['核心用例验收记录','本地性能与离线检查'],
     ['固定环境下五案例、微调、反馈和报告可重跑','网络断开后核心材料与规则流程仍可运行','记录真实响应耗时和故障恢复结果'])
task('PKG-01',6,4,'P0','打包本地演示和启动检查',['TST-06','OUT-01'],
     ['Windows启动与检查脚本','前端静态构建','版本化数据与模型包'],
     ['按交接说明能在目标机器启动，不依赖开发目录绝对路径','核心演示资源本地可用，缺失环境给出可执行提示','发行内容清单与数据和模型版本一致'])
task('DOC-01',6,4,'P0','完成技术与复现交接',['PKG-01','ML-05'],
     ['README与部署说明','字段和接口字典','规则与模型边界说明'],
     ['说明导入、运行、训练、评估和重放所需步骤','每个结论关联对应数据、规则、代码与模型版本'])
task('DEM-02',6,6,'P0','完成答辩材料和演示排练',['DOC-01','DEM-01'],
     ['答辩结构与图表','演示录制与故障备用材料'],
     ['五案例说明完整，实际效果与目标假设区分','核心演示完成两次从启动到结束的排练','记录不能支持的指标与回答口径'])
task('REL-01',6,2,'P0','冻结参赛版本与交接清单',['DEM-02','PKG-01','DOC-01','TST-06'],
     ['版本标签与发行清单','已知问题和验收结论'],
     ['所有P0有验收记录或明确范围调整','功能状态、案例、模型报告和答辩数字一致','保留可回退的上一演示版本'])

capacity = {week:{'planned_hours':26 if week<6 else 20,'buffer_hours':4 if week<6 else 10,'capacity_hours':30} for week in range(1,7)}
by_id = {t['id']:t for t in tasks}
assert len(by_id)==len(tasks)==39
states = {}


def visit(code):
    if states.get(code)=='visiting':
        raise ValueError(f'cycle: {code}')
    if states.get(code)=='done':
        return
    states[code]='visiting'
    for dependency in by_id[code]['dependencies']:
        assert dependency in by_id, (code,dependency)
        assert by_id[dependency]['week']<=by_id[code]['week'],(code,dependency,'week inversion')
        if by_id[code]['priority']=='P0':
            assert by_id[dependency]['priority']=='P0',(code,dependency,'mandatory depends on optional')
        visit(dependency)
    for dependency in by_id[code]['optional_inputs']:
        assert dependency in by_id
        assert by_id[dependency]['week']<=by_id[code]['week']
    states[code]='done'


for t in tasks:
    visit(t['id'])
    assert t['estimate_hours']>0 and t['artifacts'] and t['acceptance']
    assert t['status'] in ['ready','planned']
    if t['priority']!='P0':
        assert t['condition'] and t['fallback']
weekly = Counter()
priorities = Counter()
for t in tasks:
    weekly[t['week']]+=t['estimate_hours']
    priorities[t['priority']]+=t['estimate_hours']
for week in range(1,7):
    assert weekly[week]==capacity[week]['planned_hours']
    assert weekly[week]+capacity[week]['buffer_hours']==30
assert sum(weekly.values())==150
assert sum(c['buffer_hours'] for c in capacity.values())==30
assert priorities=={'P0':128,'P1':19,'P2':3}

milestones = [
    {'id':'M1','week':1,'title':'数据与契约可重建','gate_tasks':['DAT-04','TST-01','BIZ-01']},
    {'id':'M2','week':2,'title':'场景到推荐已打通','gate_tasks':['TST-02']},
    {'id':'M3','week':3,'title':'可比较可反馈可导出的核心版本','gate_tasks':['TST-03','DEM-01']},
    {'id':'M4','week':4,'title':'模型基准与能力边界可核验','gate_tasks':['ML-05','TST-04']},
    {'id':'M5','week':5,'title':'依据状态稳定并冻结增强范围','gate_tasks':['UQ-02','TST-05']},
    {'id':'M6','week':6,'title':'可复现的参赛交付','gate_tasks':['REL-01']},
]
payload = {
    'schema_version':'1.0','project':'数智选材','planning_date':'2026-10-18',
    'source_design_page':'https://chatgpt.com/space/page_b3e90ae7e0a88191967a4234479f66dd',
    'confirmed_constraints':{'developers':1,'weeks':6,'submission_deadline':None},
    'capacity_assumptions':{'working_days_per_week':5,'effective_hours_per_day':6,'total_hours':180,'planned_hours':150,'buffer_hours':30},
    'week_capacity':capacity,'priority_hours':dict(priorities),'milestones':milestones,
    'scheduling_policy':'单一开发者；周内先满足依赖，每天不超过6小时有效任务，最多一个主动开发任务。外部等待不计作开发工时。',
    'scope_policy':'P0核心必须验收；P1和P2为有进入条件的增强，可跳过并保留原因；P0不硬依赖增强。',
    'tasks':tasks,
}
(OUT/'development_backlog_v1.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')

lines=['# 开发任务清单','', '单人六周基准，共39项任务。P0为核心任务，P1为条件增强，P2为外部资源允许时的验证准备。工时合计150小时，另预留30小时缓冲。','']
for week in range(1,7):
    lines += [f'## 第{week}周任务','',f'本周计划{weekly[week]}小时，缓冲{capacity[week]["buffer_hours"]}小时。','',
              '| 编号 | 任务 | 优先级 | 工时 | 依赖 |','|---|---|---|---:|---|']
    for t in tasks:
        if t['week']==week:
            deps='、'.join(t['dependencies']) or '无'
            lines.append(f'| {t["id"]} | {t["title"]} | {t["priority"]} | {t["estimate_hours"]}h | {deps} |')
    lines += ['']
    for t in tasks:
        if t['week']!=week:
            continue
        lines += [f'### {t["id"]} {t["title"]}','', '交付物：'+'、'.join(t['artifacts'])+'。','', '验收：'+'；'.join(t['acceptance'])+'。','']
        if t['optional_inputs']:
            lines += ['可选输入：'+'、'.join(t['optional_inputs'])+'。不作为核心任务的硬依赖。','']
        if t['condition']:
            lines += ['进入条件：'+t['condition']+'。降级方式：'+t['fallback']+'。','']
(OUT/'backlog_detail.md').write_text('\n'.join(lines),encoding='utf-8')

print(json.dumps({'task_count':len(tasks),'planned_hours':sum(weekly.values()),'buffer_hours':30,'priority_hours':dict(priorities),'week_hours':dict(weekly),'dependency_checks':'passed','mandatory_optional_separation':'passed'},ensure_ascii=False,indent=2))
