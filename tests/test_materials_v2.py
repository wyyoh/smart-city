def test_material_card_preserves_unknown_composition_and_source_paths(client):
    options = client.get('/v2/material-options').json()
    assert len(options['product_versions']) == 180
    for profile in client.get('/v2/scene-profiles').json()['profiles']:
        resolution = client.post('/v2/demand-resolutions', json=profile['example_request']).json()
        confirmed = client.post(f"/v2/demand-resolutions/{resolution['id']}/confirm", json={
            'expected_sha256': resolution['sha256'], 'confirmed_by': '开发自测',
        }).json()
        result = client.get('/v2/materials/R1', params={'confirmation_id': confirmed['id']}).json()
        assert result['fields']['modifier']['value'] is None
        assert result['fields']['additive']['value'] is None
        assert result['fields']['mixing_window']['value'] is None
        assert result['fields']['rap_nominal_pct']['status'] == 'mass_basis_unconfirmed'
        assert len(result['relation_paths']) == 4
        assert all(path['sources'] and path['observation_id'] for path in result['relation_paths'])
        assert result['fields']['product']['value'] == '70#'
