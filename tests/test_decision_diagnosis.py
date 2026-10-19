from copy import deepcopy
import json

import pytest

from app.decision.constraints import assess_recipe, satisfies
from app.decision.comparison import compare_feasible
from app.decision.diagnosis import diagnose, verify_certificate
from app.decision.eligibility import evidence_eligibility, resource_eligibility
from app.settings import ROOT
from decision_helpers import run_case
from test_candidate_pool_v2 import confirm
from test_core import observation
from test_eligibility_v2 import example


CASES = json.loads((ROOT / 'configs/next_phase_negative_cases.json').read_text(encoding='utf-8'))['cases']


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_registered_negative(case, client):
    identifier = case['id']
    data = client.get('/v2/scene-profiles').json()['profiles'][0]['example_request']
    if identifier == 'NEG01':
        data['scene']['climate']['class'] = None
        result = client.post('/v2/demand-resolutions', json=data).json()
        assert not result['targets'] and not result['requirements_complete']
        assert any(i.get('field') == 'climate.class' for i in result['open_items'])
    elif identifier == 'NEG02':
        data['scene']['distress']['type'] = 'other_cracking'
        result = client.post('/v2/demand-resolutions', json=data).json()
        assert not result['rules']['matches'] and not result['targets']
    elif identifier == 'NEG03':
        request, target, recipe = example()
        recipe['evidence']['DS']['method'] = 'incompatible-method'
        result = evidence_eligibility(recipe, target, request)
        assert result['status'] == 'inapplicable' and not result['numeric_comparison_allowed']
    elif identifier == 'NEG04':
        data['requested_metrics'] += ['PG_grade', 'fatigue_life', 'dynamic_modulus']
        result = client.post('/v2/demand-resolutions', json=data).json()
        assert {g['metric'] for g in result['capability_gaps']} == {'PG_grade', 'fatigue_life', 'dynamic_modulus'}
        assert not result['requirements_complete'] and len(result['request']['requested_metrics']) == 7
    elif identifier == 'NEG05':
        request, _, recipe = example()
        result = resource_eligibility(recipe, request)
        assert next(c for c in result if c['key'] == 'budget')['state'] == 'missing'
    elif identifier == 'NEG06':
        data['inventory']['source_codes'] = []
        demand = confirm(client, data)
        pool = client.post('/v2/candidate-pools', json={'confirmation_id': demand['id']}).json()
        decision = client.post('/v2/decisions', json={'pool_id': pool['id']}).json()
        assert decision['diagnosis']['status'] == 'pool_empty' and not decision['diagnosis']['certificates']
    elif identifier == 'NEG07':
        demand = confirm(client, data)
        variant = client.post('/v1/recipes/R1/variants', json={'oil_stone_ratio_pct': 5.6, 'note': '负例：不继承父实测'}).json()
        result = assess_recipe(variant, demand)
        assert all(c['state'] == 'missing' for c in result['checks'])
        assert diagnose([result], demand, 'isolated-pool')['status'] == 'evidence_insufficient'
    elif identifier == 'NEG08':
        assert not satisfies(800, {'operator': '>', 'value': 800})
        assert satisfies(800, {'operator': '>=', 'value': 800})
        assert not satisfies(800, {'operator': '<', 'value': 800})
        assert satisfies(800, {'operator': '<=', 'value': 800})
        assert satisfies(800, {'operator': 'between', 'value': 800, 'upper': 900})
        assert satisfies(900, {'operator': 'between', 'value': 800, 'upper': 900})
    elif identifier == 'NEG09':
        a = {'id': 'a', 'passes_known_requirements': True, 'checks': [{'target_id': 'DS', 'value': 900}]}
        b = deepcopy(a); b['id'] = 'b'
        result = compare_feasible([b, a], {'priority': ['DS'], 'targets': [{'target_id': 'DS', 'metric': 'DS', 'operator': '>'}]})
        assert result['review_first_ids'] == ['a', 'b'] and a['tied_with'] == ['b']
    elif identifier == 'NEG10':
        old = run_case(client, 'C1')
        variant = client.post('/v1/recipes/R1/variants', json={'oil_stone_ratio_pct': 5.6, 'note': '检查快照不可变'}).json()
        assert not variant['metrics'] and not variant['evidence']
        assert client.get('/v2/records/' + old['id']).json() == old
        resolution = client.post('/v2/demand-resolutions', json=data).json()
        assert client.post(f"/v2/demand-resolutions/{resolution['id']}/confirm", json={'expected_sha256': '0'*64, 'confirmed_by': '自测'}).status_code == 409
    elif identifier == 'NEG11':
        item = client.post('/v1/observations', json=observation(client, idempotency_key='negative-scope-0001')).json()
        review = {'state': 'approved', 'reviewer': '自测', 'note': '隔离库验证', 'conditions_confirmed': True, 'use_for_recommendation': True}
        assert client.post('/v1/observations/' + item['id'] + '/review', json=review).status_code == 200
        assert client.get('/v1/recipes/R1').json()['metrics']['DS'] != 12000
        assert client.get('/v1/recipes/R1?context_kind=constructed_demo').json()['metrics']['DS'] == 12000
        official = client.post('/v1/observations', json=observation(client, data_scope='official', idempotency_key='negative-model-0001')).json()
        assert client.post('/v1/observations/' + official['id'] + '/review', json=review).status_code == 200
        assert client.post('/v1/predictions/R1', json={}).status_code == 409
    elif identifier == 'NEG12':
        decision = run_case(client)
        assert len(decision['diagnosis']['certificates']) == 4
        assert all(verify_certificate(cert, decision['results'], decision['pool_sha256'], decision['confirmation_sha256'], decision['demand'])['valid'] for cert in decision['diagnosis']['certificates'])
        assert not decision['comparison']['feasible_ids']
