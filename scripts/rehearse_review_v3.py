"""Run the five same-pool cases and save review snapshots in an isolated catalogue."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'scripts'))

from fastapi.testclient import TestClient
from app.main import create_app
from app.storage import make_engine
from compare_cases_v2 import execute_case
from v2_isolation import copy_baseline


def run(database, output):
    assert not database.exists(), 'Use a new isolated database path.'
    database.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    copy_baseline(database)
    engine = make_engine(database)
    rows = []
    try:
        with TestClient(create_app(engine)) as client:
            assert client.get('/health').json()['version'] == '0.3.0'
            cases = client.get('/v2/benchmark-cases').json()['cases']
            for case in cases:
                for view in (['all', 'complete_numeric_demo'] if case['id'] == 'C5' else ['all']):
                    report, decision = execute_case(client, case, view)
                    suffix = case['id'] + ('-complete' if view != 'all' else '')
                    response = client.post('/v2/review/reports', json={'decision_id': decision['id'], 'request_id': 'rehearsal-' + suffix})
                    assert response.status_code == 201, response.text
                    review = response.json()
                    assert review['decision_sha256'] == decision['sha256'] and not review['engineering_release_approved']
                    assert review['freshness']['current']
                    html = client.get('/v2/review/reports/' + review['id'] + '/report.html')
                    assert html.status_code == 200 and review['review_sha256'] in html.text
                    assert client.get('/v2/review/reports/' + review['id']).json() == review
                    (output / (suffix + '-review.json')).write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                    (output / (suffix + '-review.html')).write_text(html.text, encoding='utf-8')
                    row = {'case': case['id'], 'evidence_view': view, 'pool': len(decision['results']),
                           'feasible_B1': len(report['B1']['feasible_ids']), 'feasible_V2': len(report['V2']['feasible_ids']),
                           'diagnosis': decision['diagnosis']['status'], 'conflict_certificates': len(review['certificate_checks']),
                           'certificate_checks_passed': all(c['valid'] for c in review['certificate_checks']),
                           'review_id': review['id'], 'decision_id': decision['id'], 'review_sha256': review['review_sha256'],
                           'saved_export_matches': True, 'engineering_release_approved': False}
                    rows.append(row)
            overview = client.get('/v2/review/overview').json()
            assert all(e['integrity'] == 'verified' for e in overview['evidence'].values())
            template = client.get('/v2/review/validation-template').json()
            checked = client.post('/v2/review/validate-input', json=template).json()
            assert checked['human_participants'] == 0 and not checked['collection_complete']
            handbook = client.get('/v2/review/handbook.html')
            assert handbook.status_code == 200
            (output / 'review-handbook.html').write_text(handbook.text, encoding='utf-8')
            result = {'status': 'passed', 'created_at': datetime.now(timezone.utc).isoformat(), 'actor': 'AI software self-test',
                      'scope': 'constructed cases, same frozen numerical requirements and pools', 'cases': rows,
                      'human_participants': 0, 'independent_material_validation': False,
                      'external_template_unfilled': checked, 'B1_and_V2_same_feasible_set_all_cases': True}
            (output / 'cases.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            return result
    finally:
        engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.database.resolve(), args.output.resolve())
    print(json.dumps({'status': result['status'], 'cases': len(result['cases']), 'database': str(args.database)}))
