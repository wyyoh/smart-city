import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import httpx
from app.settings import ROOT


def verify(directory):
    manifest=json.loads((directory/'release-manifest.json').read_text(encoding='utf-8'))
    for f in manifest['files']:
        path=directory/f['path']
        assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==f['sha256'],f['path']
    qa=ROOT/'artifacts/package-qa';qa.mkdir(parents=True,exist_ok=True)
    database=qa/(directory.name+'.sqlite')
    shutil.copy2(directory/'data/workbench.sqlite',database)
    env=dict(os.environ,PYTHONPATH=str(directory/'backend'),ASPHALT_DATABASE=str(database))
    with (qa/'server.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen([sys.executable,'-X','utf8','-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8769'],
            cwd=directory,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            with httpx.Client(base_url='http://127.0.0.1:8769',trust_env=False,timeout=15) as client:
                for attempt in range(100):
                    try:
                        if client.get('/health').status_code==200:break
                    except httpx.TransportError:pass
                    if process.poll() is not None:raise RuntimeError('Packaged server failed')
                    time.sleep(.1)
                else:raise RuntimeError('Packaged server timeout')
                assert client.get('/').status_code==200
                scenario=client.get('/v1/cases').json()[2]['scenario']
                result=client.post('/v1/recommendations',json=scenario).json()
                assert [r['display_id'] for r in result['results'] if r['passes_targets']]==['R7']
                response=client.post('/v1/predictions/R1',json={})
                assert response.status_code==200,response.text
                assert client.get('/v1/reports').status_code==200
                case=client.get('/v2/benchmark-cases').json()['cases'][4]
                resolution=client.post('/v2/demand-resolutions',json=case['example_request']).json()
                demand=client.post('/v2/demand-resolutions/'+resolution['id']+'/confirm',json={'expected_sha256':resolution['sha256'],'confirmed_by':'AI package verification'}).json()
                pool=client.post('/v2/candidate-pools',json={'confirmation_id':demand['id'],'evidence_view':'complete_numeric_demo'}).json()
                decision=client.post('/v2/decisions',json={'pool_id':pool['id']}).json()
                assert len(decision['results'])==35 and len(decision['diagnosis']['certificates'])==4
                assert client.get('/v2/decisions/'+decision['id']+'/report.html').status_code==200
        finally:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
    result={'status':'passed','directory':str(directory),'manifest_files_verified':len(manifest['files']),
            'checks':['all packaged file hashes','relocated application root','bundled frontend','legacy C3 returns R7','bundled model prediction','saved reports','v2 C5 35-key numeric scope with four certificates','v2 HTML report'],
            'environment':'同一机器的已安装Python依赖；从另一目录启动，不是全新操作系统验收'}
    if manifest.get('app_version')=='0.2.0':
        checks_root=ROOT/'artifacts/next-phase/release-checks'
        receipts=checks_root/'package-verifications';receipts.mkdir(exist_ok=True)
        (receipts/(directory.name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        candidate_receipt=checks_root/'package-verification.json'
        if not candidate_receipt.exists():candidate_receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    else:
        (ROOT/'artifacts/package-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();verify(a.directory.resolve(strict=True))
