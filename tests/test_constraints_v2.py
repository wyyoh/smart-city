from copy import deepcopy

from app.decision.comparison import compare_feasible
from app.decision.constraints import assess_recipe
from test_eligibility_v2 import example


def test_four_states_and_strict_boundary_are_not_compensated():
    request, target, recipe = example()
    target.update({'target_id': 'DS', 'operator': '>', 'value': 800})
    recipe.update({'id': 'a', 'display_id': 'A', 'metrics': {'DS': 800}})
    request['constraints'] = {}
    demand = {'targets': [target], 'request': request, 'priority': ['DS']}
    result = assess_recipe(recipe, demand)
    assert result['checks'][0]['state'] == 'failed' and result['status'] == 'excluded'
    recipe['metrics']['DS'] = 900
    assert assess_recipe(recipe, demand)['checks'][0]['state'] == 'satisfied'
    recipe['evidence']['DS']['method'] = 'method-B'
    assert assess_recipe(recipe, demand)['checks'][0]['state'] == 'incomparable'
    recipe['metrics']['DS'] = None
    assert assess_recipe(recipe, demand)['checks'][0]['state'] == 'missing'


def test_only_feasible_values_rank_and_identical_values_tie():
    demand = {'priority': ['DS'], 'targets': [{'target_id': 'DS', 'metric': 'DS', 'operator': '>'}]}
    def row(key, value, good=True):
        return {'id': key, 'passes_known_requirements': good, 'checks': [{'target_id': 'DS', 'value': value}]}
    a, b, c, failed = row('a', 900), row('b', 900), row('c', 850), row('failed', 99999, False)
    result = compare_feasible([a, b, c, failed], demand)
    assert result['review_first_ids'] == ['a', 'b'] and failed.get('preference_rank') is None
    assert a['tied_with'] == ['b'] and c['dominated_by'] == ['a', 'b']
