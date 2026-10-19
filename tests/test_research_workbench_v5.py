from copy import deepcopy
import hashlib
import json

import numpy as np
from sqlmodel import Session, select

from app.decision.records import DecisionRecord
from app.decision.records import digest
from app.research_workbench.experiments import decide_heads
from app.research_workbench import service
from app.storage import Dataset, Measurement, Observation, Recipe


def request(client, **changes):
    body = {'title': '待确认配方试验计划', 'request_id': 'research-plan-test-001',
            'scope_sha256': client.get('/v4/research/overview').json()['scope_sha256'],
            'filters': {'source': 'H', 'kind': 'all', 'supported_only': True, 'q': ''}, 'budget': 3, 'pinned_ids': []}
    return body | changes


def test_research_overview_reports_regressions_and_distinct_validation_scopes(client):
    response = client.get('/v4/research/overview')
    assert response.status_code == 200, response.text
    value = response.json()
    assert value['compatibility']['matches']
    assert not value['production_model_promoted'] and value['independent_material_tests'] == 0
    assert value['latest_experiment']['repeats'] == 10 and value['previous_experiment']['repeats'] == 5
    assert value['latest_experiment']['exact_reproduction']
    assert any(row['relative_improvement'] < 0 for row in value['latest_experiment']['rows'])
    for row in value['latest_experiment']['rows']:
        assert np.isclose(row['relative_improvement'], 1-row['candidate_mae']/row['baseline_mae'])


def test_research_pagination_filter_and_untested_candidate_detail(client):
    supported = client.get('/v4/research/candidates').json()
    all_rows = client.get('/v4/research/candidates?supported_only=false').json()
    assert supported['total'] < all_rows['total']
    assert all(r['within_observed_support'] for r in supported['items'])
    next_page = client.get('/v4/research/candidates?offset=12').json()
    assert not {r['id'] for r in supported['items']} & {r['id'] for r in next_page['items']}
    filtered = client.get('/v4/research/candidates?source=H&kind=nominal_blend').json()
    assert filtered['total'] > 0
    assert all(r['source_code'] == 'H' and r['kind'] == 'nominal_blend' for r in filtered['items'])
    detail = client.get('/v4/research/candidates/'+filtered['items'][0]['id']).json()
    assert detail['candidate']['measured_performance'] is None
    assert not detail['candidate']['inherits_parent_measurements']
    assert not detail['summary']['engineering_release_allowed']
    assert np.isclose(sum(c['after'] for c in detail['components']), 1)
    assert detail['parent']['metrics']
    assert client.get('/v4/research/candidates?limit=1000').status_code == 422
    assert client.get('/v4/research/candidates?offset=-1').status_code == 422
    assert client.get('/v4/research/candidates/not-a-hypothesis').status_code == 404


def test_research_saved_plan_is_idempotent_immutable_and_keeps_new_performance_unknown(client, database):
    body = request(client)
    response = client.post('/v4/research/plans', json=body)
    assert response.status_code == 201, response.text
    plan = response.json()
    assert client.post('/v4/research/plans', json=body).json() == plan
    assert client.post('/v4/research/plans', json=body | {'budget': 2}).status_code == 409
    assert plan['selected_formulations'] == 3 and plan['laboratory_results'] is None
    assert not plan['engineering_release_allowed'] and plan['actual_specimen_count'] is None
    for f in plan['formulations']:
        assert f['candidate']['measured_performance'] is None
        assert not f['candidate']['inherits_parent_measurements']
    printed = client.get(f"/v4/research/plans/{plan['id']}/print.html").text
    assert plan['sha256'] in printed and plan['created_at'] in printed
    assert client.get(f"/v4/research/plans/{plan['id']}").json() == plan
    with Session(database) as s:
        ds = s.get(Dataset, plan['currentness_at_creation']['current']['id'])
        ds.revision += 1; s.add(ds); s.commit()
        assert len(s.exec(select(DecisionRecord).where(DecisionRecord.kind == 'research_test_plan')).all()) == 1
        assert len(s.exec(select(Observation)).all()) == 0
        assert all(r.kind == 'historical' for r in s.exec(select(Recipe)).all())
    assert not client.get('/v4/research/overview').json()['compatibility']['matches']
    assert client.post('/v4/research/plans', json=body | {'request_id': 'research-plan-test-002'}).status_code == 409
    assert client.post('/v4/research/plans', json=body).json() == plan
    assert client.get(f"/v4/research/plans/{plan['id']}/print.html").text == printed


