"""Run a local-only upstream/selection/lab/field contract rehearsal in an isolated database."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

sys.path.insert(0, str(ROOT / 'scripts'))
from v2_isolation import copy_baseline

from fastapi.testclient import TestClient
from app.main import create_app
from app.storage import make_engine


def exercise(client, prefix='local-mock-v2'):
    trace = []
    def post(path, body):
        start = time.perf_counter()
        response = client.post('/v2' + path, json=body)
        assert response.status_code == 201, response.text
        data = response.json()
        trace.append({'path': path, 'status_code': response.status_code, 'elapsed_ms': round(1000 * (time.perf_counter() - start), 3),
                      'record_id': data['id'], 'sha256': data['sha256']})
        return data
    request = {'request_id': prefix+'-request', 'decision_id': prefix+'-decision', 'segment_id': 'demo-section-001',
               'demand': client.get('/v2/scene-profiles').json()['profiles'][0]['example_request']}
    upstream = post('/upstream-requests', request)
    resolution = client.get('/v2/records/' + upstream['resolution_id']).json()
    confirmation = post(f"/demand-resolutions/{resolution['id']}/confirm", {'expected_sha256': resolution['sha256'], 'confirmed_by': 'AI local mock'})
    pool = post('/candidate-pools', {'confirmation_id': confirmation['id']})
    decision = post('/decisions', {'pool_id': pool['id']})
    row = next(r for r in decision['results'] if r['id'] == decision['comparison']['review_first_ids'][0])
    selection = post(f"/upstream-requests/{upstream['id']}/selection", {'idempotency_key': prefix+'-selection',
                     'decision_snapshot_id': decision['id'], 'candidate_id': row['id'], 'selected_by': 'AI local mock', 'note': '本地接口排练，非施工批准'})
    common = {'idempotency_key': prefix+'-lab', 'decision_snapshot_id': decision['id'], 'candidate_id': row['id'],
              'material_version': row['scheme']['material_version'], 'data_scope': 'demo', 'observed_at': datetime.now(timezone.utc).isoformat(),
              'source_reference': 'local_mock_only/not_a_real_report', 'note': '构造反馈，仅验证契约'}
    lab_input = {**common, 'metric': 'DS', 'value': 9000, 'unit': '次/mm', 'test_group': prefix+'-test-group',
                 'test_method': 'demo_method', 'conditions': {'temperature': 'demo_60C', 'load': 'demo_load', 'conditioning': 'demo_conditioning'}, 'sample_count': 2}
    lab = post('/lab-feedback', lab_input)
    review = post(f"/feedback/{lab['id']}/review", {'state': 'approved', 'reviewer': 'AI local mock', 'note': '确认构造条件用于演示回流',
                                                 'conditions_confirmed': True, 'use_for_decision': True})
    field_input = {**common, 'idempotency_key': prefix+'-field', 'section_id': 'demo-section-001', 'service_days': 30,
                   'site_conditions': {'rainfall': 'unknown_demo'}, 'performance_note': '构造现场文字反馈，不转成实验室性能值'}
    field = post('/field-feedback', field_input)
    assert selection['decision_id'] == request['decision_id'] and selection['segment_id'] == request['segment_id']
    assert review['training_eligibility'] == 'not_granted' and review['model_retraining'] == 'not_triggered'
    assert client.get('/v2/records/' + decision['id']).json() == decision
    return {'scope': 'isolated_local_mock_only', 'request': request, 'upstream': upstream, 'selection': selection,
            'lab_input': lab_input, 'lab_submission': lab, 'lab_review': review, 'field_input': field_input, 'field_submission': field,
            'trace': trace, 'real_enterprise_integration': False, 'real_laboratory_or_field_data': False,
            'release_note': '反馈审核不授予新微调训练资格，不触发再训练或工程施工批准。'}


def main():
    with tempfile.TemporaryDirectory(prefix='upstream-v2-') as temporary:
        path = Path(temporary) / 'mock.sqlite'
        copy_baseline(path)
        engine = make_engine(path)
        try:
            with TestClient(create_app(engine)) as client:
                report = exercise(client)
                output = ROOT / 'artifacts/next-phase/week5-integration/local-mock.json'
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                print(json.dumps({'steps': len(report['trace']), 'decision_id_round_trip': report['selection']['decision_id'], 'scope': report['scope']}))
        finally:
            engine.dispose()


if __name__ == '__main__':
    main()
