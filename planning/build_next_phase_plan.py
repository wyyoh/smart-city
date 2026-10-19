"""Build the next-phase plan without modifying the app or earlier acceptance records."""
import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
DATE = '2026-10-19'
TITLE = '数智选材下一阶段亮点开发与验证计划'
PARENT = 'page_2bce917000248191a4e5e29beb90620e'


def write(relative, value):
    (ROOT / relative).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n'
    )


def task(code, week, hours, title, dependencies, requirements, acceptance, artifacts,
         prior=None, highlight=None):
    return {
        'id': code, 'title': title, 'priority': 'core', 'status': 'planned',
        'owner': 'single_developer', 'estimate_hours': hours,
        'start_week': week, 'finish_week': week, 'week_allocations': {str(week): hours},
        'dependencies': dependencies, 'requirements': requirements,
        'prior_alignment_tasks': prior or [], 'highlights': highlight or [],
        'acceptance': acceptance, 'planned_artifacts': artifacts,
        'completion_evidence': [], 'actual_hours': None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-revision', required=True)
    args = parser.parse_args()
    requirements = json.loads((ROOT / 'design/competition_requirements_v2.json').read_text(encoding='utf-8'))
    diagnosis = json.loads((ROOT / 'artifacts/innovation-feasibility-diagnostic.json').read_text(encoding='utf-8'))
    protected = [
        '再生沥青混合料实验数据表.xlsx',
        '第十二届中国研究生智慧城市技术与创意设计大赛企业揭榜技术需求征集表-HY-01 (1).pdf',
        'planning/development_backlog_v1.json', 'planning/plan_manifest.json',
        'planning/v02_alignment_backlog.json', 'design/competition_requirements_v2.json',
        'design/alignment_design_manifest_v2.json', 'artifacts/release-final.json',
        'configs/cases.json', 'artifacts/models/model_cards.json',
    ]
    protected_hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in protected}
    tasks = [
        task('N01', 1, 2, '冻结基线与增量边界', [], ['B04'], [
            '记录0.1.0、原始文件、目录、模型和旧计划指纹；保留旧验收历史。',
            '新流程采用增量契约；验证使用隔离数据库，原始工作簿与正式目录不被改写。',
        ], ['docs/next-phase-baseline.json', 'docs/v2-contract-notes.md']),
        task('N02', 1, 3, '场景与指标契约', ['N01'], ['B01', 'B04', 'T01', 'T10'], [
            '保存工法、层位、结构、气候、交通、病害严重程度、库存和施工限制及出处。',
            '保留已知但暂不支持的PG、疲劳、动态模量需求，区分输入错误与能力不足。',
        ], ['backend/app/domain/contracts_v2.py', 'configs/metric_registry_v2.json'], ['A01']),
        task('N03', 1, 3, '三类可执行需求规则', ['N02'], ['B02', 'T01', 'T02'], [
            '高温、低温、水损害三类规则记录条件、量化目标、优先级、方法、来源与版本。',
            '构造演示与正式项目分开；不同方法条件的阈值不自动合并。',
        ], ['configs/scene_rules_v2.json', 'docs/scene-rule-cards.md'], ['A02'], ['L1']),
        task('N04', 1, 4, '需求解析与确认首条界面', ['N03'], ['B01', 'T01', 'T02', 'T09'], [
            '输入三类场景条件而不手填数值目标，即可看到有来源的需求卡。',
            '工程师覆盖保留原推导值、理由与版本；缺失、冲突和未支持需求可见。',
        ], ['backend/app/decision/demands.py', 'frontend/src/components/DemandCard.tsx',
            'artifacts/next-phase/week1-demand-flow/'], ['A03'], ['L1']),
        task('N05', 2, 4, '材料关系与完整方案卡', ['N02'], ['B01', 'B02', 'T03', 'T04'], [
            '三类场景可查询需求、材料组成、观察和来源的关系路径。',
            '卡片包含产品、级配、用油、RAP、改性剂或助剂与施工字段；未披露项不填0。',
        ], ['backend/app/decision/materials.py', 'frontend/src/components/MaterialSchemeCard.tsx'],
             ['A04', 'A05'], ['L1', 'L2']),
        task('N06', 2, 4, '候选目录检索与范围冻结', ['N04', 'N05'], ['B03', 'T03', 'T04'], [
            '按场景、库存与适用条件检索目录，原9个样例仅保留回归用途。',
            '保存入选、排除、候选ID、数据版本与池哈希；报告明确检索范围。',
        ], ['backend/app/decision/candidate_pool.py', 'artifacts/next-phase/week2-pool/'], ['A06'], ['L1', 'L2']),
        task('N07', 2, 4, '证据适用与工艺检查', ['N05', 'N06'], ['T02', 'T05', 'T10'], [
            '方法、条件、层位与工艺分别标为适用、不适用或未知；明确不兼容可排除。',
            '正式模式中未知条件不自动通过；演示数值比较单独标识。',
            '缺少价格时预算不可判定，保留组成质量基准未确认状态。',
        ], ['backend/app/decision/eligibility.py', 'docs/evidence-applicability-policy.md'], ['A07'], ['L2']),
        task('N08', 3, 3, '四态约束与可行集比较', ['N07'], ['T02', 'T05', 'T08'], [
            '逐目标返回满足、不满足、缺测、不可比，硬要求失败不被综合分补偿。',
            '仅比较同口径已知维度，显示并列与未知偏好维度，排序依据可追溯。',
        ], ['backend/app/decision/constraints.py', 'backend/app/decision/comparison.py'], ['A08'], ['L1', 'L2']),
        task('N09', 3, 4, '最小冲突与无解证书', ['N08'], ['B01', 'B03', 'T08'], [
            '区分池为空、已知冲突、证据不足和场景无效，未知项本身不能证明无解。',
            '返回包含关系下最小的冲突集合及删除任一要求后的候选见证，绑定池和需求版本。',
            'C5数值诊断重现四组冲突；不自动降低正式目标，不把池内冲突解释成物理定律。',
        ], ['backend/app/decision/diagnosis.py', 'frontend/src/components/ConflictPanel.tsx',
            'artifacts/next-phase/conflict-certificates/'], [], ['L1']),
        task('N10', 3, 3, '场景变更与推荐差异解释', ['N09'], ['B01', 'T01', 'T08'], [
            '改变已支持的场景条件，展示规则、目标、候选与结论改变的对应关系。',
            '未改变的条件不制造差异；人工更改与需要工程确认的行动分别记录。',
        ], ['frontend/src/components/DecisionDiff.tsx', 'artifacts/next-phase/week3-what-if/'], [], ['L1']),
        task('N11', 3, 2, '诊断与适用性边界验收', ['N10'], ['B03', 'B04'], [
            '覆盖协议登记的12类负例，核验冲突证书和候选见证。',
            '验证阈值相等、缺测、方法不匹配、并列、空库存及输入变化，避免只验成功路径。',
        ], ['tests/test_decision_diagnosis.py', 'configs/next_phase_negative_cases.json',
            'artifacts/next-phase/week3-acceptance.json'], [], ['L1', 'L2']),
        task('N12', 4, 5, '完整流程与方案比较界面', ['N11'], ['B01', 'T05', 'T09'], [
            '沿用现有工作台贯穿场景、需求确认、生成、对比、微调及验证计划。',
            '同屏查看主要组成、目标余量、排除原因与未知条件，关键判断不藏在次级页面。',
        ], ['frontend/src/components/DecisionWorkflow.tsx', 'artifacts/next-phase/week4-workflow/'], ['A08'], ['L1', 'L2']),
        task('N13', 4, 4, '证据卡与版本失效显示', ['N12'], ['B01', 'T04', 'T05', 'T08'], [
            '方案卡可追到源表源单元格，显示方法、条件、版本和适用状态。',
            '微调后父实测不继承，旧报告可重放，输入更新后旧结果明确失效。',
        ], ['frontend/src/components/CandidateEvidence.tsx', 'artifacts/next-phase/evidence-changes/'], ['A05'], ['L2']),
        task('N14', 4, 3, '研究预测与验证视图', ['N13'], ['B01', 'T07', 'T08'], [
            '分开显示历史实测、各指标自己的离折预测、研究性全量拟合预测与不可用原因。',
            '展示每项模型误差、样本和来源分组、区间边界；现有独立分折不称共享验证。',
            '研究预测不代替历史达标判定，不显示未经验证的联合达标概率。',
        ], ['frontend/src/components/PredictionValidation.tsx', 'artifacts/next-phase/week4-model-view/'], ['A09'], ['L2']),
        task('N15', 5, 3, '可解释的基础补测建议', ['N14'], ['B03', 'T04', 'T07'], [
            '输出候选、试验项目、条件待确认项、建议理由及停止条件。',
            '优先处理影响判断的关键缺项，已知失败不作为有待补齐的可行方案。',
            '基础规则与研究策略明确区分，不预先宣称节约试验或最优试验设计。',
        ], ['backend/app/decision/test_planning.py', 'frontend/src/components/NextTestCard.tsx'], [], ['L3']),
        task('N16', 5, 3, '上游联动与反馈契约', ['N15'], ['B04', 'T06', 'T09'], [
            '本地上游请求携带决策ID、区段和工法，选择结果返回同一决策记录。',
            '实验室与工程反馈分开定义，演示回流与正式记录隔离。',
            '真实企业联调、正式新微调试验训练资格修复及受控再训练仍单独追踪。',
        ], ['scripts/mock_upstream_v2.py', 'docs/feedback-contract-v2.json',
            'artifacts/next-phase/week5-integration/'], ['A11', 'A12'], ['L2', 'L3']),
        task('N17', 5, 6, '五案例同池对照与报告', ['N16'], ['B03', 'T09'], [
            '五案各含场景、需求来源、冻结候选池、完整方案、预期或适用判断与缺项。',
            '保留弱B0与强B1，V2与B1使用相同可见信息；需求已正确给定时允许结论相同。',
            '需求识别、预测误差和推荐验证分开评价，构造案例通过不写成工程准确率。',
        ], ['scripts/compare_cases_v2.py', 'artifacts/next-phase/case-reports/'], ['A10'], ['L1', 'L2', 'L3']),
        task('N18', 6, 2, '完整选材任务价值记录', ['N17'], ['B05'], [
            '对三项代表任务记录人工、B1与V2的完整用时、操作、遗漏与追溯质量。',
            '保留学习顺序和实际参与者信息，单人自测不代表行业平均收益。',
        ], ['artifacts/next-phase/workflow-value.json', 'docs/value-evaluation-notes.md'], ['A13']),
        task('N19', 6, 4, '界面细节与异常恢复打磨', ['N17'], ['B01', 'B04'], [
            '1440×900与1280×720检查需求、方案、冲突及补测卡，关键字段和按钮可操作。',
            '核验加载、空结果、未知、错误、并列、失效、重试和重新打开快照等状态。',
            '主流程可键盘操作，状态同时使用文字，慢响应不覆盖较新输入。',
        ], ['artifacts/next-phase/ui-review/', 'docs/interaction-checklist-v2.md'], [], ['L1', 'L2', 'L3']),
        task('N20', 6, 4, '回归离线检查与发布排练', ['N18', 'N19'], ['B04'], [
            '运行适用的既有检查及新增关键验收，完成前端构建、接口契约与旧流程回归。',
            '隔离库完成两次完整流程排练和本地离线运行检查，保存包指纹与复现步骤。',
            '主流程失败、错误目标、未知当通过、证据错配或旧结果冒充新结果均阻止发布。',
        ], ['artifacts/next-phase/release-checks/', 'artifacts/next-phase/rehearsals/',
            'docs/release-notes-v02.md']),
        task('N21', 6, 2, '亮点叙事与参赛成果核对', ['N20'], ['B01', 'B02', 'B03', 'B04', 'B05'], [
            '五项基本成果逐条挂接可检查证据；三个亮点分别说明机制、演示与验证状态。',
            '准备3分钟核心与8分钟详细排练脚本，时长是练习安排，不当作官方答辩时限。',
            '论文或技术报告、界面与实际能力一致；研究负结果与外部待验证项如实保留。',
        ], ['docs/submission-outline-v2.md', 'docs/demo-script-v2.md',
            'artifacts/next-phase/requirements-acceptance.json'], ['A14'], ['L1', 'L2', 'L3']),
    ]
    research = [
        ('EXP01', '统一实验数据与来源分组', {'1': 5, '2': 3}, ['N01', 'N02'], ['T07', 'X02'],
         ['所有指标共用冻结来源族映射与划分；缺测不造标签，预处理仅拟合训练部分。',
          '冻结训练、校准、池内查询与评价的可见信息，登记参数、种子和运行预算。'],
         ['planning/innovation_validation_plan_v2.json', 'scripts/run_innovation_benchmarks.py',
          'artifacts/next-phase/research/split-manifest.json'],
         '至少有可运行的分组和标签可见性检查；不足时只交付数据资格与限制，不产生性能结论。'),
        ('EXP02', '小样本模型与风险校准对照', {'2': 2, '3': 5, '4': 1}, ['EXP01'], ['T07', 'X02', 'X03'],
         ['均值、近邻、独立模型与一个多任务GP在相同分组与信息条件下比较。',
          '分开评价预测和区间；不将单指标覆盖或小测试集结果升级为联合工程保证。',
          '保存负结果；技术实现未完成与有效实验未提升使用不同状态。'],
         ['artifacts/next-phase/research/model-comparison.json', 'artifacts/next-phase/research/risk-coverage.json'],
         '8小时内优先保证独立强基线；多任务实现或校准不成立时维持研究状态。'),
        ('EXP03', '隐藏标签与目标补测回放', {'4': 4, '5': 5, '6': 1}, ['EXP02', 'N09'], ['T07'],
         ['训练与候选池按来源族隔离；每轮仅揭示实际查询结果，真值仅由评价器访问。',
          '比较随机、优先级且失败即停、训练集失败率排序、最大不确定性与决策价值策略。',
          '记录完成率、查询量、错误证书及预算耗尽；无解、成功、未判定分别统计。',
          '第6周仅整理结果，研究算法与参数于第5周结束前固定。'],
         ['artifacts/next-phase/research/acquisition-traces.json', 'artifacts/next-phase/research/query-budget-results.json'],
         '概率策略没有可信输入或未优于强基线时，保留基础补测卡和完整回放，不宣称效率提升。'),
        ('EXP04', '研究结果复算与展示核对', {'6': 4}, ['EXP03'], ['B03', 'B04'],
         ['按冻结输入复算决策序列与统计，核对全部组数、分母、成本假设和来源。',
          '只把有结果支持的增益写入主叙事，未完成实验不得写成负结果或通过。'],
         ['artifacts/next-phase/research/reproduction-receipt.json', 'docs/research-results-v2.md'],
         '模型或选择策略没有增益时提交可复核的实际结果，核心产品照常按确定性门槛验收。'),
    ]
    for code, title, allocations, dependencies, reqs, acceptance, artifacts, fallback in research:
        weeks = [int(w) for w in allocations]
        tasks.append({
            'id': code, 'title': title, 'priority': 'conditional_research', 'status': 'planned_conditional',
            'owner': 'single_developer', 'estimate_hours': sum(allocations.values()),
            'start_week': min(weeks), 'finish_week': max(weeks), 'week_allocations': allocations,
            'dependencies': dependencies, 'requirements': reqs,
            'prior_alignment_tasks': ['M01'] if code in ['EXP01', 'EXP02'] else [],
            'highlights': ['L2'] if code in ['EXP01', 'EXP02'] else ['L3'],
            'condition': '当周核心验收和必要缓冲已保证，且实际可用时间超过15小时；按依赖顺序开展。',
            'fallback': fallback, 'acceptance': acceptance, 'planned_artifacts': artifacts,
            'completion_evidence': [], 'actual_hours': None,
        })
    milestones = [
        ('G1', 1, '三类场景生成带来源的需求卡', ['N01', 'N02', 'N03', 'N04']),
        ('G2', 2, '材料方案完整且候选范围可重放', ['N05', 'N06', 'N07']),
        ('G3', 3, '无解诊断和场景差异可解释', ['N08', 'N09', 'N10', 'N11']),
        ('G4', 4, '证据适用性进入主操作', ['N12', 'N13', 'N14']),
        ('G5', 5, '五案例和基础验证行动贯通', ['N15', 'N16', 'N17']),
        ('G6', 6, '成果证据与运行包可复核', ['N18', 'N19', 'N20', 'N21']),
    ]
    crosswalk = {
        'A01': {'scheduled': ['N02']}, 'A02': {'scheduled': ['N03']},
        'A03': {'scheduled': ['N04']}, 'A04': {'scheduled': ['N05']},
        'A05': {'scheduled': ['N05', 'N13']}, 'A06': {'scheduled': ['N06']},
        'A07': {'scheduled': ['N07']}, 'A08': {'scheduled': ['N08', 'N12']},
        'A09': {'scheduled': ['N14']}, 'A10': {'scheduled': ['N17']},
        'A11': {'scheduled': ['N16']},
        'A12': {'scheduled': ['N16'], 'deferred': ['正式新微调试验训练资格修复', '受控再训练与模型发布']},
        'A13': {'scheduled': ['N18']}, 'A14': {'scheduled': ['N21']},
        'M01': {'conditional': ['EXP01', 'EXP02']},
        'M02': {'deferred': ['组成质量基准、变量范围、可靠代理和外部评价路径明确后的局部配方探索']},
    }
    plan = {
        'schema_version': '2.1-plan', 'title': TITLE, 'planning_date': DATE,
        'implementation_status': 'plan_ready_implementation_not_started',
        'source_revision': args.source_revision,
        'confirmed_constraints': {'developers': 1, 'weeks': 6, 'hours_per_week_range': [15, 20],
                                  'submission_deadline': None, 'start_date': None},
        'capacity': {'core_planned_hours': 72, 'core_buffer_hours': 18, 'baseline_total_hours': 90,
                     'conditional_research_hours': 30, 'upper_total_hours': 120,
                     'note': '初估工时，不代表实际投入。条件研究使用额外时间，不占用核心缓冲。'},
        'week_capacity': {str(w): {'core_hours': 12, 'buffer_hours': 3, 'baseline_capacity': 15,
                                  'conditional_research_hours': 5, 'upper_capacity': 20} for w in range(1, 7)},
        'work_policy': {'core_wip_limit': 1, 'first_production_feature_freeze': 'end_of_week_5',
                        'week_6': '修复、界面打磨、验收、复算与交付；不新增产品功能。',
                        'research_schedule': '条件研究周分配是每周20小时的上限情景；某周没有额外时间时顺延或裁剪，不挤占核心缓冲。',
                        'overrun': '先使用当周缓冲并停止条件研究；连续两周核心超出15小时则重估剩余范围与工时。'},
        'highlights': [
            {'id': 'L1', 'title': '场景双向推理与无解定位', 'core_scope': '需求解析、最小冲突、候选见证和场景差异解释'},
            {'id': 'L2', 'title': '证据适用性约束的推荐', 'core_scope': '方法工艺检查、四态判断、完整方案、证据与预测边界',
             'conditional_scope': '共享分组模型及风险校准的实证改进'},
            {'id': 'L3', 'title': '面向选材目标的补测', 'core_scope': '结构化且可解释的基础补测建议',
             'conditional_scope': '决策价值策略与强基线的预算回放'},
        ],
        'tasks': tasks,
        'milestones': [{'id': code, 'week': week, 'title': title, 'gate_tasks': gate,
                        'status': 'planned'} for code, week, title, gate in milestones],
        'prior_alignment_crosswalk': crosswalk,
        'supersedes_future_schedule': 'planning/v02_alignment_backlog.json',
        'historical_acceptance_records_preserved': True,
        'requirement_coverage': {
            r['id']: {'task_ids': [t['id'] for t in tasks if r['id'] in t['requirements']],
                      'scope_note': {
                          'T06': '本期接口与反馈契约；现场持续学习及新微调正式训练资格不计已完成。',
                          'X01': '条件不明，阶段外。', 'X02': '条件研究。', 'X03': '研究区间展示与条件验证。',
                          'X04': '保留评估字段与边界，真实核算阶段外。',
                          'X05': '补测计划不等于独立材料试验；真实试验阶段外。',
                          'X06': '本地模拟不等于企业真实联调。', 'X07': '现场持续学习和受控再训练阶段外。',
                      }.get(r['id'], '按本期原型范围验收，完成状态由对应证据决定。')}
            for r in requirements['requirements']
        },
        'source_integrity': protected_hashes,
        'execution': {'completed_core_tasks': 0, 'completed_research_tasks': 0, 'actual_hours': None},
    }
    write('planning/next_phase_backlog_v2.json', plan)
    negative_cases = [
        ('NEG01', '气候或交通缺失', '显示依赖该字段的需求未确定，不填默认地区。'),
        ('NEG02', '病害成因或严重程度不足', '请求补充或保留待确认，不将所有裂缝等同温缩。'),
        ('NEG03', '同指标不同试验方法或条件', '标为不可比，不自动合并成更严阈值。'),
        ('NEG04', 'PG疲劳动态模量需求缺少能力', '保留合法目标，显示未支持；不替换成现有指标。'),
        ('NEG05', '预算存在而价格缺失', '预算不可判定，排序不静默删除其权重。'),
        ('NEG06', '库存范围为空', '说明检索范围无候选，不生成性能冲突证书。'),
        ('NEG07', '必要性能缺测', '待补测，不当已失败，也不据此证明无解。'),
        ('NEG08', '阈值相等及区间边界', '严格与非严格比较保持原定义。'),
        ('NEG09', '候选性能并列', '明确并列，数据库顺序不当作材料优势。'),
        ('NEG10', '微调及输入更新', '父实测与旧请求结果失效，旧报告仍可追溯。'),
        ('NEG11', '演示记录或不匹配模型', '正式模式隔离演示数据，模型不匹配时停止预测。'),
        ('NEG12', '已知复合目标冲突', '给出池内最小冲突及见证，不自动降低硬要求。'),
    ]
    protocol = {
        'material_passport': {'origin_skill': 'academic-research-suite experiment-agent', 'origin_mode': 'plan',
                              'origin_date': DATE, 'verification_status': 'UNVERIFIED', 'version_label': 'innovation_validation_v2'},
        'status': 'proposed_protocol_not_executed',
        'scope': '核心确定性验收与条件研究分别记录；团队门槛不当作官方评分标准。',
        'inputs': ['design/competition_alignment_evidence_v2.json', 'artifacts/innovation-feasibility-diagnostic.json',
                   'configs/cases.json', 'artifacts/models/model_cards.json'],
        'known_data_limits': {'historical_operational_keys': 180, 'four_metric_numeric_present': 60,
                              'ac13_complete_numeric_pool': 35,
                              'common_model_eligible_operational_keys': diagnosis['common_model_eligible_recipe_ids'],
                              'independent_physical_sources_confirmed': False,
                              'note': '缺测与训练资格不同；操作键、标签行及来源族均不自动等于独立物理样本。'},
        'entry_point': {'status': 'to_be_implemented_by_EXP01', 'proposed_path': 'scripts/run_innovation_benchmarks.py',
                        'runnable_entry_command': None},
        'negative_cases': [{'id': i, 'trigger': t, 'expected': e} for i, t, e in negative_cases],
        'evaluations': [
            {'id': 'H1', 'task_ids': ['N04', 'N09', 'N10', 'N11', 'N17'],
             'hypothesis': '需求及证据状态进入推理后，可以给出可复核的目标、候选及无解原因。',
             'type': 'deterministic_engineering_acceptance',
             'comparators': ['B0预先登记单指标方法，仅作风险示例', 'B1现有全约束加单优先级，必须保留', 'V2同池同信息方法'],
             'metrics': ['需求来源与规则匹配', '冲突证书有效性及删除要求后的候选见证',
                         '未知或不可比处理', '场景差异解释完整性', '同信息完整任务操作与用时'],
             'acceptance': '全部登记确定性样例通过，证书在其声明范围内成立；不把软件通过率当工程准确率。',
             'existing_diagnostic': {'case': 'C5', 'single_target_counts': diagnosis['single_requirement_candidate_counts'],
                                     'minimal_conflicts': [x['requirements'] for x in diagnosis['minimal_infeasible_requirement_sets']]},
             'business_correctness_dependency': '规则工程适用性由对应条款或企业项目确认支持，演示规则始终标记构造。'},
            {'id': 'H2', 'task_ids': ['EXP01', 'EXP02', 'EXP04'],
             'hypothesis': '适用性与区间判断能否在相近可判定覆盖下减少阈值错误推荐，需分组验证。',
             'type': 'grouped_model_and_decision_comparison',
             'predictors': ['dummy', 'nearest', 'ridge', 'random_forest', 'independent_gpr', 'one_multitask_gp'],
             'representation_rule': '只用设计前可信组成、产品与级配输入；补测任务允许已揭示试验输入但单列任务。',
             'split': {'global_source_profile_mapping': '所有指标共用，先按来源族和重复材料曲线冻结。',
                       'prediction_track': '5折外层来源分组、训练部分内3折选择；各方法同划分，缺测用掩码。',
                       'interval_track': '另固定全局12校准组和8测试组，其余训练；实际每指标可用组数分别报告。',
                       'insufficient_calibration': '有限样本分位数无法形成有用区间时返回不可用或无界，不删去困难测试。',
                       'shared_validation_note': '旧模型每指标独立分折只作既有证据，不称本轮共享划分。'},
             'model_budget': {'independent_candidate_pipelines_max': 9, 'multitask_families_max': 1,
                              'timeout_per_fit_seconds': 120, 'total_experiment_wall_time_cap_seconds': 7200,
                              'manual_work_timebox_hours': 8},
             'primary_metrics': ['相近覆盖下错误推荐率差', '每指标MAE/RMSE/R2', '区间覆盖及宽度', '来源组表现'],
             'fair_information': '点预测与区间策略使用相同可见标签；全实测B1只作已知信息参照，不与未知目标预测作不公平胜负比较。',
             'reporting': '列出全部可评价分母、缺测与拒答；以来源族汇总差值和区间，重复种子不增加独立样本数。',
             'claim_gate': '只有分组差值支持改善且覆盖下降不超过预先登记的5个百分点，才声明该范围内稳定改善；否则记录趋势或负结果。',
             'publication_gate': '本阶段模型均保持研究用途；单指标覆盖不当多指标联合保证。'},
            {'id': 'H3', 'task_ids': ['EXP01', 'EXP02', 'EXP03', 'EXP04'],
             'hypothesis': '按预计决策价值选择方案与试验项目，能否比强顺序策略更快完成选材判断。',
             'type': 'historical_hidden_label_replay',
             'pool': '具有可评价真值的冻结候选子集；来源族与模型训练隔离，实际池大小逐次报告。',
             'visible_state': '候选设计前信息、场景需求、允许训练数据及已查询结果；池内初始目标标签为空。',
             'truth_access': '只由独立评价器揭示所查询的一项历史标签；策略不能读取完整真值或含池标签的全量拟合模型。',
             'action': ['recipe_version', 'metric', 'test_condition_status'],
             'strategies': ['uniform_random', 'scene_priority_fail_fast', 'train_failure_rate_fail_fast',
                            'maximum_uncertainty', 'proposed_decision_value_per_incremental_cost'],
             'repeats': {'seeds': list(range(20)), 'label_query_budgets': [4, 8, 16],
                         'note': '同种子同初始信息与预算，种子重复是算法稳定性重复，不是新材料样本。'},
             'stopping': {'feasible_found': '一个候选所有必要指标有已揭示可比结果且全部满足。',
                          'pool_infeasible_certified': '每个候选至少有一项已揭示的必要指标不满足。',
                          'unresolved': '预算耗尽、条件不可比或证据不足；不当成失败证书。'},
             'cost_policy': '首先按标量标签查询数计费；成本向量仅作标明假设的敏感性分析。共用制样须有依据才计算共享成本。',
             'primary_metrics': ['预算到决策完成率曲线', '同完成率下查询量', '首次证实可行或池内无解的查询量',
                                 '错误证书数量', '未判定比例'],
             'claim_gate': '必须与表现最好的强顺序或不确定性基线比较；实际查询收益和来源组差值支持时才声明该池内提升。',
             'limits': '不将回放查询数换算成真实试验次数或经费；新配方、现场收益另需实测。'},
        ],
        'monitoring': {'progress_path': 'artifacts/next-phase/research/progress.json',
                       'per_fit_timeout_seconds': 120, 'total_wall_time_cap_seconds': 7200,
                       'on_failure': '保存具体失败和已有结果，由开发者诊断；不自动反复重试或扩大预算。'},
        'numerical_reproducibility': '冻结输入、划分、版本和种子；同环境决策序列与计数应一致，数值容差于首轮运行清单登记。',
        'research_statuses': ['planned', 'not_started_capacity', 'implementation_incomplete', 'invalid_protocol',
                              'executed_no_improvement', 'executed_improvement_with_scope'],
    }
    write('planning/innovation_validation_plan_v2.json', protocol)

    blocks = []
    def add(value):
        blocks.append(value.strip())
    add('下一阶段用六周把场景双向推理、证据适用性推荐和补测建议形成可演示、可解释、可验证的作品。单人每周投入15至20小时；主线按每周15小时安排，模型与主动补测研究只使用额外时间。')
    add('阶段成果是一个贯穿养护场景、性能需求、完整材料方案、比较解释与验证行动的原型，以及至少三类场景、五个带对照案例和可复核的参赛材料。两个主亮点完成产品闭环，第三个亮点先完成基础补测流程，有额外时间再验证高级策略。')
    add('# 1 本阶段范围与当前起点')
    add('0.1.0已具备数据导入、历史筛选、追溯、微调、审核、研究模型和运行包。本期沿用这些基础，新增需求解析、候选池生成、证据适用性、冲突定位与主流程表达。旧软件验收保持原记录，下一阶段任务全部从待开发开始。')
    add('正式目录有180个历史操作配方键，60个四性能数值齐全，AC-13诊断子集为35个。现有模型按指标使用72至85个有效键、35至37个来源族，外层MAE均未优于均值。操作键和来源族并非已确认的独立物理批次，这一范围决定本期验证结论。')
    add('排期从实际开工日计算，尚未确定提交截止日。此前68小时是基础对齐估算；本计划重新组织未来工作，核心72小时另留18小时缓冲，两者不与旧估算重复相加。')
    add('# 2 三个亮点的交付标准')
    add('| 亮点 | 15小时每周的核心交付 | 额外时间开展的研究 | 演示证据 |\n|---|---|---|---|\n| 场景双向推理与无解定位 | 自动需求卡、最小冲突、候选见证、场景差异解释 | 保留后续规则和适用场景扩展 | 改变条件后展示目标及候选变化，复现C5冲突 |\n| 证据适用性约束的推荐 | 组成与工艺检查、四态判断、来源证据、版本失效、研究预测边界 | 共享来源分组模型与风险校准对照 | 候选落选、待验证与微调失效均能解释 |\n| 面向选材目标的补测 | 方案与项目建议、理由、条件缺项和停止条件 | 隐藏标签回放与决策价值策略 | 展示下一步验证行动；研究收益单独给对照 |')
    add('第一个亮点中，“最小”指删除集合中任一要求后，该子集就有候选，不表示所有冲突只有一个。C5当前数值诊断的四个单项候选数为2、2、4、9，合取为空，已发现四组两项冲突。本期把这项诊断接入界面、版本和报告；未知数据不能充当无解证明，系统不自动降低正式目标。')
    add('第二个亮点让证据适用性实际影响判断：明确不兼容时排除，缺测或方法不匹配时保留待验证，候选改变后父证据失效。完整方案卡展示沥青产品、级配与组分、用油、RAP及基准、改性剂或助剂、工艺条件。产品未披露的信息保持未知。')
    add('第三个亮点先交付可执行的建议卡。基础规则解决需要补什么和为什么；高级策略再检验选择哪项最有决策价值。现有选试验回放尚未证明效率改进，因此研究实验必须包含“按优先级检测、失败即停”等强基线。')
    add('# 3 工时与六周里程碑')
    add('| 周次 | 核心目标 | 核心加缓冲 | 当周验收 |\n|---|---|---|---|\n' + '\n'.join(
        f'| 第{w}周 | {milestones[w-1][2]} | 12小时加3小时 | {", ".join(milestones[w-1][3])} |' for w in range(1, 7)))
    add('每周安排四个约3小时的核心工作块和一个3小时缓冲块，一次只推进一个核心任务。六周核心72小时、缓冲18小时，共90小时。每周实际能达到20小时时，额外5小时按研究依赖使用，总研究上限30小时；缓冲不预先分给研究。')
    themes = {
        1: '先让场景到需求真正发生在主界面。',
        2: '让候选来自完整目录，并能看到材料组成与适用条件。',
        3: '完成最有辨识度的诊断机制，负例与证书一并验收。',
        4: '把证据、预期性能、对比与微调收进同一条操作流程。',
        5: '贯通基础验证行动、上游接口和五案例报告。',
        6: '停止新增产品功能，集中修复、打磨、核验和排练。',
    }
    for week in range(1, 7):
        add(f'## 第{week}周任务')
        add(themes[week])
        rows = [t for t in tasks if t['priority'] == 'core' and t['finish_week'] == week]
        add('| 任务 | 内容 | 工时 | 核心验收 |\n|---|---|---:|---|\n' + '\n'.join(
            f'| {t["id"]} | {t["title"]} | {t["estimate_hours"]}小时 | {t["acceptance"][0]} |' for t in rows))
    add('# 4 条件研究的时间分配')
    add('| 任务 | 工作 | 工时 | 周分配 |\n|---|---|---:|---|\n' + '\n'.join(
        f'| {t["id"]} | {t["title"]} | {t["estimate_hours"]}小时 | ' + '，'.join(f'第{w}周{h}小时' for w, h in t['week_allocations'].items()) + ' |'
        for t in tasks if t['priority'] == 'conditional_research'))
    add('研究顺序为统一数据与分组、模型及校准、主动补测回放、复算核对。额外工时累计约8小时可完成实验数据层，16小时完成模型对照时间盒，26小时完成补测回放时间盒，30小时完成复算与展示。实现未完成、协议无效、有效实验未提升和有效实验有提升分别登记；任务花完时间不代表实验完成。')
    add('条件研究表按每周20小时的上限情景列示。某周没有额外时间时，研究按依赖顺延或裁剪，不挤占核心缓冲；若每周只有15小时，四项研究保持未启动。第5周末固定研究策略与参数，第6周只整理、复算和呈现结果。')
    add('# 5 依赖与模块衔接')
    add('```mermaid\nflowchart TD\n    A[场景与需求规则] --> B[需求解析与确认]\n    B --> C[完整方案与候选范围]\n    C --> D[证据适用与四态约束]\n    D --> E[最小冲突与差异解释]\n    E --> F[比较 微调 与验证行动]\n    F --> G[五案例和发布验收]\n    H[统一实验分组] -.-> I[模型及校准对照]\n    I -.-> J[主动补测回放]\n    J -.-> K[研究结果复算]\n```')
    add('后端拟新增decision目录，将需求、材料检索、适用性、约束、诊断和补测服务分开；沿用FastAPI、SQLite和既有观察流程。前端优先增加需求卡、方案证据、冲突面板及补测卡，复用现有工作台。配置、接口和模块路径均为拟实施位置，不代表现在可调用。')
    add('核心任务没有条件研究的硬依赖。现有模型结果可在主流程显示研究状态，即使新模型没有提升，也不阻塞历史证据推荐与诊断。规则、候选池、方案、模型和报告版本共同进入新快照；旧运行包和旧报告继续可重放。')
    add('# 6 三项验证如何产生证据')
    add('| 验证 | 比较对象 | 主要结果 | 主张门槛 |\n|---|---|---|---|\n| 需求与双向诊断 | 弱B0、强B1、同池同信息V2 | 需求来源、证书、未知处理、完整任务操作 | 登记确定性样例通过，规则适用有依据 |\n| 模型与风险判断 | 均值、近邻、独立模型、一个多任务GP；点预测与区间策略 | 每指标误差、相近覆盖下错误推荐、覆盖与宽度 | 来源分组差值支持改善后才声明稳定提升 |\n| 目标补测 | 随机、优先级失败即停、训练失败率、不确定性、决策价值策略 | 预算到完成率、同完成率查询量、错误证书、未判定 | 与最强基线比较，结果支持才声明池内收益 |')
    add('模型预测采用所有指标共用的来源族划分，外层分组评价，调参和预处理只接触训练数据。区间另用固定训练、校准、测试分组，实际每指标可用组数分别披露；校准不足时保留不可用或宽区间。当前独立模型的既有折分不包装为共同验证，多指标联合工程保证不在本期承诺范围内。')
    add('补测回放隐藏池内全部目标标签，策略只读取设计前信息、允许训练数据和已经查询的结果。按20个固定种子及4、8、16个标量查询预算比较；种子重复只反映算法稳定性，不增加独立材料数量。成功须有一个候选的全部必要结果，证实池内无解须每个候选至少存在一项已揭示失败；预算耗尽保持未判定。')
    add('没有实际成本时先比较查询数，并将成本向量作为明确假设的敏感性分析。历史查询数不直接换算成真实试验次数、费用或研发周期。实验命令在实现和检查后登记，当前协议中的拟议脚本不能当作现有入口。')
    add('# 7 五案例与十二类负例')
    add('| 案例 | 重点 | 必须呈现 |\n|---|---|---|\n| 高温重载车辙 | 场景到抗车辙要求 | 需求依据、全候选范围及其他必要性能 |\n| 寒冷温缩开裂 | 病害与低温要求 | 裂缝成因、并列候选与适用条件 |\n| 水损害 | 两项水稳定需求 | TSR与残留比各自作用及落选原因 |\n| 高RAP选材 | 资源目标与性能共同约束 | RAP名义比例、计量基准与待核验项 |\n| 复合高要求 | 冲突与无解 | 最小冲突、候选见证和后续行动 |')
    add('每案报告固定记录输入来源、规则与需求、材料方案、冻结候选池、方法对照、性能预期或适用判断、未知项、微调及验证建议。需求已完整正确输入时，V2可以与B1推荐一致；改进应从需求识别、条件检查、解释和任务效率中如实体现。')
    add('十二类负例包括气候交通缺失、病害信息不足、试验口径冲突、已知指标未支持、预算缺价格、空库存、性能缺测、阈值边界、并列、版本失效、演示隔离或模型不匹配、复合目标冲突。具体触发和期望状态保存在实验协议，全部在产品接入后验收。')
    add('# 8 把亮点做精的质量要求')
    add('每个亮点同时交付可运行服务、可操作界面、可理解解释、边界样例和可重放证据。需求卡能追来源；方案卡能看完整组成；冲突面板能证明原因；补测卡能说明下一步行动。数据缺失、条件未知与性能失败始终用不同文字表达。')
    add('第6周在1440×900与1280×720检查主界面，覆盖加载、空结果、错误、并列、待验证、失效与恢复；主流程可键盘操作，关键状态不只依靠颜色。两次完整排练均使用隔离数据库，包含一次场景变化、一次无解解释、一次微调失效和一次基础验证行动。')
    add('主流程失败、目标推导错误、未知被认定通过、证据关联错误、输入变化后旧结果冒充新结果，均属于发布阻断问题。适用的旧检查、新增关键断言、前端构建、离线运行及报告重放通过后才形成候选发布包。新电脑重装或实际企业联调只有完成后才登记。')
    add('# 9 外部条件和阶段外工作')
    add('| 工作 | 本期处理 | 进入后续实施的条件 |\n|---|---|---|\n| 正式场景阈值与施工规则 | 三类构造演示和有出处参考，保留确认状态 | 企业或项目确认适用条款及条件 |\n| 连续配方优化 | 保留字段和路线 | 组成质量基准、允许变量、可靠代理与外部评价明确 |\n| 新微调正式试验进入训练与模型发布 | 继续登记缺口，本期反馈契约不代表已实现训练更新 | 补齐资格判断、固定保留验证和回退机制后另估工时 |\n| 现场持续学习与真实接口联调 | 本地契约和模拟回流 | 企业样例、可用系统及授权明确 |\n| 成本碳排寿命和独立材料试验 | 准备数据需求与验证方案 | 价格、边界、因子、试验或服役资料到位 |')
    add('外部资料未到位时核心原型继续运行。取得真实资料后先评估影响、版本和新增工时，再决定纳入当前周或下一阶段；不让外部等待占满单人开发窗口。外部联系和试验执行按实际授权开展。')
    add('# 10 开工顺序与每周控制')
    add('| 首周工作块 | 内容 | 可检查输出 |\n|---|---|---|\n| 第一个3小时 | 冻结基线2小时，场景契约起步1小时 | 基线清单、v2输入字段与边界 |\n| 第二个3小时 | 完成契约2小时，规则起步1小时 | 三类输入和指标能力状态样例 |\n| 第三个3小时 | 完成规则2小时，解析起步1小时 | 规则来源、适用条件与解析结果 |\n| 第四个3小时 | 完成解析及确认界面3小时 | 三类场景的首条可操作链路 |\n| 缓冲3小时 | 修复或补充验收 | 周验收通过及真实用时记录 |')
    add('每周末只核对本周里程碑、实际工时、剩余问题和下一周依赖。发生超时先停止条件研究、使用缓冲；连续两周核心实际需求超过15小时，重估剩余工时和范围。保留规则、证据、冲突及关键异常验收，优先压缩高级模型、动态效果和扩展场景。')
    add('# 11 追踪与交付')
    add('机器任务清单含21项核心任务和4项条件研究，每项记录依赖、工时、验收、预期产物和完成证据。任务只有在产物、适用检查和实际演示证据齐备后才更新完成；当前全部待开发，预期产物路径并不表示文件已存在。')
    add('本期未来排程以next_phase_backlog_v2.json为准，innovation_validation_plan_v2.json保存实验协议，next_phase_plan_v2.md保存可读计划。旧v0.1完成记录和旧对齐清单保持原样；交叉表标明承接、条件研究和延期部分，避免旧68小时与本期预算重复计算。')
    add('设计依据为[赛题对齐与深化设计](https://chatgpt.com/space/page_2bce917000248191a4e5e29beb90620e)、逐项赛题矩阵、0.1.0交接说明和当前诊断。五项基本成果最终通过技术方案及原型、三类结构化场景、五案例对照、可复用交接和应用价值记录逐条验收。')
    assert len(blocks) <= 95, len(blocks)
    doc_path = ROOT / 'planning/next_phase_plan_v2.md'
    doc_path.write_text('# ' + TITLE + '\n\n' + '\n\n'.join(blocks) + '\n', encoding='utf-8', newline='\n')
    write('planning/next_phase_page_blocks_v2.json', {'title': TITLE, 'blocks': blocks})
    manifest_path = ROOT / 'planning/next_phase_manifest_v2.json'
    previous = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    manifest = {
        'title': TITLE, 'planning_date': DATE, 'status': 'plan_ready_implementation_not_started',
        'parent_page_id': PARENT, 'idempotency_key': previous.get('idempotency_key') or str(uuid4()),
        'local_document': str(doc_path), 'document_sha256': hashlib.sha256(doc_path.read_bytes()).hexdigest(),
        'page_id': previous.get('page_id'), 'page_url': previous.get('page_url'),
        'page_synced_document_sha256': previous.get('page_synced_document_sha256'),
        'page_layout_preview': 'not_inspected', 'page_blocks': len(blocks),
        'backlog_file': 'planning/next_phase_backlog_v2.json',
        'experiment_protocol': 'planning/innovation_validation_plan_v2.json',
        'core_tasks': 21, 'conditional_research_tasks': 4,
        'core_hours': 72, 'buffer_hours': 18, 'conditional_research_hours': 30,
    }
    write('planning/next_phase_manifest_v2.json', manifest)
    print(json.dumps({'core_tasks': 21, 'research_tasks': 4, 'core_hours': 72, 'buffer_hours': 18,
                      'conditional_hours': 30, 'page_blocks': len(blocks),
                      'plan_characters': len(doc_path.read_text(encoding='utf-8'))}, ensure_ascii=False))


if __name__ == '__main__':
    main()
