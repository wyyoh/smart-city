from copy import deepcopy

from app.decision.diagnosis import verify_certificate
from app.decision.records import digest
from decision_helpers import run_case


def test_recomputed_hash_does_not_hide_wrong_certificate_definition_or_witness(client):
    decision=run_case(client)
    certificate=deepcopy(decision['diagnosis']['certificates'][0])
    certificate['requirements'][0]['value']+=1
    certificate['certificate_sha256']=digest({k:v for k,v in certificate.items() if k!='certificate_sha256'})
    result=verify_certificate(certificate,decision['results'],decision['pool_sha256'],decision['confirmation_sha256'],decision['demand'])
    assert not result['valid'] and 'requirement_definition_mismatch' in result['errors']
    certificate=deepcopy(decision['diagnosis']['certificates'][0])
    certificate['deletion_witnesses'][0]['remaining_checks'][0]['value']=-1
    certificate['certificate_sha256']=digest({k:v for k,v in certificate.items() if k!='certificate_sha256'})
    result=verify_certificate(certificate,decision['results'],decision['pool_sha256'],decision['confirmation_sha256'],decision['demand'])
    assert not result['valid'] and 'witness_evidence_mismatch' in result['errors']


def test_new_generation_rejects_changed_pool_but_old_report_replays(client):
    decision=run_case(client,'C1','all')
    client.post('/v1/recipes/R1/variants',json={'oil_stone_ratio_pct':5.6,'note':'冻结后变更候选目录'})
    response=client.post('/v2/decisions',json={'pool_id':decision['pool_id']})
    assert response.status_code==409
    assert client.get('/v2/records/'+decision['id']).json()==decision
