from copy import deepcopy
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from app.decision.records import DecisionRecord, digest, get_record
from app.services import latest_dataset

BASE = '/v5/design'


def run(client, case='C3', **changes):
    response = client.post(f'{BASE}/cases/{case}/runs', json={'request_id': uuid4().hex, **changes})
    assert response.status_code == 201, response.text
    return response.json()


def preference(decision, **changes):
    return {'decision_id': decision['id'], 'expected_decision_sha256': decision['sha256'],
            'priority_order': ['TSR'], **changes}


@pytest.mark.parametrize('case,count,status', [('C1', 2, 'numeric_feasible'), ('C2', 2, 'numeric_feasible'),
                                             ('C3', 5, 'numeric_feasible'), ('C4', 1, 'numeric_feasible'),
                                             ('C5', 0, 'evidence_insufficient')])
def test_case_runs_keep_same_scope_and_strong_baseline(client, case, count, status):
    result = run(client, case)
    assert len(result['decision']['results']) == 84
    assert len(result['baseline']['feasible_ids']) == count
    assert result['baseline']['same_feasible_set']
    assert result['decision']['diagnosis']['status'] == status
    assert all(t['source']['reference'] for t in result['explanation']['targets'])
    downloaded = client.get(f"{BASE}/records/{result['id']}/export.json").json()
    assert downloaded == result
    page = client.get(f"{BASE}/records/{result['id']}/print.html")
    assert page.status_code == 200 and result['sha256'] in page.text


def test_preference_changes_ranking_not_feasibility_or_original_snapshot(client, database):
    decision = run(client)['decision']; before = deepcopy(decision)
    tsr = client.post(BASE+'/preferences', json=preference(decision)).json()
    residual = client.post(BASE+'/preferences', json=preference(decision, priority_order=['residual'])).json()
    assert digest({k: v for k, v in residual.items() if k != 'sha256'}) == residual['sha256']
    assert tsr['comparison']['review_first_ids'] == ['mix_07e9acab4f8d5c4c21d0']
    assert residual['comparison']['review_first_ids'] == ['mix_59cb42163ce4719d7809']
    assert set(tsr['comparison']['feasible_ids']) == set(residual['comparison']['feasible_ids']) == set(decision['comparison']['feasible_ids'])
    assert len(residual['comparison']['front_ids']) == 5
    with Session(database) as session:
        assert get_record(session, decision['id']) == before
    for change in [{'priority_order': ['fatigue']}, {'priority_order': ['TSR', 'TSR']}, {'expected_decision_sha256': '0'*64}]:
        assert client.post(BASE+'/preferences', json=preference(decision, **change)).status_code in [409, 422]
    request = preference(decision, priority_order=['residual'], persist=True, request_id=uuid4().hex, reason='优先比较残留稳定度余量')
    saved = client.post(BASE+'/preferences', json=request).json()
    assert saved['kind'] == 'preference_comparison'
    assert client.post(BASE+'/preferences', json=request).json() == saved
    assert client.post(BASE+'/preferences', json={**request, 'reason': '另一个理由'}).status_code == 409


def test_resource_change_and_conflict_scope_are_explicit(client):
    base = run(client, 'C4'); changed = run(client, 'C4', rap_min_pct=75, adjustment_reason='比较更高名义RAP要求')
    assert len(base['decision']['comparison']['feasible_ids']) == 1
    assert changed['decision']['comparison']['feasible_ids'] == []
    assert changed['baseline']['same_feasible_set']
    assert base['decision']['demand']['request']['constraints']['rap_min_pct'] == 70
    complete = run(client, 'C5', evidence_view='complete_numeric_demo')
    assert len(complete['decision']['results']) == 35
    assert complete['decision']['diagnosis']['status'] == 'known_conflict'
    assert len(complete['decision']['diagnosis']['certificates']) == 4
    assert client.post(BASE+'/cases/C3/runs', json={'request_id': uuid4().hex, 'rap_min_pct': 75}).status_code == 422


