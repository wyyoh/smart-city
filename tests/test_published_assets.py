import hashlib
import json
import zipfile

import pytest

from scripts.restore_published_assets import restore


def bundle(root, files):
    folder = root/'artifacts/distribution'; folder.mkdir(parents=True)
    archive = folder/'runtime-assets.zip'
    entries = []
    with zipfile.ZipFile(archive, 'w') as output:
        for name, raw, preserve in files:
            output.writestr(name, raw)
            entries.append({'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'preserve_existing': preserve})
    manifest = {'archive': {'path': 'artifacts/distribution/runtime-assets.zip', 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}, 'files': entries}
    (folder/'runtime-assets.json').write_text(json.dumps(manifest), encoding='utf-8')
    return archive


def test_restore_preserves_user_data_and_verifies_frozen_assets(tmp_path):
    bundle(tmp_path, [('data/workbench.sqlite', b'published snapshot', True), ('frozen/model.bin', b'fixed model', False)])
    (tmp_path/'data').mkdir(); database = tmp_path/'data/workbench.sqlite'; database.write_bytes(b'user changes')
    result = restore(tmp_path)
    assert database.read_bytes() == b'user changes'
    assert result['existing_user_files_preserved'] == ['data/workbench.sqlite']
    assert (tmp_path/'frozen/model.bin').read_bytes() == b'fixed model'
    assert restore(tmp_path)['already_matching'] == ['frozen/model.bin']
    (tmp_path/'frozen/model.bin').write_bytes(b'local changed model')
    with pytest.raises(FileExistsError): restore(tmp_path)
    assert (tmp_path/'frozen/model.bin').read_bytes() == b'local changed model'


def test_restore_rejects_tampered_archive_before_any_write(tmp_path):
    archive = bundle(tmp_path, [('data/seed.bin', b'content', False)])
    archive.write_bytes(archive.read_bytes()+b'tampered')
    with pytest.raises(ValueError, match='SHA256'): restore(tmp_path)
    assert not (tmp_path/'data/seed.bin').exists()


@pytest.mark.parametrize('name', ['../outside.bin', '/absolute.bin', 'C:/outside.bin'])
def test_restore_rejects_paths_outside_checkout(tmp_path, name):
    bundle(tmp_path, [(name, b'content', False)])
    with pytest.raises(ValueError, match='Unsafe'): restore(tmp_path)
