from copy import deepcopy

from app.decision.eligibility import evidence_eligibility, resource_eligibility


def example():
    request = {'context_kind': 'project', 'scene': {'maintenance_method': 'hot_recycling', 'layer': 'surface', 'structure_type': 'flexible'},
               'construction': {'equipment': ['mixer'], 'mixing_window': 'window-A', 'compaction_window': 'window-B'},
               'constraints': {'budget': 500, 'budget_unit': '元/吨', 'rap_min_pct': 50}}
    target = {'metric': 'DS', 'unit': '次/mm', 'test_method': 'method-A', 'conditions': {'temperature': '60C', 'load': 'load-A', 'conditioning': 'cond-A'}, 'comparison_basis': None}
    recipe = {'evidence': {'DS': {'unit': '次/mm', 'method': 'method-A', 'conditions': deepcopy(target['conditions']), 'source_kind': 'official_workbook'}},
              'payload': {'applicability': {**request['scene'], 'construction': deepcopy(request['construction'])}, 'gradation': {'rap_mass_basis': 'unconfirmed'}}, 'rap_nominal_pct': 60}
    return request, target, recipe


def test_unknown_does_not_pass_formally_but_explicit_demo_is_labeled():
    request, target, recipe = example()
    assert evidence_eligibility(recipe, target, request)['status'] == 'applicable'
    recipe['evidence']['DS']['method'] = None
    result = evidence_eligibility(recipe, target, request)
    assert result['status'] == 'unknown' and not result['numeric_comparison_allowed']
    request['context_kind'] = 'constructed_demo'
    target['comparison_basis'] = 'legacy_workbook_numeric_demo'
    assert evidence_eligibility(recipe, target, request)['numeric_comparison_allowed']
    recipe['evidence']['DS']['conditions']['temperature'] = '50C'
    result = evidence_eligibility(recipe, target, request)
    assert result['status'] == 'inapplicable' and not result['numeric_comparison_allowed']


def test_price_and_mass_basis_unknown_remain_unresolved():
    request, _, recipe = example()
    resources = {r['key']: r for r in resource_eligibility(recipe, request)}
    assert resources['budget']['state'] == 'missing'
    assert resources['rap_min_pct']['state'] == 'incomparable'
