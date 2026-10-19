"""Read-only evidence and historical-state verification for the research UI."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from app.main import create_app
from app.research_workbench.experiments import protect_previous
from app.research_workbench.service import registry, verified_path
from app.storage import now


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    output = ROOT/'artifacts/research-workbench'
    previous = protect_previous()
    baseline = json.loads((ROOT/'artifacts/review-phase/baseline.json').read_text(encoding='utf-8'))
    files = {name: sha(ROOT/name) == expected for name, expected in baseline['files'].items()}
    tables = {}
    with sqlite3.connect((ROOT/'data/workbench.sqlite').as_uri()+'?mode=ro', uri=True) as connection:
        for name, expected in baseline['original_database'].items():
            rows = connection.execute('SELECT * FROM "'+name+'" ORDER BY id').fetchall()
            actual = {'rows': len(rows), 'sha256': hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()}
            tables[name] = {'expected': expected, 'actual': actual, 'unchanged': expected == actual}
    releases = [baseline['v02_release'], {
        'path': 'artifacts/release/asphalt-workbench-0.3.0-20261019T073332.zip',
        'sha256': '72e7e05a9c338d456f648e66bbcdb22b48e39d6be28254d1a665c9a5ea56e68e'}]
    release_checks = {r['path']: sha(ROOT/r['path']) == r['sha256'] for r in releases}
    registered = {}
    for key in registry()['evidence']:
        entry, path, raw = verified_path(key)
        registered[key] = {'path': entry['path'], 'sha256': hashlib.sha256(raw).hexdigest(), 'matches': sha(path) == entry['sha256']}
    protocol = json.loads((output/'head-fallback-protocol.json').read_text(encoding='utf-8'))
    study = json.loads((output/'head-fallback.json').read_text(encoding='utf-8'))
    original = np.load(output/'head-fallback-oof.npz')
    rerun = np.load(output/'reproduction/head-fallback-oof.npz')
    exact = set(original.files) == set(rerun.files) and all(np.array_equal(original[k], rerun[k]) for k in original.files)
    folds = json.loads((output/'head-fallback-folds.json').read_text(encoding='utf-8'))
    separation = len(folds) == 50 and all(not set(f['train_groups']) & set(f['test_groups']) and not set(f['train_ids']) & set(f['test_ids']) for f in folds)
    audit = json.loads((output/'source-audit.json').read_text(encoding='utf-8'))
    cells = [r for i in audit['issues'] for e in i['entries'] for m in e['labels'].values() for r in m['references']]
    protocol_matches = protocol['code_sha256'] == sha(ROOT/'backend/app/research_workbench/experiments.py') and study['protocol_sha256'] == sha(output/'head-fallback-protocol.json')
    result = {'created_at': now(), 'status': 'passed', 'prior_research_protection': previous,
        'protected_legacy_files': files, 'original_tables': tables, 'historical_releases': release_checks,
        'registered_evidence': registered, 'protocol_and_code_match': protocol_matches,
        'exact_prediction_and_acceptance_rerun': exact, 'outer_group_separation': separation,
        'source_references_checked': len(cells), 'all_source_rows_exist': all(r['source_row_exists'] for r in cells),
        'all_source_questions_unanswered': all(q['answer'] is None for i in audit['issues'] for q in i['questions']),
        'production_model_promoted': False, 'independent_material_tests': 0}
    assert all(files.values()) and all(t['unchanged'] for t in tables.values()) and all(release_checks.values())
    assert exact and separation and protocol_matches and len(cells) == 181 and result['all_source_rows_exist']
    assert result['all_source_questions_unanswered']
    (ROOT/'docs/api-research-v4.openapi.json').write_text(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    (output/'integrity-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'status': 'passed', 'protected_legacy_files': len(files), 'unchanged_original_tables': len(tables),
                      'registered_evidence': len(registered), 'source_cells': len(cells), 'exact_rerun': exact}))


if __name__ == '__main__':
    verify()
