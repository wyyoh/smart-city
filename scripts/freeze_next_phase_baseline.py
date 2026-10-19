"""Freeze existing evidence and an online SQLite backup without changing source data."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    destination = ROOT / 'docs/next-phase-baseline.json'
    if destination.exists():
        record = json.loads(destination.read_text(encoding='utf-8'))
        for name, digest in record['immutable_inputs'].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
        print(json.dumps({'status': 'existing_baseline_verified', 'path': str(destination)}, ensure_ascii=False))
        return
    files = [
        '再生沥青混合料实验数据表.xlsx',
        '第十二届中国研究生智慧城市技术与创意设计大赛企业揭榜技术需求征集表-HY-01 (1).pdf',
        'planning/development_backlog_v1.json', 'planning/v02_alignment_backlog.json',
        'planning/next_phase_backlog_v2.json', 'artifacts/release-final.json',
        'artifacts/models/model_cards.json', 'requirements.lock.txt',
    ]
    digests = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}
    db = ROOT / 'data/workbench.sqlite'
    backup = ROOT / 'artifacts/next-phase/baseline/workbench-v01.sqlite'
    backup.parent.mkdir(parents=True, exist_ok=True)
    assert not backup.exists(), 'An unregistered backup exists; reconcile it before freezing.'
    with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) as source:
        with sqlite3.connect(backup) as target:
            source.backup(target)
            tables = [r[0] for r in target.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            counts = {name: target.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0]
                      for name in tables}
            datasets = [dict(zip(['id', 'sha256', 'revision', 'importer_version'], row))
                        for row in target.execute('SELECT id,sha256,revision,importer_version FROM dataset')]
            assert target.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    record = {
        'frozen_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'source_revision': args.revision, 'baseline_app_version': '0.1.0',
        'immutable_inputs': digests,
        'database_snapshot': {'source': 'data/workbench.sqlite',
                              'backup': str(backup.relative_to(ROOT)).replace('\\', '/'),
                              'sha256': hashlib.sha256(backup.read_bytes()).hexdigest(),
                              'integrity_check': 'ok', 'table_counts': counts, 'datasets': datasets},
        'scope': 'SQLite online backup; original workbook and original catalogue rows remain untouched.',
        'future_validation': 'Use isolated copies through ASPHALT_DATABASE or existing temporary test fixtures.',
    }
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'status': 'baseline_frozen', 'path': str(destination), 'tables': counts}, ensure_ascii=False))


if __name__ == '__main__':
    main()
