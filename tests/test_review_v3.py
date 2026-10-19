from copy import deepcopy
import hashlib
import json

from scripts.compare_cases_v2 import execute_case


def decision(client, case='C1', view='all'):
    selected = next(c for c in client.get('/v2/benchmark-cases').json()['cases'] if c['id'] == case)
    return execute_case(client, selected, view)[1]


def save(client, value, request_id='review-test-001'):
    response = client.post('/v2/review/reports', json={'decision_id': value['id'], 'request_id': request_id})
    assert response.status_code == 201, response.text
    return response.json()


def test_competition_index_preserves_basic_technical_bonus_and_live_identity(client):
    result = client.get('/v2/review/overview').json()
    assert [sum(r['kind'] == kind for r in result['requirements']) for kind in ['basic', 'technical_detail', 'bonus']] == [5, 10, 7]
    assert result['official_scoring_weights'] is None
    assert result['current_data']['historical_keys'] == 180
    assert result['current_data']['ac13_keys'] == 84
    assert result['current_data']['complete_four_metric_ac13_keys'] == 35
    assert result['human_participants'] == 0
    assert all(e['integrity'] == 'verified' for e in result['evidence'].values())
    assert client.get('/v2/review/evidence/not-an-allowed-id').status_code == 404


def test_announcements_do_not_authorize_thresholds_or_backfill_tests(client):
    result = client.get('/v2/review/sources').json()['sources']
    assert len(result) == 2
    assert all(s['thresholds_authorized'] is False for s in result)
    assert result[1]['effective_date'] == '2025-10-01'
    assert result[1]['notice_date'] != result[1]['page_publication_date']


def test_review_separates_numeric_satisfaction_from_engineering_release(client):
    value = decision(client)
    review = save(client, value)
    assert review['decision_sha256'] == value['sha256']
    assert review['numerical_summary']['candidate_count'] == 84
    assert review['numerical_summary']['feasible_count'] == 2
    assert review['engineering_release_approved'] is False
    assert review['value_validation']['human_timing'] is None
    assert review['focus_candidates']
    assert all(c['engineering_release_approved'] is False for c in review['focus_candidates'])
    assert all(c['material_unknowns'] for c in review['focus_candidates'])
    assert all(t['issues'] for t in review['requirements'])
    assert {a['id'] for a in review['actions']} >= {'scene', 'requirements', 'identity', 'applicability', 'release'}
    raw = {r['id']: r for r in value['results']}
    for candidate in review['focus_candidates']:
        for check in candidate['checks']:
            evidence = raw[candidate['id']]['evidence'].get(check['metric'], {})
            assert check['source_count'] == len(evidence.get('raw_labels', []))
            assert check['source_preview'] or check['source_count'] == 0


def test_review_preserves_missing_vs_pool_scoped_conflict(client):
    full = save(client, decision(client, 'C5'), 'review-full-001')
    limited = save(client, decision(client, 'C5', 'complete_numeric_demo'), 'review-limited-001')
    assert full['diagnosis']['status'] == 'evidence_insufficient'
    assert not full['certificate_checks']
    assert full['numerical_summary']['candidate_count'] == 84
    assert limited['numerical_summary']['candidate_count'] == 35
    assert len(limited['certificate_checks']) == 4
    assert all(c['valid'] for c in limited['certificate_checks'])
    assert limited['focus_candidates'] == []
    assert limited['engineering_release_approved'] is False


def test_saved_review_and_export_are_immutable_and_idempotent(client):
    value = decision(client)
    first = save(client, value)
    second = save(client, value)
    assert first == second
    url = f"/v2/review/reports/{first['id']}"
    html = client.get(url + '/report.html').text
    assert first['review_sha256'] in html and first['decision_sha256'] in html
    assert first['generated_at'] in html
    assert client.get(url).json() == first
    parent = value['results'][0]['id']
    changed = client.post(f'/v1/recipes/{parent}/variants', json={'oil_stone_ratio_pct': 5.3, 'note': '隔离测试创建新版本，不写入真实试验'})
    assert changed.status_code == 201, changed.text
    fresh = client.get(f"/v2/review/decisions/{value['id']}").json()
    assert fresh['status'] == 'stale'
    assert client.get(url + '/report.html').text == html
    assert client.get(url).json() == first
    other = decision(client, 'C2')
    response = client.post('/v2/review/reports', json={'decision_id': other['id'], 'request_id': 'review-test-001'})
    assert response.status_code == 409