def test_research_plan_rejects_stale_scope_bad_pins_and_escapes_user_title(client):
    assert client.post('/v4/research/plans', json=request(client, scope_sha256='0'*64)).status_code == 409
    assert client.post('/v4/research/plans', json=request(client, pinned_ids=['outside'])).status_code == 422
    first = client.get('/v4/research/candidates?source=H').json()['items'][0]['id']
    assert client.post('/v4/research/plans', json=request(client, pinned_ids=[first, first])).status_code == 422
    response = client.post('/v4/research/plans', json=request(client, title='<script>alert(1)</script> & research'))
    assert response.status_code == 201, response.text
    output = client.get('/v4/research/plans/'+response.json()['id']+'/print.html').text
    assert '<script>alert(1)</script>' not in output and '&lt;script&gt;alert(1)&lt;/script&gt;' in output


def test_research_export_preserves_server_numeric_representation_for_snapshot_hash(client):
    plan = client.post('/v4/research/plans', json=request(client)).json()
    response = client.get('/v4/research/plans/'+plan['id']+'/export.json')
    assert response.status_code == 200 and response.headers['content-type'].startswith('application/json')
    assert 'attachment;' in response.headers['content-disposition']
    exported = response.json()
    assert exported == plan
    assert digest({k: v for k, v in exported.items() if k != 'sha256'}) == exported['sha256']
    browser_reserialized = json.loads(json.dumps(exported), parse_float=lambda x: int(float(x)) if float(x).is_integer() else float(x))
    assert browser_reserialized == plan
    assert digest({k: v for k, v in browser_reserialized.items() if k != 'sha256'}) != exported['sha256']


def test_research_download_allowlist_hash_and_source_audit(client):
    response = client.get('/v4/research/evidence/lab_handoff')
    assert response.status_code == 200
    assert hashlib.sha256(response.content).hexdigest() == service.registry()['evidence']['lab_handoff']['sha256']
    assert client.get('/v4/research/evidence/baseline').status_code == 404
    assert client.get('/v4/research/evidence/not-registered').status_code == 404
    audit = client.get('/v4/research/audit').json()
    assert audit['groups_with_observed_conflict'] < audit['input_alias_groups']
    assert any(any(e['curve_input_masked'] for e in issue['entries']) for issue in audit['issues'])
    assert all(r['source_row_exists'] for i in audit['issues'] for e in i['entries'] for m in e['labels'].values() for r in m['references'])
    assert all(q['answer'] is None for i in audit['issues'] for q in i['questions'])


def test_research_tampered_evidence_fails_closed(client, monkeypatch, tmp_path):
    registered = deepcopy(service.registry())
    fake = tmp_path/'tampered.json'; fake.write_text('{"hypotheses":[]}', encoding='utf-8')
    registered['evidence']['candidate_pool']['path'] = 'tampered.json'
    config_file = tmp_path/'registry.json'; config_file.write_text(json.dumps(registered), encoding='utf-8')
    monkeypatch.setattr(service, 'ROOT', tmp_path)
    monkeypatch.setattr(service, 'REGISTRY_PATH', config_file)
    result = client.get('/v4/research/candidates')
    assert result.status_code == 409 and '指纹' in result.json()['detail']


def test_research_space_coverage_does_not_use_performance_predictions_or_hidden_labels():
    data = service.frozen_data()
    pool = service.filtered_candidates({'source': 'H', 'kind': 'all', 'supported_only': True})[:30]
    groups = dict(zip(data['ids'], data['groups'].tolist()))
    first = service.select_diverse_designs(data['X'], pool, groups, 3, [pool[0]['id']])[0]
    changed = deepcopy(pool)
    for r in changed:
        r['prediction'] = {m: -1e12 for m in ['DS', 'strain', 'TSR', 'residual']}
        r['measured_performance'] = {m: 1e12 for m in ['DS', 'strain', 'TSR', 'residual']}
    second = service.select_diverse_designs(data['X'], changed, groups, 3, [pool[0]['id']])[0]
    assert [r['id'] for r in first] == [r['id'] for r in second]
    assert first[0]['id'] == pool[0]['id']


def test_head_fallback_rejects_unsupported_model_and_accepts_clear_training_only_signal():
    Y = np.arange(48, dtype=float).reshape(12, 4)
    base = Y+2; groups = np.repeat(np.arange(6), 2)
    _, accepted_bad, _ = decide_heads(Y, base, np.array([Y+10]), groups, np.random.default_rng(4))
    _, accepted_good, _ = decide_heads(Y, base, np.array([Y]), groups, np.random.default_rng(4))
    assert accepted_bad == [False]*4 and accepted_good == [True]*4
