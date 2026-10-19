from decision_helpers import run_case
from test_core import observation


def test_own_fold_oof_is_distinct_from_full_fit_and_hard_decision(client):
    decision = run_case(client, 'C1')
    row = next(r for r in decision['results'] if r['display_id'] == 'R1')
    response = client.get(f"/v2/decisions/{decision['id']}/models/{row['id']}")
    assert response.status_code == 200
    view = response.json()
    assert view['status'] == 'research_only' and len(view['metrics']) == 4
    assert all(m['own_fold_oof'] and m['research_fitted_prediction'] for m in view['metrics'])
    assert all(not m['beats_dummy_mae'] for m in view['metrics'])
    assert client.get('/v2/records/' + decision['id']).json() == decision
    item = client.post('/v1/observations', json=observation(client, data_scope='official', idempotency_key='v2-model-stale-001')).json()
    client.post('/v1/observations/'+item['id']+'/review', json={'state':'approved','reviewer':'自测','note':'版本核验','conditions_confirmed':True,'use_for_recommendation':True})
    view = client.get(f"/v2/decisions/{decision['id']}/models/{row['id']}").json()
    assert view['research_prediction_reason'] and all(m['research_fitted_prediction'] is None for m in view['metrics'])
