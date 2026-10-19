from copy import deepcopy
import importlib.util

from app.settings import ROOT


def exercise(client):
    spec = importlib.util.spec_from_file_location('mock_upstream_v2', ROOT/'scripts/mock_upstream_v2.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.exercise(client, 'test-local-v2')


def test_upstream_round_trip_feedback_idempotence_scope_and_versions(client):
    result = exercise(client)
    assert client.post('/v2/upstream-requests', json=result['request']).json()['id'] == result['upstream']['id']
    different = deepcopy(result['request']); different['segment_id'] = 'wrong-segment'
    assert client.post('/v2/upstream-requests', json=different).status_code == 409
    lab = result['lab_input']
    assert client.post('/v2/lab-feedback', json=lab).json()['id'] == result['lab_submission']['id']
    different = {**lab, 'value': 9100}
    assert client.post('/v2/lab-feedback', json=different).status_code == 409
    different = {**lab, 'idempotency_key': 'wrong-version-001', 'material_version': 'not-this-version'}
    assert client.post('/v2/lab-feedback', json=different).status_code == 409
    different = {**lab, 'idempotency_key': 'wrong-scope-0001', 'data_scope': 'official'}
    assert client.post('/v2/lab-feedback', json=different).status_code == 422
    assert client.post('/v2/feedback/'+result['field_submission']['id']+'/review', json={
        'state': 'approved', 'reviewer': 'AI test', 'note': '现场反馈不能变实验室指标', 'conditions_confirmed': True, 'use_for_decision': True}).status_code == 422
    cid = lab['candidate_id']
    assert client.get('/v1/recipes/'+cid+'?context_kind=constructed_demo').json()['metrics']['DS'] == 9000
    assert client.get('/v1/recipes/'+cid).json()['metrics']['DS'] != 9000
    evidence = client.get('/v1/recipes/'+cid+'?context_kind=constructed_demo').json()['evidence']['DS']
    assert evidence['structured_conditions'] == lab['conditions']
