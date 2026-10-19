"""Non-compensatory four-state hard constraints."""
from ..domain.contracts_v2 import metric_registry
from .eligibility import evidence_eligibility, resource_eligibility


def satisfies(value, target):
    return {'>': lambda: value > target['value'], '>=': lambda: value >= target['value'],
            '<': lambda: value < target['value'], '<=': lambda: value <= target['value'],
            'between': lambda: target['value'] <= value <= target['upper']}[target['operator']]()


def margin(value, target):
    if target['operator'] in ['>', '>=']:
        return value - target['value']
    if target['operator'] in ['<', '<=']:
        return target['value'] - value
    return min(value - target['value'], target['upper'] - value)


def assess_recipe(recipe, demand):
    checks = []
    registry = metric_registry()['metrics']
    for target in demand['targets']:
        evidence = evidence_eligibility(recipe, target, demand['request'])
        value = recipe['metrics'].get(target['metric'])
        supported = registry[target['metric']]['numeric_demo_supported']
        state = 'missing' if value is None else 'incomparable' if not supported or not evidence['numeric_comparison_allowed'] else 'satisfied' if satisfies(value, target) else 'failed'
        checks.append({'target_id': target['target_id'], 'metric': target['metric'], 'value': value,
                       'required_value': target['value'], 'operator': target['operator'], 'upper': target.get('upper'), 'unit': target['unit'],
                       'state': state, 'margin': margin(value, target) if state in ['satisfied', 'failed'] else None,
                       'eligibility': evidence, 'reason': '没有当前版本的有效实测值' if state == 'missing' else
                       registry[target['metric']].get('capability_gap', '暂未验证该指标筛选能力') if not supported else
                       evidence['reason'] if state == 'incomparable' else '按声明口径逐项比较，边界符保持原义'})
    resources = resource_eligibility(recipe, demand['request'])
    checks.extend({'target_id': 'resource:' + c['key'], 'metric': c['key'], **c} for c in resources)
    states = [c['state'] for c in checks]
    status = 'excluded' if 'failed' in states else 'needs_evidence' if any(s in states for s in ['missing', 'incomparable']) else 'numeric_review' if demand['request']['context_kind'] == 'constructed_demo' else 'evidence_review'
    return {'id': recipe['id'], 'display_id': recipe['display_id'], 'status': status, 'checks': checks,
            'failed_targets': [c['target_id'] for c in checks if c['state'] == 'failed'],
            'unknown_targets': [c['target_id'] for c in checks if c['state'] in ['missing', 'incomparable']],
            'passes_known_requirements': bool(checks) and all(s == 'satisfied' for s in states),
            'engineering_release_approved': False}
