from copy import deepcopy


def test_three_scene_to_confirmation_flows_and_immutable_override(client):
    profiles = client.get('/v2/scene-profiles').json()['profiles']
    for profile in profiles:
        response = client.post('/v2/demand-resolutions', json=profile['example_request'])
        assert response.status_code == 201
        original = response.json()
        assert original['requirements_complete']
        target = original['targets'][0]
        replacement = {k: v for k, v in target.items() if k not in ['target_id', 'derived_by']}
        replacement['value'] += 1
        replacement['source'] = {'kind': 'project_target', 'reference': '工程师演示覆盖', 'confirmed': False}
        confirmation = client.post(f"/v2/demand-resolutions/{original['id']}/confirm", json={
            'expected_sha256': original['sha256'], 'confirmed_by': '开发自测',
            'overrides': [{'target_id': target['target_id'], 'requirement': replacement, 'reason': '验证覆盖审计记录'}],
        })
        assert confirmation.status_code == 201
        saved = confirmation.json()
        assert saved['overrides'][0]['before']['value'] == target['value']
        assert saved['targets'][0]['value'] == target['value'] + 1
        assert client.get('/v2/records/' + original['id']).json() == original
        assert client.post(f"/v2/demand-resolutions/{original['id']}/confirm", json={
            'expected_sha256': '0' * 64, 'confirmed_by': '开发自测',
        }).status_code == 409


def test_unknown_scene_and_unsupported_requirements_stay_visible(client):
    data = deepcopy(client.get('/v2/scene-profiles').json()['profiles'][0]['example_request'])
    data['scene']['traffic']['class'] = None
    data['requested_metrics'].append('fatigue_life')
    resolved = client.post('/v2/demand-resolutions', json=data).json()
    assert not resolved['requirements_complete']
    assert not resolved['targets']
    assert resolved['capability_gaps'][0]['metric'] == 'fatigue_life'
    assert any(x.get('metric') == 'fatigue_life' for x in resolved['open_items'])
    confirmed = client.post(f"/v2/demand-resolutions/{resolved['id']}/confirm", json={
        'expected_sha256': resolved['sha256'], 'confirmed_by': '开发自测',
    }).json()
    assert not confirmed['ready_for_candidate_retrieval']


def test_formal_conditions_not_merged_and_real_contradiction_reported(client):
    data = client.get('/v2/scene-profiles').json()['profiles'][0]['example_request']
    data['context_kind'] = 'project'
    base = {'metric': 'DS', 'operator': '>', 'value': 800, 'unit': '次/mm', 'test_method': 'METHOD-A',
            'conditions': {'temperature': '60C'}, 'source': {'kind': 'project_target', 'reference': '仅为接口测试'}}
    data['project_targets'] = [base, {**base, 'operator': '<=', 'value': 800}]
    data['requested_metrics'] = ['DS']
    resolved = client.post('/v2/demand-resolutions', json=data).json()
    assert len(resolved['conflicts']) == 1 and not resolved['requirements_complete']
    data['project_targets'][1]['conditions'] = {'temperature': '50C'}
    resolved = client.post('/v2/demand-resolutions', json=data).json()
    assert len(resolved['targets']) == 2 and not resolved['conflicts']
