from app.decision.differences import compare_decisions
from decision_helpers import run_case


def test_identical_conditions_do_not_manufacture_differences(client):
    before = run_case(client, 'C1')
    after = run_case(client, 'C1')
    difference = compare_decisions(before, after)
    assert not difference['changed'] and not difference['target_changes']
    assert not difference['conclusion_changes']


def test_supported_scene_change_explains_inputs_rules_targets_and_outcomes(client):
    before, after = run_case(client, 'C1'), run_case(client, 'C2')
    response = client.get('/v2/decision-diff', params={'before_id': before['id'], 'after_id': after['id']})
    assert response.status_code == 200
    difference = response.json()
    assert difference['changed']
    assert any(c['field'] == 'scene.climate.class' for c in difference['input_changes'])
    assert {c['metric'] for c in difference['target_changes']} == {'DS', 'strain'}
    assert difference['rule_changes'] and difference['candidate_changes']['outcome_changes']
