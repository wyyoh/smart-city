"""Verify the frozen v0.2 files, original tables and historical release without rewriting them."""
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def verify():
    baseline = json.loads((ROOT / 'artifacts/review-phase/baseline.json').read_text(encoding='utf-8'))
    files = {name: (ROOT / name).is_file() and hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
             for name, expected in baseline['files'].items()}
    tables = {}
    with sqlite3.connect((ROOT / 'data/workbench.sqlite').as_uri() + '?mode=ro', uri=True) as conn:
        for name, before in baseline['original_database'].items():
            rows = conn.execute('SELECT * FROM "' + name + '" ORDER BY id').fetchall()
            after = {'rows': len(rows), 'sha256': hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()}
            tables[name] = {'before': before, 'after': after, 'unchanged': before == after}
    release = baseline['v02_release']
    same_zip = hashlib.sha256((ROOT / release['path']).read_bytes()).hexdigest() == release['sha256']
    result = {'status': 'passed' if all(files.values()) and all(v['unchanged'] for v in tables.values()) and same_zip else 'failed',
              'protected_files': files, 'original_tables': tables, 'v02_release_unchanged': same_zip}
    output = ROOT / 'artifacts/review-phase/verification/history-integrity.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert result['status'] == 'passed', result
    print(json.dumps({'status': 'passed', 'protected_files': len(files), 'original_tables': len(tables), 'v02_zip_unchanged': same_zip}))
    return result


if __name__ == '__main__':
    verify()
