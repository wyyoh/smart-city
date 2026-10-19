def run_case(client, case='C5', evidence_view='complete_numeric_demo'):
    old = next(c for c in client.get('/v1/cases').json() if c['id'] == case)['scenario']
    index = {'C1': 0, 'C2': 1, 'C3': 2, 'C4': 0, 'C5': 0}[case]
    request = client.get('/v2/scene-profiles').json()['profiles'][index]['example_request']
    request['name'] = old['name']
    if case == 'C4':
        request['constraints']['rap_min_pct'] = 70
    resolved = client.post('/v2/demand-resolutions', json=request).json()
    overrides = []
    for target in resolved['targets']:
        desired = next(t for t in old['targets'] if t['metric'] == target['metric'])
        if target['value'] != desired['value']:
            replacement = {k: v for k, v in target.items() if k not in ['target_id', 'derived_by']}
            replacement['value'] = desired['value']
            replacement['source'] = {'kind': 'constructed_demo', 'reference': f'冻结演示案例{case}的团队设定', 'confirmed': False}
            overrides.append({'target_id': target['target_id'], 'requirement': replacement, 'reason': f'构造案例{case}目标，不代表规范'})
    confirmed = client.post(f"/v2/demand-resolutions/{resolved['id']}/confirm", json={
        'expected_sha256': resolved['sha256'], 'confirmed_by': '自动化开发验证', 'overrides': overrides}).json()
    pool = client.post('/v2/candidate-pools', json={'confirmation_id': confirmed['id'], 'evidence_view': evidence_view}).json()
    response = client.post('/v2/decisions', json={'pool_id': pool['id']})
    assert response.status_code == 201, response.text
    return response.json()
