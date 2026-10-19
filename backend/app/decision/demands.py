"""Resolve scene requirements, retain unknowns, and append auditable confirmations."""
from copy import deepcopy

from fastapi import HTTPException

from ..domain.contracts_v2 import DemandConfirmation, DemandRequest, metric_registry
from .records import append_record, digest, get_record
from .rules import match_rules, rulebook, scene_value
from .cases import casebook


REQUIRED_SCENE = ['maintenance_method', 'layer', 'structure_type', 'climate.class', 'traffic.class',
                  'distress.type', 'distress.severity']


def target_conflicts(targets):
    """Contradictions within exactly the same metric/method/conditions/basis; never merge unknown methods."""
    groups = {}
    for target in targets:
        if target['operator'] == 'grade':
            continue
        key = digest({k: target[k] for k in ['metric', 'unit', 'test_method', 'conditions', 'comparison_basis']})
        groups.setdefault(key, []).append(target)
    conflicts = []
    for group in groups.values():
        # Missing method is only a declared numeric-demo basis, not an engineering equivalence.
        if group[0]['test_method'] is None and group[0]['comparison_basis'] != 'legacy_workbook_numeric_demo':
            continue
        lower, upper = (float('-inf'), False), (float('inf'), False)
        for target in group:
            op, val = target['operator'], target['value']
            if op in ['>', '>=', 'between']:
                lower = max(lower, (val, op == '>'))
            if op in ['<', '<=', 'between']:
                bound = target['upper'] if op == 'between' else val
                if bound < upper[0] or (bound == upper[0] and op == '<'):
                    upper = (bound, op == '<')
        if lower[0] > upper[0] or (lower[0] == upper[0] and (lower[1] or upper[1])):
            conflicts.append({'code': 'contradictory_targets', 'metric': group[0]['metric'],
                              'target_ids': [t['target_id'] for t in group], 'message': '相同口径目标的上下界互相冲突'})
    return conflicts


def demand_status(request, targets, rules):
    registry = metric_registry()['metrics']
    missing = [{'code': 'missing_scene', 'field': key, 'message': '场景信息待确认：' + key}
               for key in REQUIRED_SCENE if not scene_value(request['scene'], key)]
    if not rules['matches'] and not request['project_targets']:
        missing.append({'code': 'no_rule_or_project_target', 'message': '没有适用的演示规则；请确认场景或补充有出处的项目要求'})
    if request.get('demo_case_id'):
        case = next(c for c in casebook()['cases'] if c['id'] == request['demo_case_id'])
        if case['profile_id'] not in [r['id'] for r in rules['matches']]:
            missing.append({'code': 'case_scene_mismatch', 'message': '所选构造案例与当前场景条件不匹配，请重新选择案例或确认项目要求'})
    for metric in request['requested_metrics']:
        if metric not in [t['metric'] for t in targets]:
            missing.append({'code': 'unquantified_requirement', 'metric': metric, 'message': '已保留需求，尚缺目标及适用口径'})
    gaps = [{'metric': metric, 'message': registry[metric].get('capability_gap', '现有流程尚未验证该指标的筛选能力')}
            for metric in dict.fromkeys(request['requested_metrics'] + [t['metric'] for t in targets])
            if not registry[metric]['numeric_demo_supported']]
    conflicts = target_conflicts(targets)
    warnings = []
    if request['context_kind'] == 'constructed_demo':
        warnings.append('构造演示：历史数值比较不构成工程适用结论。')
    if any(not t['test_method'] or not t['conditions'] for t in targets):
        warnings.append('部分目标未确认试验方法或条件；正式项目中未知条件不能通过适用性检查。')
    if request['inventory']['source_codes'] is None:
        warnings.append('库存尚未确认；检索可展示目录，但不能据此确认可采购性。')
    if gaps:
        warnings.append('存在暂不支持的合法需求，保留缺口并等待补充证据。')
    return {'open_items': missing, 'conflicts': conflicts, 'capability_gaps': gaps, 'warnings': warnings,
            'requirements_complete': bool(targets) and not missing and not conflicts,
            'ready_for_candidate_retrieval': bool(targets) and not missing and not conflicts}


