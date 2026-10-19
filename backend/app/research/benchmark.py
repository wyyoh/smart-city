"""Repeated, nested, source-blocked benchmark with complete negative results."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import time
import warnings

import numpy as np
from sklearn.base import clone
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from threadpoolctl import threadpool_limits

from .data import METRICS, audit, dump, freeze_inputs, load_data, sha
from .estimators import ResearchModel, configurations
from ..ml.train import candidates as legacy_candidates, select_models
from ..settings import ROOT
from ..storage import now

REPEATS = [None, 20261019, 20261020, 20261021, 20261022]
THRESHOLDS = {'DS': [800, 6000, 8000], 'strain': [2000, 2200, 2500], 'TSR': [75, 85, 90], 'residual': [85, 90]}


def grouped_splits(X, groups, folds=5, seed=None):
    return list(GroupKFold(n_splits=folds, shuffle=seed is not None, random_state=seed).split(X, groups=groups))


def complexity(config):
    order = {'mean': 0, 'median': 0, 'ridge': 1, 'bayes_ridge': 2, 'elastic_net': 2,
             'kernel_ridge': 3, 'svr': 4, 'gpr': 4, 'task_kernel': 5,
             'reduced_rank': 5, 'extra_trees': 6, 'hist_boost': 7}
    return (order[config['family']], ['basic', 'compact', 'curve'].index(config['features']), config['id'])


def inner_evaluate(X, Y, groups, configs, seed=20261019, fit_counter=None):
    predictions = np.full((len(configs), len(Y), Y.shape[1]), np.nan)
    for tr, te in grouped_splits(X, groups, 3, seed):
        for c, config in enumerate(configs):
            model = ResearchModel(config).fit(X[tr], Y[tr], groups[tr])
            predictions[c, te] = model.predict(X[te])
            if fit_counter is not None: fit_counter[0] += 1
    loss = np.nanmean(abs(predictions-Y[None, :, :]), axis=1)
    group_loss = np.array([np.nanmean(abs(predictions[:, groups == g]-Y[None, groups == g]), axis=1)
                           for g in sorted(set(groups))])
    se = np.nanstd(group_loss, axis=0, ddof=1)/np.sqrt(np.sum(np.isfinite(group_loss), axis=0))
    return loss, se


def select_indices(loss, se, configs):
    minimum = np.argmin(loss, axis=0)
    one_se = []
    for t, best in enumerate(minimum):
        eligible = np.flatnonzero(loss[:, t] <= loss[best, t]+se[best, t])
        one_se.append(min(eligible, key=lambda i: complexity(configs[i])))
    # Normalize using the same training-only OOF mean baseline; no outer test labels.
    joint = int(np.argmin(np.mean(loss/np.maximum(loss[0], 1e-9), axis=1)))
    return {'nested_min': minimum.tolist(), 'nested_one_se': one_se, 'joint_nested': [joint]*4}


def metrics(y, pred, metric):
    return {'n': len(y), 'mae': float(mean_absolute_error(y, pred)),
            'rmse': float(np.sqrt(mean_squared_error(y, pred))), 'r2': float(r2_score(y, pred)),
            'threshold_diagnostics': {str(t): {
                'actual_pass': int((y > t).sum()), 'actual_fail': int((y <= t).sum()),
                'false_pass': int(((pred > t) & (y <= t)).sum()),
                'false_fail': int(((pred <= t) & (y > t)).sum())} for t in THRESHOLDS[metric]}}


def paired_group_bootstrap(Y, candidate, baseline, groups, seed=20261019):
    # Repeated predictions of one historical key are averaged before cluster resampling.
    candidate_loss = np.nanmean(abs(candidate-Y[None, :, :]), axis=0)
    baseline_loss = np.nanmean(abs(baseline-Y[None, :, :]), axis=0)
    unique = sorted(set(groups))
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(unique), size=(2000, len(unique)))
    results = {}
    for t, m in enumerate(METRICS):
        delta, size = [], []
        for g in unique:
            keep = (groups == g) & np.isfinite(Y[:, t])
            delta.append(float(np.nansum(candidate_loss[keep, t]-baseline_loss[keep, t])))
            size.append(int(keep.sum()))
        delta, size = np.array(delta), np.array(size)
        boot = delta[draws].sum(axis=1)/np.maximum(size[draws].sum(axis=1), 1)
        results[m] = {'candidate_minus_mean_mae': float(delta.sum()/size.sum()),
                      'descriptive_cluster_bootstrap_95_percentiles': np.quantile(boot, [.025, .975]).tolist(),
                      'groups_with_labels': int((size > 0).sum()),
                      'interpretation': 'Conditional descriptive stability of this historical dataset; repeated CV and adaptive research are not independent external validation.'}
    return results


def preregister(output):
    output = Path(output)
    frozen = freeze_inputs(output)
    configs = configurations()
    protocol = {'material_passport': {'origin_skill': 'academic-research-suite/experiment-agent', 'mode': 'plan',
                                     'version_label': 'research_v04_protocol_1', 'verification_status': 'UNVERIFIED'},
                'research_questions': [
                    'Do design-only feature maps and regularized small-sample models improve blocked out-of-fold error over a same-split mean baseline?',
                    'Does a masked multi-task kernel transfer across performance tasks without seeing held-out task labels?',
                    'Can constrained local formulation search and hidden-label sequential testing give useful, honestly bounded research evidence?'],
                'frozen_inputs_manifest_sha256': sha(output/'frozen-inputs.json'),
                'primary_protocol': 'Five outer group folds, three inner group folds; all metrics share recipe/group splits; all preprocessing and task correlations fit on training groups only.',
                'repeats': REPEATS, 'configurations': configs,
                'selectors': ['nested_min', 'nested_one_se', 'joint_nested', 'legacy_nested'],
                'primary_comparison': 'Nested selection procedures versus the same-split mean baseline; each metric reported separately.',
                'secondary_metrics': ['group macro MAE', 'RMSE', 'R2', 'false-pass and false-fail counts at constructed thresholds', 'paired cluster bootstrap descriptive intervals'],
                'exploratory_tables': 'Fixed-configuration rankings are fully reported and are not independent confirmations of a post-hoc winner.',
                'promotion_rule': 'No automatic promotion. A new independent, source-identified material/test dataset is required for engineering claims. An internal candidate needs >=5% MAE improvement, improvement in >=4/5 repeats, and a negative upper descriptive cluster-difference percentile.',
                'sequential_replay': {'seeds': list(range(20261019, 20261029)), 'initial_groups': 6,
                                     'max_additional_group_queries': 15,
                                     'policies': ['random', 'space_filling', 'predicted_mean', 'lower_confidence', 'upper_confidence', 'boundary_uncertainty'],
                                     'targets': {'DS': 6000, 'strain': 2200, 'TSR': 85, 'residual': 85},
                                     'scope': 'Constructed all-greater-than targets on historical complete records. Query one entire group, revealing only that group. Equal initial groups, budgets and real held labels across policies. Not new physical experiments.'},
                'diagnostics': {'learning_curve_train_fractions': [.25, .5, .75, 1], 'negative_control_permutations': 20,
                                'joint_interval_calibration_groups': 10, 'joint_interval_nominal': .9},
                'formulation_search': 'Local oil-ratio/aggregate-weight hypotheses only; same disclosed ingredients, fixed nominal RAP, bounded perturbations, nonnegative normalized weights, mass/curve reconciliation, observed-envelope and distance diagnostics. Unconfirmed basis and weak surrogates block engineering release.',
                'max_wall_seconds': 1800,
                'external_uploads': False, 'independent_material_tests_executed': 0}
    path = output/'protocol.json'
    if path.exists():
        existing = json.loads(path.read_text(encoding='utf-8'))
        if existing != protocol: raise ValueError('Protocol already frozen. Use a new version for changed experiments.')
    else: dump(path, protocol)
    return protocol


def run_benchmark(database, output):
    output = Path(output)
    protocol = preregister(output)
    result_path = output/'benchmark.json'
    if result_path.exists(): raise FileExistsError('Benchmark exists; use a new output directory for another run.')
    start = time.monotonic()
    dump(output/'execution-start.json', {'started_at': now(), 'protocol_sha256': sha(output/'protocol.json'),
         'code_sha256': {p.name: sha(p) for p in Path(__file__).parent.glob('*.py')},
         'command': '.venv/Scripts/python.exe -X utf8 scripts/research_v04.py benchmark'})
    # A group can have no observed value for one task; those group means remain NaN.
    warnings.filterwarnings('ignore', message='Mean of empty slice', category=RuntimeWarning)
    data = load_data(database)
    X, Y, groups = data['X'], data['Y'], data['groups']
    dump(output/'data-audit.json', audit(data))
    dump(output/'row-manifest.json', {'ids': data['ids'], 'groups': groups.tolist(),
         'labels': [[None if np.isnan(v) else float(v) for v in row] for row in Y],
         'label_provenance': data['label_provenance'], 'metadata': data['metadata']})
    configs = protocol['configurations']
    allpred = np.full((len(configs), len(REPEATS), len(Y), 4), np.nan)
    chosen = {name: np.full((len(REPEATS), len(Y), 4), np.nan) for name in protocol['selectors']}
    folds, fit_counter = [], [0]
    with threadpool_limits(limits=1):
        for repeat, seed in enumerate(REPEATS):
            for fold, (tr, te) in enumerate(grouped_splits(X, groups, 5, seed)):
                if time.monotonic()-start > protocol['max_wall_seconds']: raise TimeoutError('Research benchmark hard timeout')
                inner_seed = 20261019+repeat*10+fold
                loss, se = inner_evaluate(X[tr], Y[tr], groups[tr], configs, inner_seed, fit_counter)
                selection = select_indices(loss, se, configs)
                for c, config in enumerate(configs):
                    model = ResearchModel(config).fit(X[tr], Y[tr], groups[tr])
                    allpred[c, repeat, te] = model.predict(X[te])
                    fit_counter[0] += 1
                for name, indices in selection.items():
                    for t, c in enumerate(indices): chosen[name][repeat, te, t] = allpred[c, repeat, te, t]
                legacy_selections = []
                for t in range(4):
                    labeled = tr[np.isfinite(Y[tr, t])]
                    options = legacy_candidates(True)
                    selected, _, _ = select_models(X[labeled], Y[labeled, t], groups[labeled], options)
                    model = clone(options[selected][1]).fit(X[labeled], Y[labeled, t])
                    chosen['legacy_nested'][repeat, te, t] = model.predict(X[te])
                    fit_counter[0] += 3*len(options)+1
                    legacy_selections.append(options[selected][0])
                folds.append({'repeat': repeat, 'seed': seed, 'fold': fold,
                    'train_ids': [data['ids'][i] for i in tr], 'test_ids': [data['ids'][i] for i in te],
                    'train_groups': sorted(set(groups[tr])), 'test_groups': sorted(set(groups[te])),
                    'selection': {name: [configs[i]['id'] for i in indices] for name, indices in selection.items()},
                    'legacy_selection': legacy_selections,
                    'inner_losses': {c['id']: loss[i].tolist() for i, c in enumerate(configs)}})
                dump(output/'progress.json', {'stage': 'benchmark', 'completed_outer_folds': len(folds), 'total_outer_folds': 25,
                                             'research_model_fits': fit_counter[0], 'elapsed_seconds': round(time.monotonic()-start, 2)})
                print(json.dumps({'repeat': repeat, 'fold': fold, 'completed': len(folds), 'fits': fit_counter[0],
                                  'seconds': round(time.monotonic()-start, 2)}), flush=True)
    if not np.isfinite(allpred).all() or any(not np.isfinite(v).all() for v in chosen.values()):
        raise ValueError('Incomplete or non-finite out-of-fold predictions')
    summaries = {}
    for name, predictions in [*[(c['id'], allpred[i]) for i, c in enumerate(configs)], *chosen.items()]:
        score = {}
        for t, metric in enumerate(METRICS):
            keep = np.isfinite(Y[:, t]); y = np.tile(Y[keep, t], len(REPEATS)); pred = predictions[:, keep, t].ravel()
            repeated = [metrics(Y[keep, t], p[keep, t], metric) for p in predictions]
            baseline_losses = np.array([mean_absolute_error(Y[keep, t], p[keep, t]) for p in allpred[0]])
            errors = abs(predictions[:, :, t]-Y[None, :, t])
            score[metric] = {**metrics(y, pred, metric), 'unique_labeled_rows': int(keep.sum()), 'repeats': repeated,
                'group_macro_mae': float(np.nanmean([np.nanmean(errors[:, groups == g]) for g in sorted(set(groups[keep]))])),
                'relative_mae_improvement_vs_mean': float(1-np.mean([s['mae'] for s in repeated])/baseline_losses.mean()),
                'repeats_better_than_mean': int(np.sum(np.array([s['mae'] for s in repeated]) < baseline_losses))}
        summaries[name] = score
    # Serialize loss data without implying each repeat is an independent sample.
    arrays = {f'pred_{i}': allpred[i] for i in range(len(configs))}
    arrays.update(chosen)
    np.savez_compressed(output/'oof-predictions.npz', **arrays)
    dump(output/'fold-manifest.json', folds)
    results = {'material_passport': {'origin_skill': 'academic-research-suite/experiment-agent', 'mode': 'run',
                                   'verification_status': 'UNVERIFIED', 'version_label': 'research_v04_benchmark_1'},
               'created_at': now(), 'protocol_sha256': sha(output/'protocol.json'),
               'code_sha256': {p.name: sha(p) for p in Path(__file__).parent.glob('*.py')},
               'configurations': len(configs), 'outer_folds': len(folds), 'fit_count': fit_counter[0],
               'elapsed_seconds': round(time.monotonic()-start, 3), 'summaries': summaries,
               'paired_uncertainty': {name: paired_group_bootstrap(Y, pred, allpred[0], groups) for name, pred in chosen.items()},
               'production_model_promotion': False,
               'limitations': ['All configurations and failures are retained; post-hoc fixed-model winners are exploratory.',
                               'The same historical keys appear in each repeat; pooled n counts are prediction counts, not new samples.',
                               'Repeated CV and bootstrap do not validate a new laboratory batch or establish engineering coverage.',
                               'Threshold diagnostics use constructed demonstration targets with potentially imbalanced pass/fail prevalence.']}
    dump(result_path, results)
    return results
