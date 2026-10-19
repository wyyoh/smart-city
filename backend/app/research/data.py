"""Freeze official historical labels and design-only inputs for fair experiments."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

import numpy as np
from sqlmodel import Session, create_engine, select

from ..ml.features import FEATURES, design_features, source_groups, training_rows
from ..services import latest_dataset
from ..settings import ROOT
from ..storage import Measurement, Recipe, now

METRICS = ['DS', 'strain', 'TSR', 'residual']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def load_data(database):
    path = Path(database).resolve()
    engine = create_engine('sqlite://', creator=lambda: sqlite3.connect(path.as_uri() + '?mode=ro', uri=True))
    with Session(engine) as session:
        ds = latest_dataset(session)
        recipes = session.exec(select(Recipe).where(Recipe.dataset_id == ds.id, Recipe.kind == 'historical')).all()
        grouping = source_groups(recipes)
        labels = {m: training_rows(session, ds.id, m) for m in METRICS}
        ids = sorted(set().union(*(set(v[3]) for v in labels.values())))
        by_id = {r.id: r for r in recipes}
        X = np.array([design_features(by_id[r]) for r in ids])
        Y = np.full((len(ids), 4), np.nan)
        index = {r: i for i, r in enumerate(ids)}
        provenance = {}
        for t, metric in enumerate(METRICS):
            _, y, _, mids, prov, _ = labels[metric]
            provenance[metric] = prov
            for rid, value in zip(mids, y):
                Y[index[rid], t] = value
        rows = [by_id[r].model_dump() for r in ids]
        groups = np.array([grouping[r] for r in ids])
        metadata = {'dataset_id': ds.id, 'dataset_sha256': ds.sha256, 'dataset_revision': ds.revision,
                    'importer_version': ds.importer_version, 'recipe_count': len(recipes)}
    engine.dispose()
    return {'X': X, 'Y': Y, 'ids': ids, 'groups': groups, 'recipes': rows,
            'label_provenance': provenance, 'metadata': metadata}


def audit(data):
    X, Y, groups = data['X'], data['Y'], data['groups']
    signatures = {}
    for i, row in enumerate(X):
        key = tuple(None if np.isnan(x) else round(float(x), 8) for x in row)
        signatures.setdefault(key, []).append(i)
    collisions = []
    for indices in signatures.values():
        if len(indices) > 1:
            spans = []
            for t in range(4):
                values = Y[indices, t]
                values = values[np.isfinite(values)]
                spans.append(float(np.ptp(values)) if len(values) >= 2 else None)
            collisions.append({'ids': [data['ids'][i] for i in indices], 'label_ranges': dict(zip(METRICS, spans))})
    pairwise = {}
    for a in range(4):
        for b in range(a + 1, 4):
            keep = np.isfinite(Y[:, a]) & np.isfinite(Y[:, b])
            pairwise[f'{METRICS[a]}:{METRICS[b]}'] = {'n': int(keep.sum()), 'pearson': float(np.corrcoef(Y[keep, a], Y[keep, b])[0, 1])}
    return {'created_at': now(), **data['metadata'], 'union_labeled_rows': len(Y),
            'union_groups': len(set(groups)), 'complete_four_metric_rows': int(np.isfinite(Y).all(axis=1).sum()),
            'labels_by_metric': {m: {'n': int(np.isfinite(Y[:, t]).sum()),
                                     'groups': len(set(groups[np.isfinite(Y[:, t])]))} for t, m in enumerate(METRICS)},
            'missing_design_counts': dict(zip(FEATURES, np.isnan(X).sum(axis=0).tolist())),
            'flags': dict(Counter(flag for r in data['recipes'] for flag in r['payload']['flags'])),
            'exact_design_collisions': collisions, 'pairwise_label_correlation_descriptive_only': pairwise,
            'limitations': ['Historical operational keys are not confirmed independent material batches.',
                           'Grouping uses source codes and shared complete nonzero ingredient profiles; physical identity is unconfirmed.',
                           'Source codes, measured voids, other test outcomes and specimen identities never enter design X.',
                           'Existing aggregation and exclusions are retained; no deletion based on prediction errors.',
                           'No external or synthetic labels are added. Correlations do not establish transfer or causality.']}


def freeze_inputs(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    path = output / 'frozen-inputs.json'
    protected = [ROOT / '再生沥青混合料实验数据表.xlsx', ROOT / 'artifacts/models/model_cards.json',
                 *sorted((ROOT / 'artifacts/models').glob('*.joblib')),
                 ROOT / 'artifacts/next-phase/baseline/workbench-v01.sqlite',
                 ROOT / 'artifacts/review-phase/final-handoff.json',
                 ROOT / 'backend/app/ml/features.py', ROOT / 'backend/app/ml/train.py', ROOT / 'backend/app/ml/predict.py']
    current = {p.relative_to(ROOT).as_posix(): sha(p) for p in protected}
    if path.exists():
        old = json.loads(path.read_text(encoding='utf-8'))
        if old['protected_sha256'] != current:
            raise ValueError('Frozen inputs changed; use a new research version.')
        return old
    payload = {'created_at': now(), 'protected_sha256': current,
               'scope': 'Offline experiments only. Existing production artifacts and historical evidence stay frozen.'}
    dump(path, payload)
    return payload