def resolve_demand(session, request: DemandRequest):
    rules = match_rules(request)
    targets, history, priority = [], {}, []
    # Multiple matches are kept as separate requirements, never silently max/min merged.
    for rule in rules['matches']:
        for index, target in enumerate(rule['targets']):
            target_id = f"{rule['id']}:{target['metric']}:{index}"
            targets.append({'target_id': target_id, 'derived_by': rule['id'], **target})
            history[target_id] = rule['target_history'][target['metric']]
        priority.extend(rule['priority'])
    for index, target in enumerate(request.project_targets):
        target_id = f'project:{target.metric}:{index}'
        value = target.model_dump(mode='json')
        targets.append({'target_id': target_id, 'derived_by': 'project_input', **value})
        history[target_id] = [value]
        priority.append(target.metric)
    case_application = None
    if request.demo_case_id:
        case = next(c for c in casebook()['cases'] if c['id'] == request.demo_case_id)
        if case['profile_id'] in [r['id'] for r in rules['matches']]:
            for target in targets:
                if target['derived_by'] == 'project_input':
                    continue
                value = case['targets'].get(target['metric'])
                if value is not None and target['value'] != value:
                    target['value'] = value
                    target['source'] = {'kind': 'constructed_demo', 'reference': f"明确选用的团队构造案例{case['id']} v2.0.0；非规范推导", 'confirmed': False}
                    target['derived_by'] = 'explicit_demo_case'
                    history[target['target_id']].append({k: v for k, v in target.items() if k not in ['target_id', 'derived_by']})
            priority = [case['priority']] + [p for p in priority if p != case['priority']]
            case_application = {'id': case['id'], 'title': case['title'], 'version': casebook()['version'],
                                'source': '用户明确选择的构造要求模板；C4/C5附加目标不声称仅由气候病害自动推导'}
    body = request.model_dump(mode='json', by_alias=True)
    return append_record(session, 'demand_resolution', {
        'schema_version': '2.0', 'request': body, 'rules': rules, 'targets': targets,
        'target_history': history, 'case_application': case_application, 'priority': list(dict.fromkeys(priority)),
        'versions': {'rules': rules['version'], 'rules_sha256': rules['sha256'],
                     'case_scenarios_sha256': casebook()['sha256'],
                     'metrics': metric_registry()['version'], 'metrics_sha256': digest(metric_registry())},
        **demand_status(body, targets, rules),
    })


def confirm_demand(session, resolution_id, request: DemandConfirmation):
    original = get_record(session, resolution_id, 'demand_resolution')
    if original['sha256'] != request.expected_sha256:
        raise HTTPException(409, '需求版本已变化，请重新读取并确认')
    if original['versions']['rules_sha256'] != rulebook()['sha256'] or original['versions']['metrics_sha256'] != digest(metric_registry()):
        raise HTTPException(409, '规则或指标注册表已更新，请重新解析需求')
    if original['versions'].get('case_scenarios_sha256') != casebook()['sha256']:
        raise HTTPException(409, '构造案例模板已更新，请重新解析需求')
    targets = deepcopy(original['targets'])
    changes = []
    for override in request.overrides:
        target = next((t for t in targets if t['target_id'] == override.target_id), None)
        if target is None:
            raise HTTPException(422, '覆盖目标不属于当前需求卡')
        new = override.requirement.model_dump(mode='json')
        if new['metric'] != target['metric']:
            raise HTTPException(422, '覆盖必须保留原指标；新增指标请重新解析项目需求')
        if original['request']['context_kind'] == 'project' and (
            new['source']['kind'] == 'constructed_demo' or new['comparison_basis'] == 'legacy_workbook_numeric_demo'
        ):
            raise HTTPException(422, '正式项目不可使用演示阈值或口径')
        changes.append({'target_id': target['target_id'], 'before': deepcopy(target), 'after': new,
                        'reason': override.reason})
        target.update(new)
        target['derived_by'] = 'engineer_override'
    status = demand_status(original['request'], targets, original['rules'])
    return append_record(session, 'demand_confirmation', {
        'schema_version': '2.0', 'resolution_id': resolution_id, 'resolution_sha256': original['sha256'],
        'request': original['request'], 'targets': targets, 'target_history': original['target_history'],
        'priority': original['priority'], 'rules': original['rules'], 'versions': original['versions'], 'case_application': original.get('case_application'),
        'confirmed_by': request.confirmed_by, 'confirmation_note': request.note, 'overrides': changes,
        'confirmation_status': 'confirmed' if status['requirements_complete'] else 'confirmed_with_open_items', **status,
    }, parent_id=resolution_id)
