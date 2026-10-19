"""Five constructed comparisons: B0 risk example, existing strong B1 and V2 on identical pools."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from fastapi.testclient import TestClient
from app.main import create_app
from app.storage import make_engine
from app.decision.diagnosis import verify_certificate
from app.decision.reports import html_report


def execute_case(client, case, evidence_view='all'):
    resolved = client.post('/v2/demand-resolutions', json=case['example_request']).json()
    assert resolved['requirements_complete'] and resolved['case_application']['id'] == case['id']
    confirmation = client.post(f"/v2/demand-resolutions/{resolved['id']}/confirm", json={'expected_sha256': resolved['sha256'], 'confirmed_by':'AI reproducible case verification'}).json()
    pool = client.post('/v2/candidate-pools', json={'confirmation_id':confirmation['id'],'evidence_view':evidence_view}).json()
    decision = client.post('/v2/decisions', json={'pool_id':pool['id']}).json()
    assert 'results' in decision
    legacy = next(c['scenario'] for c in client.get('/v1/cases').json() if c['id'] == case['id'])
    legacy['candidate_ids'] = pool['candidate_ids']
    b1 = client.post('/v1/recommendations', json=legacy).json()
    b1_ids = sorted(r['id'] for r in b1['results'] if r['passes_targets'])
    v2_ids = sorted(decision['comparison']['feasible_ids'])
    assert b1_ids == v2_ids, 'With all numerical targets given correctly, strong B1 and V2 should agree.'
    metric = case['baseline_priority']
    measured = [r for r in pool['candidates'] if r['metrics'].get(metric) is not None]
    best = max((r['metrics'][metric] for r in measured), default=None)
    b0_ids = [r['id'] for r in measured if r['metrics'][metric] == best and r['metrics'][metric] > case['targets'][metric]]
    b0_failed = [r['id'] for r in decision['results'] if r['id'] in b0_ids and r['failed_targets']]
    b0_unresolved = [r['id'] for r in decision['results'] if r['id'] in b0_ids and not r['failed_targets'] and r['unknown_targets']]
    certificate_checks = [verify_certificate(c,decision['results'],decision['pool_sha256'],decision['confirmation_sha256']) for c in decision['diagnosis']['certificates']]
    assert all(c['valid'] for c in certificate_checks)
    report = {'case_id':case['id'],'title':case['title'],'source':case['source'],'evidence_view':evidence_view,
              'scope':decision['scope'],'pool_sha256':decision['pool_sha256'],'candidate_ids':pool['candidate_ids'],
              'demand':confirmation,'pool_exclusions':pool['excluded'],'summary':decision['summary'],
              'B0':{'rule':'预登记单指标阈值与最高值（并列保留），忽略其他要求；仅为弱风险示例','metric':metric,'selected_ids':b0_ids,'known_other_failure_ids':b0_failed,'unresolved_other_requirement_ids':b0_unresolved},
              'B1':{'rule':'保留原v1全约束加单优先级，使用同一冻结候选ID和同一数值目标','feasible_ids':b1_ids,'information_scope':'same_visible_numerical_evidence'},
              'V2':{'feasible_ids':v2_ids,'review_first_ids':decision['comparison']['review_first_ids'],'diagnosis':decision['diagnosis'],'certificate_checks':certificate_checks},
              'strong_B1_agrees_on_feasible_set':b1_ids==v2_ids,
              'demand_evaluation':{'scope':'three_rule_derived_profiles_plus_two_explicit_constructed_requirement_templates','engineering_validity':'not_verified'},
              'model_error_evaluation':'Separate existing model cards; no prediction accuracy inferred from these examples.',
              'recommendation_validation':'Software replay of recorded aggregate labels only; independent material tests pending.'}
    return report, decision


def run_comparisons(client, output):
    output.mkdir(parents=True,exist_ok=True)
    cases=client.get('/v2/benchmark-cases').json()['cases']
    summaries=[]
    for case in cases:
        report,decision=execute_case(client,case)
        (output/(case['id']+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (output/(case['id']+'.html')).write_text(html_report(decision),encoding='utf-8')
        (output/(case['id']+'-snapshot.json')).write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        summaries.append({'case':case['id'],'pool':len(decision['results']),'feasible_B1':len(report['B1']['feasible_ids']),
                          'feasible_V2':len(report['V2']['feasible_ids']),'B0_known_failed':len(report['B0']['known_other_failure_ids']),
                          'B0_unresolved':len(report['B0']['unresolved_other_requirement_ids']),'diagnosis':decision['diagnosis']['status']})
        if case['id']=='C5':
            diagnostic,snapshot=execute_case(client,case,'complete_numeric_demo')
            assert len(snapshot['results'])==35 and len(snapshot['diagnosis']['certificates'])==4
            (output/'C5-complete-numeric-diagnostic.json').write_text(json.dumps(diagnostic,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            (output/'C5-complete-numeric-diagnostic.html').write_text(html_report(snapshot),encoding='utf-8')
    summary={'scope':'constructed_software_cases_only','created_at':datetime.now(timezone.utc).isoformat(),'cases':summaries,
             'B1_and_V2_same_feasible_set_all_cases':True,'independent_engineering_validation':False,
             'optional_research_experiments':'deferred_by_user_capacity_choice'}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return summary


def main():
    with tempfile.TemporaryDirectory(prefix='five-cases-v2-') as temporary:
        path=Path(temporary)/'cases.sqlite';shutil.copyfile(ROOT/'artifacts/next-phase/baseline/workbench-v01.sqlite',path)
        engine=make_engine(path)
        try:
            with TestClient(create_app(engine)) as client:
                print(json.dumps(run_comparisons(client,ROOT/'artifacts/next-phase/case-reports'),ensure_ascii=False))
        finally:engine.dispose()


if __name__=='__main__':main()
