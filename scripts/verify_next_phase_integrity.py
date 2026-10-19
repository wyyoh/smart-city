"""Check immutable sources and original database rows against the registered baseline."""
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT=Path(__file__).resolve().parents[1]


def table_hash(connection,table):
    rows=connection.execute('SELECT * FROM "'+table.replace('"','""')+'" ORDER BY id').fetchall()
    return {'rows':len(rows),'sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()}


def main():
    baseline=json.loads((ROOT/'docs/next-phase-baseline.json').read_text(encoding='utf-8'))
    inputs={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==fingerprint for name,fingerprint in baseline['immutable_inputs'].items()}
    comparisons={}
    with sqlite3.connect((ROOT/'data/workbench.sqlite').as_uri()+'?mode=ro',uri=True) as current, sqlite3.connect((ROOT/baseline['database_snapshot']['backup']).as_uri()+'?mode=ro',uri=True) as saved:
        for table in ['dataset','recipe','measurement','sourcerow','recommendation','observation']:
            before,after=table_hash(saved,table),table_hash(current,table)
            comparisons[table]={'before':before,'after':after,'unchanged':before==after}
    result={'status':'passed' if all(inputs.values()) and all(v['unchanged'] for v in comparisons.values()) else 'failed',
            'immutable_inputs':inputs,'original_database_tables':comparisons}
    assert result['status']=='passed',result
    path=ROOT/'artifacts/next-phase/release-checks/source-integrity.json';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'immutable_files':len(inputs),'unchanged_original_tables':len(comparisons)}))


if __name__=='__main__':main()
