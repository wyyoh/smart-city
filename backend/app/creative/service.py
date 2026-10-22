from copy import deepcopy
import hashlib
from pathlib import Path

from fastapi import HTTPException
from sqlmodel import select

from ..decision.candidate_pool import PoolRequest, freeze_pool
from ..decision.cases import demonstration_cases
from ..decision.comparison import compare_feasible
from ..decision.decisions import DecisionRequest, run_decision
from ..decision.constraints import assess_recipe
from ..decision.demands import confirm_demand, resolve_demand
from ..decision.freshness import decision_freshness
from ..decision.records import DecisionRecord, append_record, digest, get_record
from ..domain.contracts import Scenario
from ..domain.contracts_v2 import DemandConfirmation, DemandRequest, metric_registry
from ..research_workbench import service as research
from ..services import assess, case_cards

CASE_COPY = {
    'C1': ('为什么这个路段需要这些材料性能？', '场景到需求', '查看需求出处，并比较两种材料的性能余量。'),
    'C2': ('应变相同，怎样选择并继续设计？', '人机协同设计', '解释并列后的取舍，再从R4探索油石比微调。'),
    'C3': ('都满足要求，应该优先看哪一种？', '多目标取舍', '切换TSR、残留稳定度和应变优先，比较选择理由。'),
    'C4': ('再生材料要求提高后还有方案吗？', '资源约束', '比较名义RAP70%与75%要求下的结果。'),
    'C5': ('没有可行方案，下一步应该做什么？', '冲突与后续行动', '区分资料不足与范围内冲突，再选择后续方向。'),
}
RECORD_KINDS = {'creative_case_run', 'preference_comparison', 'design_draft'}


