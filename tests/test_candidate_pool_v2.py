def confirm(client, request):
    result = client.post('/v2/demand-resolutions', json=request).json()
    response = client.post(f"/v2/demand-resolutions/{result['id']}/confirm", json={
        'expected_sha256': result['sha256'], 'confirmed_by': '开发自测'})
    assert response.status_code == 201
    return response.json()


def test_full_catalogue_pool_freeze_empty_inventory_and_replay(client):
    request = client.get('/v2/scene-profiles').json()['profiles'][0]['example_request']
    request['inventory']['gradation_family'] = None
    demand = confirm(client, request)
    pool = client.post('/v2/candidate-pools', json={'confirmation_id': demand['id']}).json()
    assert pool['summary']['included'] == pool['summary']['catalogue_total'] == 180
    assert len(pool['candidate_ids']) > 9
    assert not pool['scope']['inventory_confirmed']
    assert client.get('/v2/records/' + pool['id']).json() == pool
    request['inventory']['source_codes'] = []
    demand = confirm(client, request)
    empty = client.post('/v2/candidate-pools', json={'confirmation_id': demand['id']}).json()
    assert not empty['candidate_ids'] and len(empty['excluded']) == 180
    assert all('source_not_in_inventory' in r['reasons'] for r in empty['excluded'])


def test_complete_diagnostic_scope_is_explicit_and_repeatable(client):
    request = client.get('/v2/scene-profiles').json()['profiles'][0]['example_request']
    demand = confirm(client, request)
    body = {'confirmation_id': demand['id'], 'evidence_view': 'complete_numeric_demo'}
    pool = client.post('/v2/candidate-pools', json=body).json()
    assert pool['summary']['included'] == 35
    repeat = client.post('/v2/candidate-pools', json=body).json()
    assert pool['pool_sha256'] == repeat['pool_sha256']
    assert any('incomplete_numeric_demo_scope' in r['reasons'] for r in pool['excluded'])
