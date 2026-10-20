"""Verify and restore published assets without overwriting existing user data."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def destination(root, relative):
    parts = PurePosixPath(relative)
    if not relative or '\\' in relative or parts.is_absolute() or '..' in parts.parts or any(':' in p for p in parts.parts):
        raise ValueError('Unsafe asset path: '+relative)
    target = (root/parts).resolve()
    if target == root or not target.is_relative_to(root): raise ValueError('Asset leaves project directory: '+relative)
    return target


def restore(root=ROOT):
    root = Path(root).resolve()
    manifest = json.loads((root/'artifacts/distribution/runtime-assets.json').read_text(encoding='utf-8'))
    archive = destination(root, manifest['archive']['path'])
    if sha(archive) != manifest['archive']['sha256']: raise ValueError('Runtime archive SHA256 mismatch')
    entries = manifest['files']; paths = [e['path'] for e in entries]
    if len(paths) != len(set(paths)): raise ValueError('Duplicate asset paths')
    planned, identical, preserved = [], [], []
    with zipfile.ZipFile(archive) as bundle:
        if len(bundle.namelist()) != len(paths) or set(bundle.namelist()) != set(paths):
            raise ValueError('Archive contents differ from the manifest')
        for entry in entries:
            name = entry['path']; target = destination(root, name)
            info = bundle.getinfo(name)
            with bundle.open(name) as stream: actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if info.file_size != entry['bytes'] or actual != entry['sha256']: raise ValueError('Asset integrity mismatch: '+name)
            if target.exists():
                if not target.is_file(): raise FileExistsError('Asset destination is not a file: '+name)
                if sha(target) == entry['sha256']: identical.append(name)
                elif entry.get('preserve_existing', False): preserved.append(name)
                else: raise FileExistsError('Existing frozen asset differs; preserved without overwrite: '+name)
            else: planned.append((entry, target))
        for entry, target in planned:
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(entry['path']) as source, target.open('xb') as output:
                while chunk := source.read(1024*1024): output.write(chunk)
            if sha(target) != entry['sha256']: raise ValueError('Restored asset integrity mismatch: '+entry['path'])
    return {'status': 'passed', 'restored': [e['path'] for e, _ in planned], 'already_matching': identical,
            'existing_user_files_preserved': preserved}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    result = restore(parser.parse_args().root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
