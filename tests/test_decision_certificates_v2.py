from copy import deepcopy

from app.decision.diagnosis import diagnose, verify_certificate
from decision_helpers import run_case


def test_c5_reproduces_four_verified_minimal_conflicts(client):
    decision = run_case(client)
    diagnosis = decision['diagnosis']
    assert diagnosis['status'] == 'known_conflict'
    assert len(decision['results']) == 35
    pairs = {frozenset(r['metric'] for r in cert['requirements']) for cert in diagnosis['certificates']}
    assert pairs == {frozenset(x) for x in [('DS', 'strain'), ('DS', 'TSR'), ('DS', 'residual'), ('strain', 'TSR')]}
    for cert in diagnosis['certificates']:
        assert cert['minimality_status'] == 'verified_inclusion_minimal'
        assert verify_certificate(cert, decision['results'], decision['pool_sha256'], decision['confirmation_sha256'], decision['demand'])['valid']
        bad = deepcopy(cert)
        bad['deletion_witnesses'][0]['candidate_id'] = 'does-not-exist'
        assert not verify_certificate(bad, decision['results'], decision['pool_sha256'], decision['confirmation_sha256'], decision['demand'])['valid']


def test_unknown_is_not_evidence_of_no_solution_and_empty_pool_distinct():
    demand = {'sha256': 'demand', 'ready_for_candidate_retrieval': True, 'request': {'context_kind': 'constructed_demo'}, 'targets': []}
    result = {'id': 'a', 'display_id': 'A', 'passes_known_requirements': False, 'failed_targets': [],
              'checks': [{'target_id': 'DS', 'state': 'missing', 'value': None}]}
    assert diagnose([result], demand, 'pool')['status'] == 'evidence_insufficient'
    assert diagnose([], demand, 'pool')['status'] == 'pool_empty'