def test_review_rejects_wrong_candidate_and_escapes_user_text(client):
    selected = deepcopy(client.get('/v2/benchmark-cases').json()['cases'][0])
    selected['example_request']['name'] = '<script>alert(1)</script> & review'
    value = execute_case(client, selected)[1]
    review = save(client, value)
    html = client.get(f"/v2/review/reports/{review['id']}/report.html").text
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html
    assert client.get(f"/v2/review/decisions/{value['id']}?candidate_id=outside-pool").status_code == 404
    assert client.get(f"/v2/review/reports/{value['id']}").status_code == 404


def test_external_template_has_no_human_or_fabricated_completed_evidence(client):
    blank = client.get('/v2/review/validation-template').json()
    result = client.post('/v2/review/validate-input', json=blank).json()
    assert result['schema_valid'] is True
    assert result['collection_complete'] is False
    assert result['authenticity_verified'] is False
    assert result['human_participants'] == 0
    assert result['human_effective_times'] == []


def test_external_timing_rejects_ai_and_invalid_time_and_requires_pairing(client):
    blank = client.get('/v2/review/validation-template').json()
    task = {'participant_id': 'fixture-human', 'actor': 'AI', 'task': 'routine_selection', 'workflow': 'V2',
            'background': 'synthetic fixture only', 'order': 1, 'started_at': '2026-10-19T10:00:00+08:00',
            'ended_at': '2026-10-19T10:01:00+08:00', 'operations': 3, 'omission_count': 0,
            'trace_complete': True, 'log_reference': 'fixture/not-real'}
    blank['human_tasks'] = [task]
    assert client.post('/v2/review/validate-input', json=blank).json()['schema_valid'] is False
    task['actor'] = 'human'
    task['ended_at'] = task['started_at']
    assert client.post('/v2/review/validate-input', json=blank).json()['schema_valid'] is False
    task['ended_at'] = '2026-10-19T10:01:00+08:00'
    task['interruption_seconds'] = 10
    result = client.post('/v2/review/validate-input', json=blank).json()
    assert result['schema_valid'] is True
    assert result['human_effective_times'][0]['effective_seconds'] == 50
    assert result['collection_complete'] is False
    assert result['authenticity_verified'] is False
    assert any('三流程' in item['message'] for item in result['issues'])


def test_review_evidence_reports_changes_and_refuses_paths_outside_registered_root(client, monkeypatch, tmp_path):
    from app.review import registry as module
    data = module.registry()
    original_root = module.ROOT
    (tmp_path / 'configs').mkdir()
    proof = tmp_path / 'proof.txt'
    proof.write_text('registered evidence', encoding='utf-8')
    data['evidence'] = {'proof': {'id': 'proof', 'label': 'proof.txt', 'path': 'proof.txt',
                                  'sha256': hashlib.sha256(proof.read_bytes()).hexdigest()}}
    (tmp_path / 'configs/review_evidence_v3.json').write_text(json.dumps(data), encoding='utf-8')
    fallback = tmp_path / 'artifacts/next-phase/case-reports'
    fallback.mkdir(parents=True)
    (fallback / 'summary.json').write_text('{"cases":[]}', encoding='utf-8')
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    assert client.get('/v2/review/overview').json()['evidence']['proof']['integrity'] == 'verified'
    proof.write_text('changed evidence', encoding='utf-8')
    assert client.get('/v2/review/overview').json()['evidence']['proof']['integrity'] == 'changed'
    data['evidence']['proof']['path'] = str(original_root / 'README.md')
    (tmp_path / 'configs/review_evidence_v3.json').write_text(json.dumps(data), encoding='utf-8')
    assert client.get('/v2/review/evidence/proof').status_code == 404