def test_exact_parent_locks_and_draft_provenance(client, database):
    decision = run(client, 'C2')['decision']; parent = 'mix_ec30ff644f3111c570bc'
    endpoint = f"{BASE}/explorations/{decision['id']}/{parent}"
    context = client.get(endpoint).json()
    assert context['total_parent_hypotheses'] == 10 and context['total'] == 7
    assert all(r['parent_id'] == parent for r in context['items'])
    locked = client.get(endpoint, params=[('locked_fields', 'oil_stone_ratio_pct'), ('locked_fields', 'nominal_component_weights')]).json()
    assert locked['total'] == 0 and locked['items'] == []
    assert client.get(f"{BASE}/explorations/{decision['id']}/not-in-pool").status_code == 404
    request = {'request_id': uuid4().hex, 'origin_decision_id': decision['id'], 'expected_decision_sha256': decision['sha256'],
               'parent_recipe_id': parent, 'hypothesis_id': 'hyp_6e18d41dcaefa559',
               'locked_fields': ['nominal_component_weights'], 'design_intent': '比较油石比增加0.1个百分点的设计假设<script>bad()</script>',
               'research_scope_sha256': context['scope_sha256']}
    response = client.post(BASE+'/drafts', json=request)
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft['measured_performance'] is None and draft['inherits_parent_measurements'] is False
    assert draft['demand_context'] == decision['demand'] and draft['parent_recipe_id'] == parent
    assert draft['hypothesis']['parent']['metrics']['strain']['value'] == 2525
    assert draft['actual_changes']['oil_stone_ratio_pct'] == {'before': 4.9, 'after': 5.0, 'unit': '%'}
    assert client.post(BASE+'/drafts', json=request).json() == draft
    assert client.get(f"{BASE}/records/{draft['id']}/export.json").json() == draft
    page = client.get(f"{BASE}/records/{draft['id']}/print.html").text
    assert '<script>bad()' not in page and '&lt;script&gt;' in page and draft['sha256'] in page
    wrong_parent_hyp = {**request, 'request_id': uuid4().hex, 'hypothesis_id': 'hyp_8653a083f5ddc37f'}
    assert client.post(BASE+'/drafts', json=wrong_parent_hyp).status_code == 422
    locked_oil = {**request, 'request_id': uuid4().hex, 'locked_fields': ['oil_stone_ratio_pct']}
    assert client.post(BASE+'/drafts', json=locked_oil).status_code == 422
    stale_scope = {**request, 'request_id': uuid4().hex, 'research_scope_sha256': '0'*64}
    assert client.post(BASE+'/drafts', json=stale_scope).status_code == 409
    with Session(database) as session:
        assert get_record(session, decision['id']) == decision


def test_stale_decision_rejects_new_preference_and_draft(client, database):
    decision = run(client, 'C2')['decision']; parent = 'mix_ec30ff644f3111c570bc'
    context = client.get(f"{BASE}/explorations/{decision['id']}/{parent}").json()
    with Session(database) as session:
        dataset = latest_dataset(session); dataset.revision += 1; session.add(dataset); session.commit()
    assert client.post(BASE+'/preferences', json=preference(decision, priority_order=['strain'])).status_code == 409
    request = {'request_id': uuid4().hex, 'origin_decision_id': decision['id'], 'expected_decision_sha256': decision['sha256'],
               'parent_recipe_id': parent, 'hypothesis_id': 'hyp_6e18d41dcaefa559', 'design_intent': '检查过期版本拒绝新建',
               'research_scope_sha256': context['scope_sha256']}
    assert client.post(BASE+'/drafts', json=request).status_code == 409


def test_adjustment_preview_is_read_only_and_confirmation_creates_new_demand(client, database):
    initial = run(client, 'C4'); decision = initial['decision']
    with Session(database) as session:
        before_count = len(session.exec(select(DecisionRecord)).all())
    preview = client.post(f"{BASE}/decisions/{decision['id']}/adjustment-preview", json={
        'expected_decision_sha256': decision['sha256'], 'rap_min_pct': 75}).json()
    assert len(preview['before_feasible_ids']) == 1 and preview['after_feasible_ids'] == []
    with Session(database) as session:
        assert len(session.exec(select(DecisionRecord)).all()) == before_count
        assert get_record(session, decision['id']) == decision
    changed = run(client, 'C4', rap_min_pct=75, target_overrides={'strain': 2100},
                  adjustment_reason='比较更高再生要求并明确记录应变要求变化', based_on_decision_id=decision['id'],
                  expected_decision_sha256=decision['sha256'])
    assert changed['baseline']['same_feasible_set']
    assert changed['decision']['demand']['overrides'][0]['after']['value'] == 2100
    assert decision['demand']['request']['constraints']['rap_min_pct'] == 70
    boundary = client.post(f"{BASE}/decisions/{decision['id']}/adjustment-preview", json={
        'expected_decision_sha256': decision['sha256'], 'target_overrides': {'DS': 6260}}).json()
    assert boundary['after_feasible_ids'] == []  # R5 equals the strict greater-than target.
