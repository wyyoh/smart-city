"""Explicit competition coverage and verifiable file references, without a readiness score."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'configs/review_evidence_v3.json'

# Each statement describes the implementation's actual scope, not official acceptance.
COVERAGE = {
    'B01': ('prototype', '核心操作流程可演示', '场景、需求确认、候选比较、依据和验证行动贯通；工程应用尚需外部核验。', ['backend/app/decision/demands.py', 'frontend/src/components/DecisionWorkflow.tsx', 'backend/app/review/assessment.py', 'docs/technical-report-v02.md']),
    'B02': ('constructed', '三类构造场景已覆盖', '高温、低温、水损害规则与材料证据关联；量化阈值未经真实区域核定。', ['configs/scene_rules_v2.json', 'backend/app/decision/materials.py']),
    'B03': ('software_verified', '五案同池软件对照', 'B1与V2的数值可行集一致；C5区分84条含缺测目录和35条完整数值子池。', ['artifacts/next-phase/case-reports/summary.json', 'artifacts/next-phase/conflict-certificates/C5.json', 'scripts/compare_cases_v2.py', 'artifacts/review-phase/verification/cases.json']),
    'B04': ('prototype', '数据契约与交接可复用', '代码、规则、字段、接口和运行包已提供；新主机需安装依赖。', ['docs/api-v3.openapi.json', 'docs/feedback-contract-v2.json', 'README.md', 'docs/external-validation-schema-v3.json']),
    'B05': ('partial', '潜在价值可分析，真人收益待验证', '三任务九流程AI代理记录可复核；没有真人节时、成本、碳排或寿命收益数据。', ['artifacts/next-phase/workflow-value.json', 'docs/value-evaluation-notes.md', 'artifacts/next-phase/human-validation-scope-confirmation.json']),
    'T01': ('constructed', '场景映射可执行', '映射使用团队构造的量化要求。正式项目应另提供有出处的目标和适用条件。', ['configs/scene_rules_v2.json', 'backend/app/decision/rules.py']),
    'T02': ('partial', '硬约束与优先级可查', '硬失败不补偿，支持优先序、并列与Pareto比较；未知价格、碳排和供货不判为通过。', ['backend/app/decision/comparison.py', 'backend/app/decision/eligibility.py']),
    'T03': ('prototype', '关系路径可查询', '场景、要求、材料版本、观察和来源建立显式关系；未披露组成保持未知。', ['backend/app/decision/materials.py']),
    'T04': ('partial', '历史材料检索与微调', '支持有限历史目录推荐、完整材料字段和微调失效；自动新配方优化未启用。', ['backend/app/decision/candidate_pool.py', 'backend/app/decision/materials.py', 'configs/features.json']),
    'T05': ('partial', '性能与适用性比较', '同界面比较已知性能、工艺和未知项；无成本、碳排与寿命数据时不绘制伪数值。', ['frontend/src/components/MaterialSchemeCard.tsx', 'frontend/src/components/CandidateEvidence.tsx']),
    'T06': ('partial', '反馈契约与范围隔离', '实验室与现场反馈分开，审核和新决策联动；尚无真实路用监测和持续学习实证。', ['backend/app/decision/integration.py', 'docs/feedback-contract-v2.json']),
    'T07': ('research_only', '独立模型研究已有结果', '现有四项独立模型外层MAE均未优于均值基线；多性能协同预测与环境泛化尚未验证。', ['artifacts/models/model_cards.json', 'backend/app/decision/model_view.py']),
    'T08': ('partial', '规则及证据解释可核查', '可解释要求、适用性、冲突和模型研究边界；未据特征关联宣称材料因果影响。', ['backend/app/decision/diagnosis.py', 'frontend/src/components/PredictionValidation.tsx']),
    'T09': ('prototype', '模块接口可本地模拟', '上游决策ID、区段与材料返回值绑定；企业真实系统联调待开展。', ['backend/app/decision/integration.py', 'scripts/mock_upstream_v2.py']),
    'T10': ('partial', '施工适用性检查', '比较工法、层位、结构、设备和施工窗口；缺少条件时保留未知，未进行材料工艺联合优化。', ['backend/app/decision/eligibility.py', 'docs/evidence-applicability-policy.md']),
    'X01': ('deferred', '自动配方优化延后', 'RAP质量基准和可靠代理尚不足，自动优化关闭。', ['configs/features.json']),
    'X02': ('deferred', '协同预测研究延后', '四个独立模型不作为多任务协同预测成果。', ['artifacts/models/model_cards.json']),
    'X03': ('research_only', '单指标研究区间', '现有分组校准结果不构成多指标联合达标概率或工程保证。', ['artifacts/models/model_cards.json']),
    'X04': ('pending_external', '成本碳排寿命待数据', '需要统一计量边界、价格、因子和服役资料。', ['docs/enterprise-questions.md']),
    'X05': ('pending_external', '独立材料试验待开展', '历史工作簿记录和软件回放不作为新增独立试验。', ['docs/enterprise-questions.md']),
    'X06': ('pending_external', '企业真实联调待开展', '本地模拟只验证契约与软件流程。', ['scripts/mock_upstream_v2.py']),
    'X07': ('deferred', '受控持续学习待开展', '审核反馈不自动赋予训练资格，不自动再训练或发布模型。', ['backend/app/decision/integration.py']),
}

SOURCES = [
    {'id': 'mot-5521-2019', 'title': '公路沥青路面再生技术规范发布公告',
     'standard': 'JTG/T 5521—2019', 'authority': '交通运输部', 'type': '推荐性行业标准发布公告',
     'notice_date': '2019-08-21', 'page_publication_date': '2019-08-29', 'effective_date': '2019-11-01',
     'replaces': 'JTG F41—2008',
     'url': 'https://xxgk.mot.gov.cn/jigou/glj/202006/t20200623_3313172.html',
     'verified_on': '2026-10-19', 'verification_scope': '核对官方发布公告中的名称、性质、施行日期和替代关系；项目适用及具体条款另行核定。',
     'thresholds_authorized': False},
    {'id': 'mot-3410-2025', 'title': '公路工程沥青及沥青混合料试验规程发布公告',
     'standard': 'JTG 3410—2025', 'authority': '交通运输部', 'type': '强制性行业标准发布公告',
     'notice_date': '2025-06-13', 'page_publication_date': '2025-08-22', 'effective_date': '2025-10-01',
     'replaces': 'JTG E20—2011',
     'url': 'https://xxgk.mot.gov.cn/jigou/glj/202508/t20250822_4175218.html',
     'verified_on': '2026-10-19', 'verification_scope': '核对官方发布公告；不据新规程倒填历史试验方法、条件或日期。',
     'thresholds_authorized': False},
]

HIGHLIGHTS = [
    {'id': 'conflict', 'title': '要求冲突有范围、有见证', 'question': '为什么当前没有候选，先复核哪项要求？', 'case_id': 'C5',
     'mechanism': '四态硬约束、冻结候选池、最小冲突与删除见证。',
     'steps': ['先看含缺测的完整目录：证据不足。', '明确切换完整数值子池：检查四组冲突。', '展开删除任一要求后的候选见证和原值。'],
     'boundary': '结论只对声明的需求与候选池成立；最小冲突算法本身不作为原创数学方法。'},
    {'id': 'evidence', 'title': '材料方案沿证据追到原值', 'question': '为什么能比较，哪里还不能用于工程？', 'case_id': 'C1',
     'mechanism': '完整材料、方法条件、原单元格与材料版本共同约束比较。',
     'steps': ['查看数值满足候选的材料组成与未披露项。', '从性能证据追到来源表格和单元格。', '检查复核单中的方法、条件和身份缺口。'],
     'boundary': '已知数值满足与工程适用分别检查；未披露改性剂不推断为零。'},
    {'id': 'validation', 'title': '把未知变成下一步核验行动', 'question': '还差什么证据，下一步做哪项验证？', 'case_id': 'C2',
     'mechanism': '候选、项目、条件、理由、停止规则绑定同一次决策。',
     'steps': ['查看待核验候选及基础验证卡。', '微调组成后重新检索，检查父实测失效。', '导出复核单并下载真实核验模板。'],
     'boundary': '当前为规则型基础建议，高级主动补测和真实节约收益尚未验证。'},
]

QUESTIONS = [
    ('符合赛题哪一项核心要求？', '对应企业课题一的场景到材料推荐核心流程，覆盖三类结构化场景与五个基准对照案例。详细技术要求和加分项各自标注交付范围。', ['B01', 'B02', 'B03']),
    ('创新点在哪，是否只是筛表？', '新增价值在要求来源、适用性、范围内冲突与下一步验证的贯通。需求正确给定时，强B1与V2数值可行集一致，未声称筛选准确率提升。', ['T01', 'T03', 'T08']),
    ('阈值来自规范吗？', '基础参考来自企业工作簿，强化阈值来自明确的团队构造假设。官方公告只登记标准版本；正式项目需要适用条款和批准依据。', ['T01']),
    ('为什么84条没有冲突证书，35条却有？', '完整目录包含缺测，不能以未知证明无解。35条是明确选择的完整数值演示子池，只在该范围验证四组包含最小冲突。', ['B03', 'T08']),
    ('AI模型效果怎样？', '四项现有模型外层MAE都未优于均值基线，保留研究展示。当前硬约束结论由记录证据与规则产生，预测不替代实测。', ['T07', 'X02', 'X03']),
    ('能设计任意新配方吗？', '支持历史目录选材与创建待试验微调版本；新版本不继承父实测。RAP质量基准及可靠代理不足，自动新配方优化延后。', ['T04', 'X01']),
    ('节省多少时间、成本或碳排？', '目前完成AI软件自测，真人用时、价格、碳排及寿命收益待真实数据验证。可核查的是流程审计与未知处理，不能从API时延推算人工节时。', ['B05', 'X04']),
    ('企业能继续使用哪些成果？', '可交接数据结构、规则、接口、代码、模型档案与复现包；需要继续确认材料身份、试验口径、真实需求和企业系统接口。', ['B04', 'T09', 'X06']),
]


def build():
    original = json.loads((ROOT / 'design/competition_requirements_v2.json').read_text(encoding='utf-8'))
    references = {}
    rows = []
    for item in original['requirements']:
        state, label, scope, paths = COVERAGE[item['id']]
        keys = []
        for name in paths:
            key = 'ev_' + hashlib.sha256(name.encode()).hexdigest()[:14]
            path = ROOT / name
            references[key] = {'id': key, 'path': name, 'label': path.name,
                               'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            keys.append(key)
        rows.append({k: item[k] for k in ['id', 'kind', 'source_page', 'title', 'requirement_paraphrase']} |
                    {'status': state, 'status_label': label, 'delivered_scope': scope, 'evidence_ids': keys})
    pdf = next(ROOT.glob('*.pdf'))
    data = {'schema_version': '3.0', 'generated_at': datetime.now(timezone.utc).isoformat(),
            'title': '数智选材成果与证据', 'topic': '企业课题一', 'official_scoring_weights': None,
            'competition_source': {'file': pdf.name, 'sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(),
                                   'topic_pages': [1, 2, 3, 4, 5], 'core_deliverables_page': 4},
            'requirements': rows, 'evidence': references, 'sources': SOURCES, 'highlights': HIGHLIGHTS,
            'questions': [{'question': q, 'answer': a, 'requirement_ids': ids} for q, a, ids in QUESTIONS],
            'scope_note': '状态为团队对本地原型的证据登记，不代表官方评分、专家认可或工程批准。',
            'external_pending': ['真实场景与阈值适用确认', '材料身份和RAP质量基准', '独立材料与现场试验', '真人完整任务测时', '企业真实接口联调'],
            'human_participants': 0, 'actual_human_hours': None, 'conditional_research': 'deferred'}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'requirements': len(rows), 'evidence_files': len(references), 'output': OUT.relative_to(ROOT).as_posix()}))


if __name__ == '__main__':
    build()
