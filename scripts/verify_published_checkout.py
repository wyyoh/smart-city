"""Export a Git tree, restore its assets, and smoke-test the independent checkout."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SMOKE = r'''
from contextlib import closing
import hashlib,json,sqlite3
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import create_app
from app.settings import ROOT
from app.storage import make_engine
assert ROOT.resolve()==Path.cwd().resolve()
baseline=json.loads((ROOT/'artifacts/review-phase/baseline.json').read_text(encoding='utf-8'))
mismatched=[p for p,h in baseline['files'].items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
assert not mismatched, 'Historical evidence hash mismatch: '+json.dumps(mismatched,ensure_ascii=False)
with closing(sqlite3.connect((ROOT/'data/workbench.sqlite').as_uri()+'?mode=ro',uri=True)) as connection:
 for name,expected in baseline['original_database'].items():
  rows=connection.execute('SELECT * FROM "'+name+'" ORDER BY id').fetchall()
  assert {'rows':len(rows),'sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()}==expected
engine=make_engine(ROOT/'artifacts/review-phase/demo.sqlite')
with TestClient(create_app(engine)) as client:
 assert client.get('/health').json()['version']=='0.4.0'
 assert client.get('/').status_code==200
 for asset in (ROOT/'frontend/dist/assets').iterdir():
  assert client.get('/assets/'+asset.name).status_code==200
 review=client.get('/v2/review/overview').json()
 assert review['submission_scope']['physical_validation_required'] is False
 assert all(e['integrity']=='verified' for e in review['evidence'].values())
 assert review['current_data']['historical_keys']==180
 research=client.get('/v4/research/overview').json()
 assert research['compatibility']['matches'] and research['production_model_promoted'] is False
 candidates=client.get('/v4/research/candidates').json()
 assert candidates['total']==731
 detail=client.get('/v4/research/candidates/'+candidates['items'][0]['id']).json()
 assert detail['candidate']['measured_performance'] is None
 assert client.get('/v1/models').status_code==200
 assert client.get('/v2/review/handbook.html').status_code==200
 decisions=client.get('/v2/decisions').json()
engine.dispose()
print(json.dumps({'status':'passed','historical_keys':180,'supported_designs':731,'saved_demo_decisions':len(decisions),
 'review_evidence_verified':len(review['evidence']),'protected_legacy_files':len(baseline['files']),
 'original_database_tables_unchanged':len(baseline['original_database']),'frontend_static_assets':'passed',
 'creative_scope_preserved':True,'new_formulation_performance_remains_unknown':True}))
'''


def verify(git, revision):
    tree = subprocess.check_output([git, 'rev-parse', revision+'^{tree}'], cwd=ROOT, text=True).strip()
    with tempfile.TemporaryDirectory(prefix='smart-city-github-checkout-') as temporary:
        checkout = Path(temporary).resolve()
        assert checkout.is_relative_to(Path(tempfile.gettempdir()).resolve())
        archive = checkout/'source.tar'
        with archive.open('wb') as output:
            subprocess.run([git, 'archive', '--format=tar', tree], cwd=ROOT, stdout=output, check=True)
        with tarfile.open(archive) as source: source.extractall(checkout, filter='data')
        restored = subprocess.run([sys.executable, '-X', 'utf8', str(checkout/'scripts/restore_published_assets.py')],
                                  cwd=checkout, capture_output=True, text=True, encoding='utf-8', check=True)
        restoration = json.loads(restored.stdout)
        env = dict(os.environ); env['PYTHONPATH'] = str(checkout/'backend')+os.pathsep+str(checkout)
        smoke = subprocess.run([sys.executable, '-X', 'utf8', '-c', SMOKE], cwd=checkout, env=env,
                               capture_output=True, text=True, encoding='utf-8')
        if smoke.returncode: raise RuntimeError(smoke.stderr or smoke.stdout)
        result = {'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'passed', 'validated_git_tree': tree,
                  'restored_assets': len(restoration['restored']), 'core_application': json.loads(smoke.stdout),
                  'scope': 'Independent Git export and asset restoration using the prepared dependency environment; dependency installation on a second physical computer was not performed.'}
    destination = ROOT/'artifacts/github-publish/clean-checkout.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--git', default=shutil.which('git') or 'git')
    parser.add_argument('--revision', default='HEAD')
    args = parser.parse_args()
    verify(args.git, args.revision)
