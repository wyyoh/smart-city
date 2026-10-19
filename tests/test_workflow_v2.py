from decision_helpers import run_case


def test_full_flow_variant_and_next_validation_preserve_prior_snapshot(client):
    old = run_case(client, 'C1', 'all')
    variant = client.post('/v1/recipes/R1/variants', json={'oil_stone_ratio_pct': 5.6, 'note': '隔离验收：材料新版本'}).json()
    pool = client.post('/v2/candidate-pools', json={'confirmation_id': old['confirmation_id']}).json()
    result = client.post('/v2/decisions', json={'pool_id': pool['id']}).json()
    row = next(r for r in result['results'] if r['id'] == variant['id'])
    assert row['status'] == 'needs_evidence' and not row['metrics'] and not row['evidence']
    assert {c['metric'] for c in result['test_plan']['cards'] if c['candidate_id'] == row['id']} == {'DS', 'strain', 'TSR', 'residual'}
    assert client.get('/v2/records/' + old['id']).json() == old
    assert any(r['id'] == result['id'] for r in client.get('/v2/decisions').json())
