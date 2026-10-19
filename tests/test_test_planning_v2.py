from decision_helpers import run_case


def test_known_failures_never_receive_completion_plan_and_actions_have_stopping_rule(client):
    decision = run_case(client, 'C1', 'all')
    plan = decision['test_plan']
    failed = {r['id'] for r in decision['results'] if r['failed_targets']}
    assert failed
    assert not failed & {c['candidate_id'] for c in plan['cards']}
    assert all(c['reason'] and c['stop_condition'] and c['pool_sha256'] == decision['pool_sha256'] for c in plan['cards'])
    assert plan['strategy'] == 'explainable_base_rules'
    # Numerically adequate demo candidates need applicability confirmation, not a claim of optimal retesting.
    first = decision['comparison']['review_first_ids'][0]
    assert all(c['action'] == 'confirm_applicability' for c in plan['cards'] if c['candidate_id'] == first)


def test_variant_has_specific_test_actions_and_no_inherited_measurements(client):
    variant = client.post('/v1/recipes/R1/variants', json={'oil_stone_ratio_pct':5.6,'note':'验证新版本行动'}).json()
    decision = run_case(client, 'C1', 'all')
    actions = [c for c in decision['test_plan']['cards'] if c['candidate_id'] == variant['id']]
    assert {c['metric'] for c in actions} == {'DS','strain','TSR','residual'}
    assert all(c['action'] == 'obtain_comparable_test' and c['conditions_to_confirm'] for c in actions)
