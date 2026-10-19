"""Applicability is separate from numerical satisfaction; unknown never passes formally."""
from ..domain.contracts_v2 import metric_registry


def dimension(name, requirement, evidence, *, membership=False):
    if requirement is None or evidence is None or requirement == '' or evidence == '':
        status = 'unknown'
    else:
        status = 'applicable' if (requirement in evidence if membership else requirement == evidence) else 'inapplicable'
    return {'dimension': name, 'required': requirement, 'recorded': evidence, 'status': status}


def construction_eligibility(recipe, request):
    application = recipe['payload'].get('applicability', {})
    dimensions = []
    for key in ['maintenance_method', 'layer', 'structure_type']:
        recorded = application.get(key)
        if recorded is not None and not isinstance(recorded, list):
            recorded = [recorded]
        dimensions.append(dimension(key, request['scene'].get(key), recorded, membership=True))
    recorded = application.get('construction', {})
    for key in ['mixing_window', 'compaction_window']:
        # These are declared compatible window identifiers; free-text descriptions are not range algebra.
        dimensions.append(dimension(key, request['construction'].get(key), recorded.get(key)))
    equipment, available = recorded.get('equipment'), request['construction'].get('equipment')
    if equipment is not None and available is not None:
        dimensions.append({'dimension': 'equipment', 'required': equipment, 'recorded': available,
                           'status': 'applicable' if set(equipment).issubset(set(available)) else 'inapplicable'})
    else:
        dimensions.append(dimension('equipment', equipment, available))
    return {'dimensions': dimensions, 'status': combined_status(dimensions)}


def combined_status(dimensions):
    statuses = [d['status'] for d in dimensions]
    return 'inapplicable' if 'inapplicable' in statuses else 'unknown' if 'unknown' in statuses else 'applicable'


def evidence_eligibility(recipe, target, request):
    evidence = recipe['evidence'].get(target['metric'], {})
    definition = metric_registry()['metrics'][target['metric']]
    dimensions = [dimension('unit', target['unit'], evidence.get('unit')),
                  dimension('test_method', target.get('test_method'), evidence.get('method'))]
    conditions = evidence.get('structured_conditions', evidence.get('conditions'))
    conditions = conditions if isinstance(conditions, dict) else {}
    # Require all metric-defining conditions, not just the subset conveniently supplied by a caller.
    for key in sorted(set(definition['condition_keys'] + list(target['conditions'])) - {'test_method'}):
        dimensions.append(dimension('condition.' + key, target['conditions'].get(key), conditions.get(key)))
    source_kind = evidence.get('source_kind', '')
    scope_status = 'inapplicable' if request['context_kind'] == 'project' and source_kind.startswith('demo') else 'applicable' if source_kind else 'unknown'
    dimensions.append({'dimension': 'data_scope', 'required': request['context_kind'], 'recorded': source_kind or None,
                       'status': scope_status})
    common = construction_eligibility(recipe, request)
    dimensions.extend(common['dimensions'])
    known_invalid = any(d['status'] == 'inapplicable' for d in dimensions)
    demo_numeric = request['context_kind'] == 'constructed_demo' and target.get('comparison_basis') == 'legacy_workbook_numeric_demo' and definition['numeric_demo_supported']
    comparable = not known_invalid and (demo_numeric or combined_status(dimensions) == 'applicable')
    return {'status': combined_status(dimensions), 'dimensions': dimensions,
            'numeric_comparison_allowed': comparable, 'comparison_mode': 'numeric_demo' if demo_numeric else 'engineering_evidence',
            'unresolved_dimensions': [d['dimension'] for d in dimensions if d['status'] == 'unknown'],
            'reason': '存在明确不兼容条件' if known_invalid else '仅允许历史数值演示，工程适用仍未知' if demo_numeric else
                      '同方法条件证据适用' if comparable else '方法、条件或工艺未知，不能作为正式达标证据'}


def resource_eligibility(recipe, request):
    constraints = request['constraints']
    results = []
    for key, value_field, unit_field in [('budget', 'unit_cost', 'cost_unit'), ('carbon_cap', 'carbon', 'carbon_unit'),
                                          ('schedule_days', 'delivery_days', None)]:
        limit = constraints.get(key)
        if limit is None:
            continue
        recorded = recipe['payload'].get('resources', {})
        value = recorded.get(value_field)
        unit_ok = unit_field is None or (constraints.get('budget_unit' if key == 'budget' else 'carbon_unit') is not None and
                                           constraints.get('budget_unit' if key == 'budget' else 'carbon_unit') == recorded.get(unit_field))
        status = 'missing' if value is None else 'incomparable' if not unit_ok else 'satisfied' if value <= limit else 'failed'
        results.append({'key': key, 'limit': limit, 'value': value, 'state': status,
                        'reason': '尚无价格/碳排/供货证据，不能判断' if value is None else '单位基准不一致' if not unit_ok else '按已记录资源值比较'})
    rap_limit = constraints.get('rap_min_pct')
    if rap_limit is not None:
        value = recipe['rap_nominal_pct']
        grade = recipe['payload'].get('gradation') or {}
        demo = request['context_kind'] == 'constructed_demo'
        basis_ok = grade.get('rap_mass_basis') == 'confirmed'
        state = 'missing' if value is None else 'incomparable' if not basis_ok and not demo else 'satisfied' if value >= rap_limit else 'failed'
        results.append({'key': 'rap_min_pct', 'limit': rap_limit, 'value': value, 'state': state,
                        'reason': '名义RAP演示比较，组成质量基准仍待确认' if demo and not basis_ok else 'RAP质量基准未确认' if not basis_ok else '确认质量口径后比较'})
    return results
