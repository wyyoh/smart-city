"""Compare a frozen decision with current inputs without changing the old report."""
import hashlib
from pathlib import Path

from ..domain.contracts_v2 import metric_registry
from ..services import catalog, latest_dataset
from .candidate_pool import scope_exclusions
from .records import digest, get_record
from .rules import rulebook
from .cases import casebook


def engine_fingerprint():
    root = Path(__file__).parent
    return hashlib.sha256(b''.join(p.read_bytes() for p in sorted(root.glob('*.py')))).hexdigest()


def decision_freshness(session, decision_id):
    decision = get_record(session, decision_id, 'material_decision')
    pool = get_record(session, decision['pool_id'], 'candidate_pool')
    dataset = latest_dataset(session)
    reasons = []
    if decision['scope']['dataset'] != {'id': dataset.id, 'sha256': dataset.sha256, 'revision': dataset.revision}:
        reasons.append('数据集或反馈修订版本已更新')
    if decision['demand']['versions']['rules_sha256'] != rulebook()['sha256']:
        reasons.append('场景规则已更新')
    if decision['demand']['versions']['metrics_sha256'] != digest(metric_registry()):
        reasons.append('指标注册表已更新')
    if decision['demand']['versions'].get('case_scenarios_sha256') != casebook()['sha256']:
        reasons.append('构造案例模板已更新')
    if decision.get('engine_sha256') != engine_fingerprint():
        reasons.append('决策代码版本已更新或旧快照未记录代码指纹')
    current = []
    for recipe in sorted(catalog(session, context_kind=decision['demand']['request']['context_kind']), key=lambda r: r['id']):
        if scope_exclusions(recipe, decision['demand']['request']):
            continue
        if decision['scope']['evidence_view'] == 'complete_numeric_demo' and any(recipe['metrics'].get(t['metric']) is None for t in decision['demand']['targets']):
            continue
        current.append(recipe)
    old_by_id = {r['id']: digest(r) for r in pool['candidates']}
    current_by_id = {r['id']: digest(r) for r in current}
    added = sorted(set(current_by_id) - set(old_by_id))
    removed = sorted(set(old_by_id) - set(current_by_id))
    changed = sorted(k for k in set(old_by_id) & set(current_by_id) if old_by_id[k] != current_by_id[k])
    if added or removed or changed:
        reasons.append('当前检索范围的候选或证据发生变化')
    return {'decision_id': decision_id, 'snapshot_sha256': decision['sha256'], 'current': not reasons, 'reasons': reasons,
            'candidate_changes': {'added': added, 'removed': removed, 'changed_evidence': changed},
            'replay_note': '此快照保持原内容，可重放历史判断；新决策须使用重新确认的需求与冻结池。'}
