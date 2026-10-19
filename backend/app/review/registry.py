import hashlib
import json
from pathlib import Path

from fastapi import HTTPException

from ..settings import ROOT
from ..services import catalog, latest_dataset


def registry():
    return json.loads((ROOT / 'configs/review_evidence_v3.json').read_text(encoding='utf-8'))


def evidence_path(item):
    path = (ROOT / item['path']).resolve()
    if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
        raise HTTPException(404, '证据文件不可用，请检查交付包是否完整')
    return path


def overview(session):
    data = registry()
    for key, item in data['evidence'].items():
        try:
            path = evidence_path(item)
            current_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            item.update({'integrity': 'verified' if current_hash == item['sha256'] else 'changed',
                         'current_sha256': current_hash, 'download_url': '/v2/review/evidence/' + key})
        except HTTPException:
            item.update({'integrity': 'missing', 'current_sha256': None, 'download_url': None})
    dataset = latest_dataset(session)
    recipes = catalog(session)
    ac13 = [r for r in recipes if r['gradation'].startswith('AC-13') and r['kind'] != 'variant']
    complete = [r for r in ac13 if all(r['metrics'].get(m) is not None for m in ['DS', 'strain', 'TSR', 'residual'])]
    data['current_data'] = {'dataset_id': dataset.id, 'dataset_sha256': dataset.sha256, 'revision': dataset.revision,
                            'historical_keys': sum(r['kind'] != 'variant' for r in recipes),
                            'variants': sum(r['kind'] == 'variant' for r in recipes),
                            'ac13_keys': len(ac13), 'complete_four_metric_ac13_keys': len(complete),
                            'identity_note': '历史操作键，不等同于独立配方或独立批次。'}
    replay = ROOT / 'artifacts/review-phase/verification/cases.json'
    fallback = ROOT / 'artifacts/next-phase/case-reports/summary.json'
    path = replay if replay.is_file() else fallback
    data['case_replay'] = {'artifact': path.relative_to(ROOT).as_posix(),
                           'scope': 'v0.3软件复核' if path == replay else 'v0.2历史软件验收',
                           'data': json.loads(path.read_text(encoding='utf-8'))}
    return data


def download_evidence(key):
    item = registry()['evidence'].get(key)
    if item is None:
        raise HTTPException(404, '证据索引不存在')
    return item, evidence_path(item)