def policy_sha():
    return hashlib.sha256(b''.join(p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py')))).hexdigest()


def cases():
    result = demonstration_cases()
    for case in result['cases']:
        question, mechanism, action = CASE_COPY[case['id']]
        case.update(question=question, mechanism=mechanism, action=action)
    return result


def existing_request(session, record_id, fingerprint, kind):
    record = session.get(DecisionRecord, record_id)
    if record:
        saved = get_record(session, record_id, kind)
        if saved.get('request_fingerprint') != fingerprint:
            raise HTTPException(409, '请求编号已用于其他内容，请重新发起操作。')
        return saved
    return None


def current_decision(session, decision_id, expected_sha256=None):
    decision = get_record(session, decision_id, 'material_decision')
    if expected_sha256 is not None and decision['sha256'] != expected_sha256:
        raise HTTPException(409, '原选材决策指纹不一致，请重新读取。')
    freshness = decision_freshness(session, decision_id)
    if not freshness['current']:
        raise HTTPException(409, '原选材结果已变化，请重新运行场景：'+'；'.join(freshness['reasons']))
    return decision


def scene_explanation(decision):
    demand = decision['demand']
    return {'scene': demand['request']['scene'], 'rules': demand['rules']['matches'],
            'case_application': demand.get('case_application'), 'priority': demand['priority'],
            'targets': deepcopy(demand['targets']), 'target_history': deepcopy(demand.get('target_history', {})),
            'constraints': deepcopy(demand['request']['constraints']),
            'path': ['养护场景', '有出处的性能要求', '同范围候选', '材料历史证据'],
            'note': '场景或要求变化会重新筛选；历史材料数值保持原记录。'}


def run_case(session, case_id, request):
    case = next((c for c in cases()['cases'] if c['id'] == case_id), None)
    if not case:
        raise HTTPException(404, '案例不存在。')
    if request.rap_min_pct is not None and (case_id != 'C4' or not request.adjustment_reason):
        raise HTTPException(422, '仅C4支持该资源要求比较，调整时请填写理由。')
    if request.evidence_view != 'all' and case_id != 'C5':
        raise HTTPException(422, '完整数值诊断视图在本工作区仅用于C5。')
    body = {'case_id': case_id, **request.model_dump()}
    fingerprint = digest(body); record_id = 'crun_'+request.request_id
    saved = existing_request(session, record_id, fingerprint, 'creative_case_run')
    if saved:
        return saved
    if request.based_on_decision_id:
        original = current_decision(session, request.based_on_decision_id, request.expected_decision_sha256)
        if (original['demand'].get('case_application') or {}).get('id') != case_id:
            raise HTTPException(422, '原决策与当前案例不匹配。')
    example = deepcopy(case['example_request'])
    if request.rap_min_pct is not None:
        example['constraints']['rap_min_pct'] = request.rap_min_pct
        example['name'] += f' · 名义RAP要求{request.rap_min_pct:g}%'
    resolution = resolve_demand(session, DemandRequest.model_validate(example))
    overrides = []
    for target in resolution['targets']:
        if target['metric'] in request.target_overrides and request.target_overrides[target['metric']] != target['value']:
            requirement = {k: v for k, v in target.items() if k not in ['target_id', 'derived_by']}
            requirement['value'] = request.target_overrides[target['metric']]
            requirement['source'] = {'kind': 'constructed_demo', 'reference': '本地案例人工调整：'+request.adjustment_reason, 'confirmed': False}
            overrides.append({'target_id': target['target_id'], 'requirement': requirement, 'reason': request.adjustment_reason})
    confirmed = confirm_demand(session, resolution['id'], DemandConfirmation.model_validate({
        'expected_sha256': resolution['sha256'], 'confirmed_by': '本地创意案例操作',
        'note': request.adjustment_reason, 'overrides': overrides}))
    pool = freeze_pool(session, PoolRequest(confirmation_id=confirmed['id'], evidence_view=request.evidence_view))
    decision = run_decision(session, DecisionRequest(pool_id=pool['id']))
    # Reuse the actual v1 assessment on exactly this frozen pool without writing a v1 recommendation.
    legacy = deepcopy(next(c['scenario'] for c in case_cards() if c['id'] == case_id))
    legacy['candidate_ids'] = pool['candidate_ids']
    if request.rap_min_pct is not None:
        legacy['rap_min_pct'] = request.rap_min_pct
    for target in legacy['targets']:
        if target['metric'] in request.target_overrides:
            target['value'] = request.target_overrides[target['metric']]
    baseline_request = Scenario.model_validate(legacy)
    assessed = [assess(row, baseline_request) for row in pool['candidates']]
    b1_ids = sorted(r['id'] for r in assessed if r['passes_targets'])
    v2_ids = sorted(decision['comparison']['feasible_ids'])
    payload = {'schema_version': 'creative-1', 'case_id': case_id, 'title': case['title'],
               'question': case['question'], 'mechanism': case['mechanism'],
               'identity': '团队合理构造场景；使用工作簿历史数值作软件演示',
               'request_fingerprint': fingerprint, 'run_request': body, 'decision': decision,
               'explanation': scene_explanation(decision),
               'baseline': {'method': 'B1：原v1全数值约束评估，同一冻结候选及目标',
                            'candidate_ids': pool['candidate_ids'], 'feasible_ids': b1_ids,
                            'same_feasible_set': b1_ids == v2_ids,
                            'note': '一致时说明数值筛选一致；新增价值由解释、比选与调整过程展示。'},
               'policy_sha256': policy_sha(), 'adjustment_reason': request.adjustment_reason}
    return append_record(session, 'creative_case_run', payload, parent_id=decision['id'],
                         dataset_id=decision['scope']['dataset']['id'], record_id=record_id)


def preview_adjustment(session, decision_id, request):
    decision = current_decision(session, decision_id, request.expected_decision_sha256)
    demand = deepcopy(decision['demand'])
    case_id = (demand.get('case_application') or {}).get('id')
    if not case_id or demand['request']['context_kind'] != 'constructed_demo':
        raise HTTPException(422, '此入口仅用于已选用构造案例的要求比较。')
    if request.rap_min_pct is not None and case_id != 'C4':
        raise HTTPException(422, '名义RAP要求比较仅用于C4。')
    available = {t['metric'] for t in demand['targets']}
    if set(request.target_overrides) - available:
        raise HTTPException(422, '调整指标不属于当前需求。')
    changes = []
    for target in demand['targets']:
        value = request.target_overrides.get(target['metric'], target['value'])
        if value != target['value']:
            changes.append({'metric': target['metric'], 'before': target['value'], 'after': value, 'unit': target['unit']})
            target['value'] = value
    if request.rap_min_pct is not None:
        before = demand['request']['constraints']['rap_min_pct']
        demand['request']['constraints']['rap_min_pct'] = request.rap_min_pct
        if before != request.rap_min_pct:
            changes.append({'metric': 'rap_min_pct', 'before': before, 'after': request.rap_min_pct, 'unit': '%'})
    pool = get_record(session, decision['pool_id'], 'candidate_pool')
    results = [assess_recipe(r, demand) for r in pool['candidates']]
    ids = sorted(r['id'] for r in results if r['passes_known_requirements'])
    return {'kind': 'adjustment_preview', 'source_decision_id': decision_id, 'source_decision_sha256': decision['sha256'],
            'pool_sha256': decision['pool_sha256'], 'pool_size': len(results), 'changes': changes,
            'before_feasible_ids': decision['comparison']['feasible_ids'], 'after_feasible_ids': ids,
            'summary': {status: sum(r['status'] == status for r in results) for status in ['excluded', 'needs_evidence', 'numeric_review', 'evidence_review']},
            'note': '仅预览同池数值判断，不保存或修改原需求；确认后生成新的需求和决策。'}


def preference_comparison(session, request):
    body = request.model_dump(); fingerprint = digest(body)
    record_id = 'pref_'+request.request_id if request.persist else None
    if record_id:
        saved = existing_request(session, record_id, fingerprint, 'preference_comparison')
        if saved:
            return saved
    decision = current_decision(session, request.decision_id, request.expected_decision_sha256)
    demand = deepcopy(decision['demand']); rows = deepcopy(decision['results'])
    comparable = list(dict.fromkeys(t['metric'] for t in demand['targets'] if t['operator'] in ['>', '>=', '<', '<=']))
    if set(request.priority_order) - set(comparable):
        raise HTTPException(422, '偏好只能使用本次已量化且可比较的性能指标。')
    priority = list(dict.fromkeys(request.priority_order+demand['priority']+comparable))
    demand['priority'] = priority
    comparison = compare_feasible(rows, demand)
    original_ids = decision['comparison']['feasible_ids']
    if set(comparison['feasible_ids']) != set(original_ids):
        raise HTTPException(409, '偏好比较改变了可行集合，请重新核对。')
    by_id = {r['id']: r for r in rows}
    ordered = [by_id[k] for k in comparison['feasible_ids']]
    labels = metric_registry()['metrics']
    explanations = []
    for row in ordered:
        values = []
        for metric in priority:
            check = next((c for c in row['checks'] if c['metric'] == metric), None)
            if check:
                values.append({'metric': metric, 'label': labels[metric]['label'], 'value': check.get('value'),
                               'unit': check.get('unit'), 'margin': check.get('margin'), 'operator': check.get('operator')})
        first_difference = None
        if ordered and row['id'] != ordered[0]['id']:
            top_checks = {c['target_id']: c for c in ordered[0]['checks']}
            for target_id in comparison['target_order']:
                check = next(c for c in row['checks'] if c['target_id'] == target_id)
                if check.get('value') != top_checks[target_id].get('value'):
                    first_difference = {'metric': check['metric'], 'label': labels[check['metric']]['label'],
                                        'value': check.get('value'), 'first_value': top_checks[target_id].get('value'),
                                        'unit': check.get('unit'), 'operator': check.get('operator')}
                    break
        explanations.append({'id': row['id'], 'rank': row['preference_rank'], 'tied_with': row['tied_with'],
                             'values': values, 'first_difference_from_first': first_difference})
    payload = {'schema_version': 'creative-1', 'request_fingerprint': fingerprint,
               'source_decision_id': decision['id'], 'source_decision_sha256': decision['sha256'],
               'pool_sha256': decision['pool_sha256'], 'priority_order': priority, 'reason': request.reason,
               'comparison': comparison, 'candidates': ordered, 'explanations': explanations,
               'same_feasible_set': True, 'policy_sha256': policy_sha(),
               'note': '仅调整同一硬要求下的查看顺序；并列保留，其他性能更好不补偿硬要求失败。'}
    if request.persist:
        return append_record(session, 'preference_comparison', payload, parent_id=decision['id'],
                             dataset_id=decision['scope']['dataset']['id'], record_id=record_id)
    preview = {**payload, 'kind': 'preference_preview'}
    return {**preview, 'sha256': digest(preview)}


def research_context(session, decision_id, parent_id):
    decision = current_decision(session, decision_id)
    parent = next((r for r in decision['results'] if r['id'] == parent_id), None)
    if parent is None:
        raise HTTPException(404, '所选材料不属于此选材结果。')
    compatible = research.compatibility(session)
    if not compatible['matches']:
        raise HTTPException(409, compatible['reason'])
    if decision['scope']['dataset'] != compatible['current']:
        raise HTTPException(409, '选材与研究数据版本不匹配，请重新选材。')
    # All evidence bound to a newly saved design is checked, not just the selected hypothesis.
    for evidence_id in research.registry()['evidence']:
        research.verified_path(evidence_id)
    hypotheses = [h for h in research.artifact('candidate_pool')['hypotheses'] if h['parent_id'] == parent_id]
    return decision, parent, hypotheses


def matches_locks(hypothesis, locks, parent):
    if 'oil_stone_ratio_pct' in locks and hypothesis['oil_stone_ratio_pct'] != parent['scheme']['fields']['oil_stone_ratio_pct']['value']:
        return False
    if 'nominal_component_weights' in locks:
        original = [c['nominal_weight'] for c in parent['scheme']['components']]
        if hypothesis['nominal_component_weights'] != original:
            return False
    return True


def exploration(session, decision_id, parent_id, supported_only=True, locked_fields=None):
    decision, parent, hypotheses = research_context(session, decision_id, parent_id)
    locks = locked_fields or []
    rows = [h for h in hypotheses if matches_locks(h, locks, parent) and
            (not supported_only or (h['within_basic_design_distance_support'] and h['within_observed_same_nmas_curve_envelope']))]
    return {'decision_id': decision_id, 'decision_sha256': decision['sha256'], 'parent': parent,
            'demand_context': decision['demand'], 'scope_sha256': digest(research.scope()),
            'total_parent_hypotheses': len(hypotheses), 'total': len(rows),
            'items': [research.summary(row) for row in rows], 'locked_fields': locks,
            'supported_only': supported_only, 'policy_sha256': policy_sha(),
            'empty_reason': '此父方案没有满足当前锁定项与支持范围的假设；可解除锁定或返回选材。' if not rows else None}


def save_draft(session, request):
    body = request.model_dump(); fingerprint = digest(body); record_id = 'draft_'+request.request_id
    saved = existing_request(session, record_id, fingerprint, 'design_draft')
    if saved:
        return saved
    decision, parent, hypotheses = research_context(session, request.origin_decision_id, request.parent_recipe_id)
    if decision['sha256'] != request.expected_decision_sha256:
        raise HTTPException(409, '原选材决策指纹不一致，请重新读取。')
    if digest(research.scope()) != request.research_scope_sha256:
        raise HTTPException(409, '研究证据版本已变化，请重新查看假设。')
    chosen = next((h for h in hypotheses if h['id'] == request.hypothesis_id), None)
    if chosen is None:
        raise HTTPException(422, '所选假设不属于准确的父方案。')
    if not matches_locks(chosen, request.locked_fields, parent):
        raise HTTPException(422, '所选假设改变了已锁定的字段。')
    detail = research.candidate_detail(chosen['id'])
    changes = {'oil_stone_ratio_pct': {'before': parent['scheme']['fields']['oil_stone_ratio_pct']['value'],
                                     'after': chosen['oil_stone_ratio_pct'], 'unit': '%'},
               'components': [c for c in detail['components'] if c['delta_percentage_points'] != 0]}
    payload = {'schema_version': 'creative-1', 'title': '材料设计草案', 'request_fingerprint': fingerprint,
               'origin_decision_id': decision['id'], 'source_decision_sha256': decision['sha256'],
               'parent_recipe_id': parent['id'], 'parent': deepcopy(parent), 'hypothesis_id': chosen['id'],
               'hypothesis': detail, 'actual_changes': changes, 'locked_fields': request.locked_fields,
               'demand_context': deepcopy(decision['demand']), 'design_intent': request.design_intent,
               'scope': research.scope(), 'research_scope_sha256': request.research_scope_sha256,
               'policy_sha256': policy_sha(), 'measured_performance': None,
               'inherits_parent_measurements': False, 'engineering_release_allowed': False,
               'note': '保存设计意图、组成变化与原需求。父方案历史数值仅作参照，新设计实测仍未知。'}
    # Re-check currentness after preparing the complete saved content.
    session.expire_all()
    current_decision(session, decision['id'], decision['sha256'])
    if not research.compatibility(session)['matches'] or digest(research.scope()) != request.research_scope_sha256:
        raise HTTPException(409, '保存期间数据或研究证据版本已变化，请重新查看。')
    return append_record(session, 'design_draft', payload, parent_id=decision['id'],
                         dataset_id=decision['scope']['dataset']['id'], record_id=record_id)


def saved_record(session, record_id):
    record = get_record(session, record_id)
    if record['kind'] not in RECORD_KINDS:
        raise HTTPException(404, '工作区记录不存在。')
    return record


def history(session, kind):
    if kind not in RECORD_KINDS:
        raise HTTPException(422, '记录类型不支持。')
    rows = session.exec(select(DecisionRecord).where(DecisionRecord.kind == kind).order_by(DecisionRecord.created_at.desc()).limit(30)).all()
    return [{'id': r.id, 'title': r.payload.get('title', ''), 'created_at': r.created_at,
             'case_id': r.payload.get('case_id'), 'parent_recipe_id': r.payload.get('parent_recipe_id'),
             'design_intent': r.payload.get('design_intent'), 'sha256': r.payload['sha256']} for r in rows]
