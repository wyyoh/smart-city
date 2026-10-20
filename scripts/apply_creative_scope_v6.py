"""Apply the user's creative-submission scope without changing material evidence."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT/'configs/creative_scope_v6.json'
REGISTRY = ROOT/'configs/review_evidence_v3.json'


def apply_scope(data):
    policy = json.loads(POLICY.read_text(encoding='utf-8'))
    source = data['competition_source']
    assert hashlib.sha256((ROOT/source['file']).read_bytes()).hexdigest() == source['sha256']
    assert policy['submission_scope']['physical_validation_required'] is False
    rows = {r['id']: r for r in data['requirements']}
    assert set(policy['requirement_overrides']).issubset(rows)
    for key, changes in policy['requirement_overrides'].items(): rows[key].update(changes)
    data['submission_scope'] = deepcopy(policy['submission_scope'])
    data['submission_scope']['source'] = deepcopy(source) | {'page': 4}
    data['scope_note'] = '作品按创意方案与可演示原型交付；基本成果与可选加分分别登记。实物实验不作为本轮完成门槛。'
    data['conditional_research'] = 'optional_for_creative_submission'
    titles = {'conflict': '多目标权衡与冲突解释', 'evidence': '场景驱动的可解释推荐', 'validation': '人机协同的配方演化'}
    for item in data['highlights']:
        item['title'] = titles.get(item['id'], item['title'])
        if item['id'] == 'validation':
            item['question'] = '工程师调整配方后，方案和依据如何随之变化？'
            item['mechanism'] = '人工微调、组分变化、材料版本与重新比较贯通。'
    answers = {
        '创新点在哪，是否只是筛表？': '创新设计在场景需求转译、多目标冲突解释与人机协同配方演化的衔接，形成可追溯的交互设计流程。常见规则和优化算法不作为原创数学方法；同池数值可行集一致时，价值体现在决策组织和解释能力。',
        'AI模型效果怎样？': '已有独立、多任务与集成计算实验，完整保留与基线的比较及退步结果，用作小样本建模可行性的辅助材料。本次重点说明模型设计、数据条件和核心原型，不以正式模型上线或四项全部超越基线为完成门槛。',
        '节省多少时间、成本或碳排？': '用案例解释需求整理、候选比选和调整记录的潜在价值，情景测算明确假设与来源。本次不要求真人测时；尚无依据的节时、成本、碳排和寿命收益不填为实绩。',
    }
    for item in data['questions']:
        if item['question'] in answers: item['answer'] = answers[item['question']]
    scope_question = {'question': '本次参赛必须完成实物实验吗？',
        'answer': '不需要。赛题第4页以创意方案为主，不要求完整工程实现，实验室性能验证属于加分成果。本次按技术方案、核心原型、至少三类场景、五个带对照案例和潜在应用价值分析交付；实物实验留作后续工程化拓展。',
        'requirement_ids': ['B01', 'B02', 'B03', 'B04', 'B05', 'X05']}
    data['questions'] = [q for q in data['questions'] if q['question'] != scope_question['question']] + [scope_question]
    new_evidence = {'B01': ['docs/creative-proposal-scope-v6.md'],
                    'B04': ['docs/creative-proposal-scope-v6.md', 'planning/creative_proposal_phase_v6.json', 'configs/creative_scope_v6.json'],
                    'B05': ['docs/creative-proposal-scope-v6.md'], 'X05': ['docs/creative-proposal-scope-v6.md']}
    for requirement, paths in new_evidence.items():
        for name in paths:
            key = 'ev_'+hashlib.sha256(name.encode()).hexdigest()[:14]
            data['evidence'][key] = {'id': key, 'path': name, 'label': Path(name).name,
                'sha256': hashlib.sha256((ROOT/name).read_bytes()).hexdigest()}
            if key not in rows[requirement]['evidence_ids']: rows[requirement]['evidence_ids'].append(key)
    # Refresh only documents/code intentionally changed for this scope correction.
    allowed_updates = {'README.md', 'backend/app/review/reports.py', 'frontend/src/components/ReviewCenter.tsx',
                       'frontend/src/components/ResearchWorkbench.tsx', 'frontend/src/main.tsx', 'frontend/src/review-types.ts'}
    for item in data['evidence'].values():
        if item['path'] in allowed_updates: item['sha256'] = hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()
    data['creative_scope_update'] = {'updated_at': datetime.now(timezone.utc).isoformat(),
        'policy': POLICY.relative_to(ROOT).as_posix(), 'user_instruction': policy['user_instruction'],
        'previous_registry': 'artifacts/creative-scope/previous-review-registry.json',
        'physical_validation_required': False, 'historical_measurements_unchanged': True}
    return data


def update():
    raw = REGISTRY.read_bytes()
    backup = ROOT/'artifacts/creative-scope/previous-review-registry.json'
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists(): backup.write_bytes(raw)
    result = apply_scope(json.loads(raw))
    REGISTRY.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print({'scope': result['submission_scope']['kind'], 'physical_validation_required': False,
           'requirements': len(result['requirements']), 'evidence': len(result['evidence'])})


if __name__ == '__main__':
    update()
