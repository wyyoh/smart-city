"""Two complete isolated workflow rehearsals with no internet-dependent core calls."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'));sys.path.insert(0,str(ROOT/'scripts'))
from v2_isolation import copy_baseline
from fastapi.testclient import TestClient
from app.main import create_app
from app.storage import make_engine
from mock_upstream_v2 import exercise


def rehearse(run_id):
    output=ROOT/'artifacts/next-phase/rehearsals'/run_id;output.mkdir(parents=True,exist_ok=True)
    trace=[]
    with tempfile.TemporaryDirectory(prefix='rehearsal-v2-') as temporary:
        path=Path(temporary)/'rehearsal.sqlite';copy_baseline(path);engine=make_engine(path)
        try:
            with TestClient(create_app(engine)) as client:
                def post(path,body):
                    start=time.perf_counter();response=client.post(path,json=body);assert response.status_code==201,response.text
                    result=response.json();trace.append({'path':path,'status':response.status_code,'elapsed_ms':round(1000*(time.perf_counter()-start),3),'id':result.get('id'),'sha256':result.get('sha256')});return result
                assert client.get('/health').json()['version']=='0.2.0'
                page=client.get('/');assert page.status_code==200
                import re
                assets=re.findall(r'(?:src|href)="(/[^\"]+)"',page.text)
                assert assets and all(client.get(asset).status_code==200 for asset in assets)
                case=client.get('/v2/benchmark-cases').json()['cases'][0]
                resolved=post('/v2/demand-resolutions',case['example_request'])
                demand=post('/v2/demand-resolutions/'+resolved['id']+'/confirm',{'expected_sha256':resolved['sha256'],'confirmed_by':'AI offline rehearsal'})
                pool=post('/v2/candidate-pools',{'confirmation_id':demand['id']})
                decision=post('/v2/decisions',{'pool_id':pool['id']})
                assert len(decision['results'])==84 and len(decision['comparison']['feasible_ids'])==2
                report=client.get(f"/v2/decisions/{decision['id']}/report.html");assert report.status_code==200
                (output/'initial-report.html').write_text(report.text,encoding='utf-8')
                row=next(r for r in decision['results'] if r['display_id']=='R1')
                label=row['evidence']['DS']['raw_labels'][0]
                assert client.get(f"/v1/evidence/{pool['scope']['dataset']['id']}/{label['sheet']}/{label['row']}").status_code==200
                variant=post('/v1/recipes/R1/variants',{'oil_stone_ratio_pct':5.6,'note':'Rehearsal synthetic variant; no real new experiment'})
                assert not variant['metrics']
                assert client.post('/v2/decisions',json={'pool_id':pool['id']}).status_code==409
                pool2=post('/v2/candidate-pools',{'confirmation_id':demand['id']})
                revised=post('/v2/decisions',{'pool_id':pool2['id']})
                assert any(c['candidate_id']==variant['id'] for c in revised['test_plan']['cards'])
                diff=client.get('/v2/decision-diff',params={'before_id':decision['id'],'after_id':revised['id']}).json()
                assert variant['id'] in diff['candidate_changes']['added']
                assert client.get('/v2/records/'+decision['id']).json()==decision
                assert not client.get(f"/v2/decisions/{decision['id']}/freshness").json()['current']
                upstream=exercise(client,run_id)
                source_hash=pool['scope']['dataset']['sha256']
                result={'run_id':run_id,'status':'passed','created_at':datetime.now(timezone.utc).isoformat(),'app_version':'0.2.0',
                        'database':'disposable baseline copy','network':'in-process local HTTP only; built assets require no public service',
                        'trace':trace,'assets_verified':assets,'upstream_steps':len(upstream['trace']),'dataset_sha256':source_hash,
                        'checks':['scene-derived requirements','confirmation','84-key full pool','two numerical review candidates','source row','HTML report',
                                  'variant clears evidence','stale pool rejected','next test card','snapshot replay','difference','upstream linkage','separate feedback scopes'],
                        'limits':['No independent mixture tests or live enterprise integration.','Same machine with installed dependencies; not a fresh OS installation test.']}
                (output/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                print(json.dumps({'run_id':run_id,'status':'passed','core_steps':len(trace),'upstream_steps':len(upstream['trace'])}))
        finally:engine.dispose()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);args=parser.parse_args();rehearse(args.run_id)
