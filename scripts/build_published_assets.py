"""Bundle ignored runtime assets and historical releases for a complete checkout."""
from datetime import datetime, timezone
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/'artifacts/distribution'


def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def build():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sources = {name: ROOT/name for name in ['data/workbench.sqlite', 'artifacts/next-phase/baseline/workbench-v01.sqlite']}
    for name in ['DS', 'strain', 'TSR', 'residual']:
        relative = f'artifacts/models/{name}.joblib'; sources[relative] = ROOT/relative
    sources.update({p.relative_to(ROOT).as_posix(): p for p in (ROOT/'frontend/dist').rglob('*') if p.is_file()})
    legacy = json.loads((ROOT/'artifacts/review-phase/baseline.json').read_text(encoding='utf-8'))['v02_release']
    releases = [legacy, {'path': 'artifacts/release/asphalt-workbench-0.3.0-20261019T073332.zip',
                         'sha256': '72e7e05a9c338d456f648e66bbcdb22b48e39d6be28254d1a665c9a5ea56e68e'}]
    for item in releases:
        path = ROOT/item['path']; assert sha(path) == item['sha256']; sources[item['path']] = path
    frozen = json.loads((ROOT/'configs/research_workbench_v5.json').read_text(encoding='utf-8'))['evidence']['baseline']
    assert sha(ROOT/frozen['path']) == frozen['sha256']
    archive = OUTPUT/'runtime-assets.zip'
    with tempfile.TemporaryDirectory(prefix='.snapshot-', dir=OUTPUT) as temporary:
        stage = Path(temporary).resolve(); assert stage.is_relative_to(OUTPUT.resolve())
        demo = stage/'demo.sqlite'
        with closing(sqlite3.connect((ROOT/'artifacts/review-phase/demo.sqlite').as_uri()+'?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(demo)) as destination: source.backup(destination)
        sources['artifacts/review-phase/demo.sqlite'] = demo
        entries = []
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
            for name, path in sorted(sources.items()):
                assert path.is_file(), name
                entries.append({'path': name, 'bytes': path.stat().st_size, 'sha256': sha(path),
                    'preserve_existing': name in ['data/workbench.sqlite', 'artifacts/review-phase/demo.sqlite'] or name.startswith('frontend/dist/')})
                bundle.write(path, name)
    manifest = {'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(), 'application_version': '0.4.0',
        'archive': {'path': 'artifacts/distribution/runtime-assets.zip', 'bytes': archive.stat().st_size, 'sha256': sha(archive)},
        'files': entries, 'scope': 'Existing runtime snapshots, frozen research input, research-only models, frontend build, historical final releases.',
        'restoration': 'python scripts/restore_published_assets.py',
        'notes': ['Existing mutable databases are preserved. No credentials, dependency folders, or temporary QA databases are bundled.',
                  'Material experiments remain optional; snapshots do not add material measurements.']}
    (OUTPUT/'runtime-assets.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'files': len(entries), 'zip_bytes': archive.stat().st_size, 'sha256': manifest['archive']['sha256']}))


if __name__ == '__main__':
    build()
