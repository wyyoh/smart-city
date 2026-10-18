"""Start an isolated real server and replay the complete core workflow."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import httpx
from sqlmodel import Session

from app.importer import import_workbook
from app.settings import ROOT
from app.storage import initialize, make_engine


def run(run_id,port):
    out=ROOT/'artifacts/acceptance'/run_id
    out.mkdir(parents=True,exist_ok=False)
    database=out/'rehearsal.sqlite'
    eng=make_engine(database);initialize(eng)
    with Session(eng) as session:
        dataset,_=import_workbook(ROOT/'再生沥青混合料实验数据表.xlsx',session)
        source_hash=dataset.sha256
    eng.dispose()
    env=dict(os.environ,PYTHONPATH=str(ROOT/'backend'),ASPHALT_DATABASE=str(database))
    log=(out/'server.log').open('w',encoding='utf-8')
    command=[sys.executable,'-X','utf8','-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)]
    started=time.perf_counter()
    process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    trace=[]
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=15,trust_env=False) as client:
            for attempt in range(100):
                try:
                    if client.get('/health').status_code==200:break
                except httpx.TransportError:
                    pass
                if process.poll() is not None:raise RuntimeError('Server failed; see log')
                time.sleep(.1)
            else:raise RuntimeError('Server readiness timed out')
            startup=time.perf_counter()-started
            assert client.get('/').status_code==200
            catalog=client.get('/v1/catalog').json()
            assert len(catalog['recipes'])==180
            cases=client.get('/v1/cases').json()
            expected=[['R1'],['R4'],['R7'],['R5'],[]]
            timings=[];snapshots=[]
            for repeat in range(3):
                for i,case in enumerate(cases):
                    t=time.perf_counter();response=client.post('/v1/recommendations',json=case['scenario']);timings.append((time.perf_counter()-t)*1000)
                    assert response.status_code==201,response.text
                    snapshot=response.json()
                    assert [r['display_id'] for r in snapshot['results'] if r['passes_targets']]==expected[i]
                    if repeat==0:
                        snapshots.append(snapshot)
                        (out/f'{case["id"]}.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
                        html=client.get(f'/v1/recommendations/{snapshot["id"]}/report.html').text
                        assert '历史材料记录' in html
                        (out/f'{case["id"]}.html').write_text(html,encoding='utf-8')
            trace.append({'step':'five_cases','passed':True,'repetitions':3,'expected':expected})
            prediction=client.post('/v1/predictions/R1',json={})
            assert prediction.status_code==200,prediction.text
            trace.append({'step':'research_prediction','status':prediction.json()['status']})
            v=client.post('/v1/recipes/R1/variants',json={'oil_stone_ratio_pct':5.6,'note':'隔离排练微调，非真实试验'}).json()
            assert v['metrics']=={} and v['parent_id']
            scenario=dict(cases[0]['scenario'],candidate_ids=[v['id']])
            vr=client.post('/v1/recommendations',json=scenario).json()
            assert vr['results'][0]['status']=='needs_test'
            trace.append({'step':'variant_invalidates_parent','passed':True})
            observation={'recipe_id':'R1','metric':'DS','value':9400,'unit':'次/mm','test_group':run_id,
                'method':'本地排练，合成示范方法','conditions':'演示流程数据，不是新增实测',
                'source_reference':f'scripts/rehearse.py#{run_id}','sample_count':2,
                'idempotency_key':uuid4().hex,'data_scope':'demo'}
            obs=client.post('/v1/observations',json=observation).json()
            assert client.post('/v1/observations',json=observation).json()['id']==obs['id']
            assert client.get('/v1/recipes/R1?context_kind=constructed_demo').json()['metrics']['DS']!=9400
            review={'state':'approved','reviewer':'自动排练流程','note':'仅核验演示状态流转','conditions_confirmed':True,'use_for_recommendation':True}
            response=client.post('/v1/observations/'+obs['id']+'/review',json=review)
            assert response.status_code==200,response.text
            assert client.get('/v1/recipes/R1?context_kind=constructed_demo').json()['metrics']['DS']==9400
            assert client.get('/v1/recipes/R1').json()['metrics']['DS']!=9400
            assert client.get('/v1/recommendations/'+snapshots[0]['id']).json()==snapshots[0]
            trace.append({'step':'observation_review_scope_idempotency_and_snapshot','passed':True})
            # Data revisions invalidate saved model use until explicit retraining.
            assert client.post('/v1/predictions/R1',json={}).status_code==409
            trace.append({'step':'stale_model_guard','passed':True})
            ordered=sorted(timings)
            result={'run_id':run_id,'completed_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                'source_sha256':source_hash,'startup_seconds':round(startup,3),
                'recommendation_http_ms':{'n':len(timings),'median':round(ordered[len(ordered)//2],2),
                    'p95':round(ordered[int(.95*(len(ordered)-1))],2),'max':round(max(timings),2)},
                'trace':trace,'scope':'真实回环HTTP、隔离数据库、全新进程；演示观察不代表实验室实测'}
            (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(result,ensure_ascii=False,indent=2))
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        log.close()
    assert hashlib.sha256((ROOT/'再生沥青混合料实验数据表.xlsx').read_bytes()).hexdigest()==source_hash


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('run_id');parser.add_argument('--port',type=int,default=8768)
    args=parser.parse_args();run(args.run_id,args.port)
