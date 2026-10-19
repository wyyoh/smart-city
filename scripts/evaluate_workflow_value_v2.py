"""Automated task proxies; never substitute their timings for human time or field benefit."""
from datetime import datetime, timezone
from itertools import combinations
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
sys.path.insert(0, str(ROOT / 'scripts'))
from v2_isolation import copy_baseline

from fastapi.testclient import TestClient
from app.main import create_app
from app.storage import make_engine


def reference_review(pool,targets,rap_min):
    rows=[];evaluations=0
    for recipe in pool['candidates']:
        states={}
        for metric,threshold in targets.items():
            actual=recipe['metrics'].get(metric);evaluations+=1
            states[metric]='missing' if actual is None else 'satisfied' if actual>threshold else 'failed'
        if rap_min is not None:
            actual=recipe['rap_nominal_pct'];evaluations+=1
            states['rap']='missing' if actual is None else 'satisfied' if actual>=rap_min else 'failed'
        rows.append({'id':recipe['id'],'states':states})
    feasible=sorted(r['id'] for r in rows if all(v=='satisfied' for v in r['states'].values()))
    possible=[r['id'] for r in rows if 'failed' not in r['states'].values()]
    conflicts=[]
    if rows and not possible:
        metrics=list(rows[0]['states'])
        for size in range(1,len(metrics)+1):
            for subset in combinations(metrics,size):
                if any(set(found).issubset(subset) for found in conflicts):continue
                if all(any(r['states'][key]=='failed' for key in subset) for r in rows):conflicts.append(subset)
    return {'feasible_ids':feasible,'possible_ids':possible,'minimal_known_failure_subsets':conflicts,
            'predicate_evaluations':evaluations,'status':'feasible' if feasible else 'insufficient' if possible else 'conflict' if rows else 'empty'}


