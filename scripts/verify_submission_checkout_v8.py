"""Restore an independent checkout and run current creative workflows end to end."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SMOKE = r'''
from contextlib import closing
import hashlib,json,sqlite3,tempfile
from pathlib import Path
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import create_app
from app.settings import ROOT
from app.storage import make_engine
assert ROOT.resolve()==Path.cwd().resolve()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((ROOT/'artifacts/distribution/runtime-assets.json').read_text(encoding='utf-8'))
assert all(sha(ROOT/n)==h for n,h in manifest['frontend_source_files'].items())
assert all(sha(ROOT/e['path'])==e['sha256'] for e in manifest['files'])
original=ROOT/'data/workbench.sqlite';original_hash=sha(original)
with tempfile.TemporaryDirectory(prefix='creative-smoke-',dir=ROOT/'tmp') as temporary:
 database=Path(temporary)/'workbench.sqlite'
 with closing(sqlite3.connect(original.as_uri()+'?mode=ro',uri=True)) as old,closing(sqlite3.connect(database)) as new:old.backup(new)
 engine=make_engine(database)
 try:
  with TestClient(create_app(engine)) as client:
   assert client.get('/health').json()['version']=='0.4.0'
   assert client.get('/?view=design').status_code==200
   for p in (ROOT/'frontend/dist/assets').iterdir():assert client.get('/assets/'+p.name).status_code==200
   review=client.get('/v2/review/overview').json()
   assert review['current_data']['historical_keys']==180
   assert review['submission_scope']['physical_validation_required'] is False
   assert all(v['integrity']=='verified' for v in review['evidence'].values()), {k:v['integrity'] for k,v in review['evidence'].items()}
   research=client.get('/v4/research/overview').json()
   assert research['compatibility']['matches']
   assert research['production_model_promoted'] is False
   cases={}
   for case,count in zip(['C1','C2','C3','C4','C5'],[2,2,5,1,0]):
    response=client.post('/v5/design/cases/'+case+'/runs',json={'request_id':uuid4().hex})
    assert response.status_code==201,response.text[:500]
    value=response.json();d=value['decision'];cases[case]=value
    assert len(d['results'])==84 and len(d['comparison']['feasible_ids'])==count
    assert value['baseline']['same_feasible_set']
    assert client.get('/v5/design/records/'+value['id']+'/export.json').json()==value
    assert value['sha256'] in client.get('/v5/design/records/'+value['id']+'/print.html').text
   d=cases['C3']['decision']
   response=client.post('/v5/design/preferences',json={'decision_id':d['id'],'expected_decision_sha256':d['sha256'],'priority_order':['residual']})
   assert response.status_code==200
   preference=response.json()['comparison']
   assert preference['review_first_ids']==['mix_59cb42163ce4719d7809']
   assert set(preference['feasible_ids'])==set(d['comparison']['feasible_ids'])
   d=cases['C2']['decision'];parent='mix_ec30ff644f3111c570bc'
   context=client.get('/v5/design/explorations/'+d['id']+'/'+parent).json()
   assert context['total_parent_hypotheses']==10 and context['total']==7
   response=client.post('/v5/design/drafts',json={'request_id':uuid4().hex,'origin_decision_id':d['id'],'expected_decision_sha256':d['sha256'],
     'parent_recipe_id':parent,'hypothesis_id':'hyp_6e18d41dcaefa559','locked_fields':['nominal_component_weights'],
     'design_intent':'独立目录核对：保持原要求，探索油石比4.9%到5.0%。','research_scope_sha256':context['scope_sha256']})
   assert response.status_code==201,response.text[:500]
   draft=response.json();assert draft['measured_performance'] is None and not draft['inherits_parent_measurements']
   response=client.post('/v5/design/cases/C5/runs',json={'request_id':uuid4().hex,'evidence_view':'complete_numeric_demo'})
   assert response.status_code==201
   complete=response.json()['decision']
   assert cases['C5']['decision']['diagnosis']['status']=='evidence_insufficient'
   assert len(complete['results'])==35 and len(complete['diagnosis']['certificates'])==4
   assert complete['diagnosis']['status']=='known_conflict'
   result={'status':'passed','historical_keys':180,'case_pool':84,'case_feasible':[2,2,5,1,0],
    'same_pool_baselines_match':True,'C3_preference_preserves_feasible_set':True,'C2_exact_parent_draft_unknown':True,
    'C5_complete_pool':35,'C5_conflicts':4,'current_frontend_and_source_match':True,
    'review_evidence_verified':len(review['evidence']),'research_compatible':True}
 finally:engine.dispose()
assert sha(original)==original_hash
result['source_database_unchanged']=True
print(json.dumps(result,ensure_ascii=False))
'''


def check(directory):
    directory=Path(directory).resolve()
    (directory/'tmp').mkdir(exist_ok=True)
    restored=subprocess.run([sys.executable,'-X','utf8',str(directory/'scripts/restore_published_assets.py')],
                            cwd=directory,capture_output=True,text=True,encoding='utf-8',check=True)
    env=dict(os.environ);env['PYTHONPATH']=str(directory/'backend')+os.pathsep+str(directory)
    smoke=subprocess.run([sys.executable,'-X','utf8','-c',SMOKE],cwd=directory,env=env,
                         capture_output=True,text=True,encoding='utf-8')
    if smoke.returncode:raise RuntimeError(smoke.stderr or smoke.stdout)
    return {'restoration':json.loads(restored.stdout),'core_application':json.loads(smoke.stdout),
            'launcher':check_launcher(directory)}


def check_launcher(directory):
    """Run the shipped PowerShell launcher with a prepared dependency junction."""
    if os.name!='nt':return {'status':'not_run','reason':'PowerShell launcher check requires Windows'}
    dependency=ROOT/'.venv'
    link=directory/'.venv'
    assert not link.exists() and dependency.is_dir()
    literal=lambda value:"'"+str(value).replace("'","''")+"'"
    created=subprocess.run(['powershell.exe','-NoProfile','-Command',
        'New-Item -ItemType Junction -Path '+literal(link)+' -Target '+literal(dependency)+' | Out-Null'],
        capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    if created.returncode:raise RuntimeError(created.stderr)
    assert link.resolve()==dependency.resolve()
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1',0));port=reserved.getsockname()[1]
    log_path=directory/'tmp/launcher.log'
    log=log_path.open('w',encoding='utf-8')
    process=None
    try:
        process=subprocess.Popen(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
            str(directory/'scripts/start-creative-demo.ps1'),'-Port',str(port)],cwd=directory,
            stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        base=f'http://127.0.0.1:{port}'
        for _ in range(80):
            try:
                with urllib.request.urlopen(base+'/health',timeout=1) as response:
                    health=json.load(response)
                break
            except OSError:
                if process.poll() is not None:raise RuntimeError(log_path.read_text(encoding='utf-8',errors='replace')[-1500:])
                time.sleep(.25)
        else:raise RuntimeError('Published launcher did not start')
        assert health['version']=='0.4.0'
        request=urllib.request.Request(base+'/v5/design/cases/C1/runs',
            data=json.dumps({'request_id':uuid4().hex}).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=10) as response:value=json.load(response)
        assert len(value['decision']['results'])==84 and len(value['decision']['comparison']['feasible_ids'])==2
        return {'status':'passed','script':'scripts/start-creative-demo.ps1','health_version':'0.4.0',
                'C1_pool':84,'C1_feasible':2,'dependency_environment':'Prepared dependency junction, no new dependency installation claim.'}
    finally:
        if process is not None:
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            process.wait(timeout=10)
        log.close()
        assert link.resolve()==dependency.resolve()
        link.rmdir()  # Remove only the junction, never the dependency directory.


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path)
    parser.add_argument('--revision',default='HEAD')
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/submission-v8/clean-checkout.json')
    args=parser.parse_args()
    result={'created_on':'2026-10-23','status':'passed',
            'scope':'Independent directory restoration using this host prepared Python dependencies; no second-machine installation claim.'}
    if args.directory:
        result.update(check(args.directory))
    else:
        tree=subprocess.check_output(['git','rev-parse',args.revision+'^{tree}'],cwd=ROOT,text=True).strip()
        with tempfile.TemporaryDirectory(prefix='submission-checkout-') as temporary:
            directory=Path(temporary).resolve()
            assert directory.is_relative_to(Path(tempfile.gettempdir()).resolve())
            archive=directory/'source.tar'
            with archive.open('wb') as stream:subprocess.run(['git','archive','--format=tar',tree],cwd=ROOT,stdout=stream,check=True)
            with tarfile.open(archive) as bundle:bundle.extractall(directory,filter='data')
            result.update(check(directory))
        result['validated_git_tree']=tree
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result['core_application'],ensure_ascii=False))


if __name__=='__main__':main()
