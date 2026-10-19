from decision_helpers import run_case


def test_variant_detects_changed_pool_without_altering_old_report(client):
    decision = run_case(client, 'C1', 'all')
    assert client.get(f"/v2/decisions/{decision['id']}/freshness").json()['current']
    variant = client.post('/v1/recipes/R1/variants', json={'oil_stone_ratio_pct': 5.6, 'note': '校验证据失效'}).json()
    freshness = client.get(f"/v2/decisions/{decision['id']}/freshness").json()
    assert not freshness['current'] and variant['id'] in freshness['candidate_changes']['added']
    assert client.get('/v2/records/' + decision['id']).json() == decision
    source = next(r for r in decision['results'] if r['display_id'] == 'R1')['evidence']['DS']['raw_labels'][0]
    raw = client.get(f"/v1/evidence/{decision['scope']['dataset']['id']}/{source['sheet']}/{source['row']}")
    assert raw.status_code == 200 and source['cell'] in raw.json()['payload']['cells']