def evaluate(client):
    cases={c['id']:c for c in client.get('/v2/benchmark-cases').json()['cases']}
    task_definitions=[('routine_selection','C1','all'),('conflict_review','C5','complete_numeric_demo'),('new_version_validation','C1','all')]
    orders=[['manual_proxy','B1','V2'],['B1','V2','manual_proxy'],['V2','manual_proxy','B1']]
    tasks=[]
    for (name,case_id,view),order in zip(task_definitions,orders):
        case=cases[case_id];request=json.loads(json.dumps(case['example_request']))
        start=time.perf_counter();shared_operations=[]
        if name=='new_version_validation':
            variant=client.post('/v1/recipes/R1/variants',json={'oil_stone_ratio_pct':5.6,'note':'AI value proxy fixture, not a real mixture experiment'}).json()
            scheme=client.get('/v2/materials/'+variant['id']).json();request['inventory']['product_versions']=[scheme['material_version']]
            shared_operations.extend(['create labelled variant fixture','read material version'])
        resolution=client.post('/v2/demand-resolutions',json=request).json();shared_operations.append('resolve demand')
        confirmation=client.post(f"/v2/demand-resolutions/{resolution['id']}/confirm",json={'expected_sha256':resolution['sha256'],'confirmed_by':'AI proxy self-test'}).json();shared_operations.append('record confirmation')
        pool=client.post('/v2/candidate-pools',json={'confirmation_id':confirmation['id'],'evidence_view':view}).json();shared_operations.append('freeze shared visible pool')
        shared_seconds=time.perf_counter()-start
        expected=reference_review(pool,case['targets'],case['rap_min_pct'])
        measurements=[]
        for method in order:
            start=time.perf_counter();native_omissions=[]
            if method=='manual_proxy':
                output=reference_review(pool,case['targets'],case['rap_min_pct'])
                feasible=output['feasible_ids'];operations=[{'operation':'explicit spreadsheet-style predicate scan','unit':'software predicate evaluations','count':output['predicate_evaluations']},
                    {'operation':'enumerate requirement subsets for review when all candidates have known failures','count':len(output['minimal_known_failure_subsets'])}]
                # A script represents the manual procedure; no human operations have been observed.
                note='人工表格核对步骤的软件代理；不是人工实测。'
            elif method=='B1':
                legacy=next(c['scenario'] for c in client.get('/v1/cases').json() if c['id']==case_id)
                legacy['candidate_ids']=pool['candidate_ids']
                result=client.post('/v1/recommendations',json=legacy).json()
                feasible=sorted(r['id'] for r in result['results'] if r['passes_targets'])
                operations=[{'operation':'read existing baseline scenario','unit':'API calls','count':1},{'operation':'run existing B1 all-constraint method','unit':'API calls','count':1}]
                if name=='conflict_review':native_omissions=['native minimal conflict certificate']
                if name=='new_version_validation':native_omissions=['native method/condition-specific stopping card']
                supplement=reference_review(pool,case['targets'],case['rap_min_pct'])
                operations.append({'operation':'explicit software reference supplement for unavailable native audit outputs','unit':'predicate evaluations','count':supplement['predicate_evaluations']})
                note='保留原B1；补充审计步骤由软件代理执行，不能称真人补充用时。'
            else:
                result=client.post('/v2/decisions',json={'pool_id':pool['id']}).json()
                feasible=sorted(result['comparison']['feasible_ids'])
                operations=[{'operation':'generate audited decision and verification actions','unit':'API calls','count':1}]
                assert (result['diagnosis']['status']=='evidence_insufficient')==(expected['status']=='insufficient')
                if name=='conflict_review':assert len(result['diagnosis']['certificates'])==4
                if name=='new_version_validation':assert len(result['test_plan']['cards'])==4
                note='V2原生生成来源、四态、诊断、验证动作与冻结快照。'
            elapsed=time.perf_counter()-start
            assert feasible==expected['feasible_ids']
            measurements.append({'method':method,'operator':'AI-controlled software proxy','shared_preparation_seconds':round(shared_seconds,6),
                                 'adapter_elapsed_seconds':round(elapsed,6),'replayed_workflow_seconds':round(shared_seconds+elapsed,6),
                                 'human_effective_seconds':None,'human_operation_count':None,'software_operations':operations,
                                 'native_output_omissions_before_reference_supplement':native_omissions,'numerical_feasible_set_matches_reference':True,
                                 'pool_sha256':pool['pool_sha256'],'note':note})
        tasks.append({'task':name,'case':case_id,'pool_count':len(pool['candidate_ids']),'order':order,'shared_operations':shared_operations,
                      'visible_information':'All arms receive the same frozen candidate labels, targets and provenance; shared preparation is reported explicitly.',
                      'measurements':measurements,'expected':expected})
    return {'task':'N18','measurement_kind':'automated_proxy_replay','created_at':datetime.now(timezone.utc).isoformat(),
            'participant':{'human_participants':0,'operator':'AI-controlled local software','learning_order':'Three method orders rotated; no human learning effect measured.'},
            'tasks':tasks,'human_timing_status':'not_measured','industry_efficiency_gain':'not_estimated',
            'limitations':['API/CPU/serialization and shared preparation affect these timings. They cannot rank human productivity.',
                          'Manual proxy is a script of reference steps, not a person using a spreadsheet.',
                          'B1 remains strong; identical feasible sets do not establish V2 recommendation accuracy gains.',
                          'Human end-to-end task times, cost, carbon, life and field benefits require later independent measurement.']}


def main():
    with tempfile.TemporaryDirectory(prefix='value-v2-') as temporary:
        path=Path(temporary)/'value.sqlite';copy_baseline(path);engine=make_engine(path)
        try:
            with TestClient(create_app(engine)) as client:
                report=evaluate(client)
                (ROOT/'artifacts/next-phase/workflow-value.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                print(json.dumps({'tasks':len(report['tasks']),'proxy_workflows':sum(len(t['measurements']) for t in report['tasks']),'human_participants':0,'human_speedup_claimed':False}))
        finally:engine.dispose()


if __name__=='__main__':main()
