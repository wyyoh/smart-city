from copy import deepcopy

from app.decision.rules import match_rules, profiles
from app.domain.contracts_v2 import DemandRequest


def test_three_distinct_conditions_generate_sourced_targets():
    cards = profiles()['profiles']
    for card, priority, value in zip(cards, ['DS', 'strain', 'TSR'], [8000, 2500, 85]):
        result = match_rules(DemandRequest.model_validate(card['example_request']))
        assert len(result['matches']) == 1
        rule = result['matches'][0]
        assert rule['priority'][0] == priority
        assert next(t for t in rule['targets'] if t['metric'] == priority)['value'] == value
        assert all(t['source']['reference'] for t in rule['targets'])
        assert len(rule['target_history'][priority]) == 2


def test_unknown_severity_or_wrong_context_never_uses_demo_defaults():
    example = profiles()['profiles'][0]['example_request']
    for field, value in [('severity', None), ('severity', 'mild'), ('type', 'unknown_cracking')]:
        data = deepcopy(example)
        data['scene']['distress'][field] = value
        assert not match_rules(DemandRequest.model_validate(data))['matches']
    data = deepcopy(example)
    data['context_kind'] = 'project'
    assert not match_rules(DemandRequest.model_validate(data))['matches']
    data = deepcopy(example)
    data['scene']['traffic']['class'] = None
    assert not match_rules(DemandRequest.model_validate(data))['matches']
