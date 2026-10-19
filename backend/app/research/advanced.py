"""Adaptive second-round material descriptors and conservative ensembling.

This round is explicitly exploratory after observing round-one results. It reuses
the frozen outer folds for paired comparison, not as a fresh independent test.
"""
from __future__ import annotations

import json
from pathlib import Path
import time

import numpy as np
from scipy.optimize import minimize
from threadpoolctl import threadpool_limits

from .benchmark import REPEATS, grouped_splits, metrics, paired_group_bootstrap
from .data import METRICS, dump, freeze_inputs, load_data, sha
from .estimators import ResearchModel, feature_map
from .optimization import checked_components, config
from ..storage import now

DESCRIPTORS = ['new_coarse_nominal_fraction', 'new_fine_nominal_fraction', 'filler_nominal_fraction',
               'rap_coarse_nominal_fraction', 'rap_fine_nominal_fraction',
               'nominal_harmonic_bulk_density', 'nominal_harmonic_apparent_density',
               'nominal_density_difference', 'nominal_absorption_proxy',
               'new_aggregate_harmonic_bulk_density', 'rap_harmonic_bulk_density', 'new_rap_bulk_density_contrast']


def material_descriptors(recipe):
    components, issue = checked_components(recipe)
    if issue: return np.full(len(DESCRIPTORS), np.nan)
    w, _, rows = components
    bulk = np.array([c.get('density_bulk') if c.get('density_bulk') is not None else np.nan for c in rows])
    apparent = np.array([c.get('density_apparent') if c.get('density_apparent') is not None else np.nan for c in rows])
    active = w > 0
    if not np.isfinite(bulk[active]).all() or not np.isfinite(apparent[active]).all() or (bulk[active] <= 0).any() or (apparent[active] <= 0).any():
        return np.full(len(DESCRIPTORS), np.nan)
    # Inactive ingredient fields are not evidence, and cannot invalidate zero mass.
    bulk[~active] = 1; apparent[~active] = 1
    types = np.array([r['type'] for r in rows])
    rap = np.array(['RAP' in t for t in types])
    new = ~rap
    def harmonic(mask):
        total = w[mask].sum()
        return float(total/np.sum(w[mask]/bulk[mask])) if total > 0 else np.nan
    rb, ra = 1/np.sum(w/bulk), 1/np.sum(w/apparent)
    nr, rr = harmonic(new), harmonic(rap)
    return np.array([w[types == '粗集料'].sum(), w[types == '细集料'].sum(), w[types == '矿粉'].sum(),
                     w[types == '粗RAP料'].sum(), w[types == '细RAP料'].sum(), rb, ra, ra-rb,
                     100*np.sum(w*(1/bulk-1/apparent)), nr, rr, nr-rr])


def advanced_configs():
    original = [config('mean'), config('ridge', alpha=100), config('ridge', alpha=1000),
                config('svr', 'compact', C=.5), config('reduced_rank', 'compact', alpha=100, rank=1),
                config('ridge', 'curve', alpha=1000)]
    out = [{**c, 'pack': 'original'} for c in original]
    for pack in ['material', 'material_compact', 'material_curve']:
        entries = [('ridge', {'alpha': a}) for a in [10, 100, 1000]]
        entries += [('svr', {'C': .5}), ('svr', {'C': 2}),
                    ('task_kernel', {'strength': 0, 'factor': 3, 'noise': .5}),
                    ('task_kernel', {'strength': .3, 'factor': 3, 'noise': .5}),
                    ('reduced_rank', {'alpha': 100, 'rank': 1}), ('extra_trees', {'leaf': 8})]
        for family, params in entries:
            out.append({'id': pack+':'+family+':'+','.join(f'{k}={v}' for k, v in sorted(params.items())),
                        'family': family, 'features': 'curve', 'params': params, 'pack': pack})
    return out


def prepare_packs(D):
    X = D['X']; descriptors = np.array([material_descriptors(r) for r in D['recipes']])
    return {'original': X, 'material': np.column_stack([X[:, :7], descriptors]),
            'material_compact': np.column_stack([feature_map(X, 'compact'), descriptors]),
            'material_curve': np.column_stack([X, descriptors])}, descriptors


def convex_weights(pred, Y, penalty):
    """Fit shared nonnegative weights on inner OOF values, with fixed shrinkage."""
    scale = np.maximum(np.nanstd(Y, axis=0), 1e-6)
    observed = np.isfinite(Y)
    P = pred[:, observed]/np.broadcast_to(scale, Y.shape)[observed]
    truth = Y[observed]/np.broadcast_to(scale, Y.shape)[observed]
    prior = np.full(len(pred), .5/(len(pred)-1)); prior[0] = .5
    def objective(w):
        error = w@P-truth
        # Smooth absolute loss avoids letting extreme DS values set every task's weights.
        root = np.sqrt(error**2+.01)
        return float(root.mean()+penalty*np.sum((w-prior)**2))
    def jac(w):
        error = w@P-truth
        return P@(error/np.sqrt(error**2+.01))/len(truth)+2*penalty*(w-prior)
    result = minimize(objective, prior, jac=jac, method='SLSQP', bounds=[(0, 1)]*len(prior),
                      constraints=[{'type': 'eq', 'fun': lambda w: w.sum()-1, 'jac': lambda w: np.ones_like(w)}],
                      options={'maxiter': 200, 'ftol': 1e-10})
    if not result.success: raise RuntimeError('Convex research stacking failed: '+result.message)
    return result.x


def run_advanced(database, output):
    output = Path(output)
    freeze_inputs(output)
    if (output/'advanced.json').exists(): raise FileExistsError('Advanced run exists; use a new output directory.')
    if not (output/'benchmark.json').exists(): raise FileNotFoundError('Run and preserve round one first.')
    configs = advanced_configs()
    protocol = {'created_at': now(), 'adaptive_round': 2, 'status': 'exploratory_not_fresh_holdout',
        'parent_benchmark_sha256': sha(output/'benchmark.json'), 'code_sha256': sha(__file__),
        'reason': 'Round one showed unstable model selection and input collisions. Add disclosed ingredient descriptors and reduce selection variance.',
        'descriptor_names': DESCRIPTORS,
        'descriptor_basis': 'Declared nominal weights and disclosed pre-mixture ingredient densities; no measured mixture voids or outcomes. Unreconciled profiles yield missing descriptors. These nominal proxies do not confirm the physical RAP/binder mass basis.',
        'configurations': configs, 'outer_repeats': REPEATS, 'outer_folds': 5, 'inner_folds': 3,
        'fixed_ensemble': 'Median of prespecified regularized learner predictions, blended 50% with the mean baseline.',
        'conservative_selector': 'Among prespecified 50%-mean blends, require >=5% lower inner OOF MAE than the mean; otherwise retain mean.',
        'convex_stack': 'Shared nonnegative weights across tasks, sum=1; inner OOF smooth absolute loss standardized by training-label SD; fixed L2 penalties 1 and 10 toward a 50%-mean prior.',
        'promotion': 'No automatic model promotion. This adaptive repeat of existing folds cannot serve as new independent validation.',
        'max_wall_seconds': 900}
    dump(output/'advanced-protocol.json', protocol)
    start = time.monotonic()
    D = load_data(database); Y, groups = D['Y'], D['groups']; packs, descriptors = prepare_packs(D)
    dump(output/'material-descriptor-audit.json', {'names': DESCRIPTORS,
        'missing_counts': np.isnan(descriptors).sum(axis=0).tolist(),
        'rows': [{'id': rid, 'source_profile_reference': r['payload'].get('gradation', {}).get('curve_reference'),
                  'descriptors': [None if np.isnan(v) else float(v) for v in row]} for rid, r, row in zip(D['ids'], D['recipes'], descriptors)]})
    base = np.load(output/'oof-predictions.npz')['pred_0']
    predictions = np.full((len(configs), 5, len(Y), 4), np.nan)
    methods = ['advanced_nested_min', 'fixed_half_ensemble', 'conservative_nested', 'convex_stack_1', 'convex_stack_10']
    outputs = {name: np.full_like(base, np.nan) for name in methods}
    # Fixed before round-two execution; all these are strongly regularized learners.
    members = [i for i, c in enumerate(configs) if (c['family'] == 'ridge' and c['params'].get('alpha') == 100)
               or (c['family'] == 'svr' and c['params'].get('C') == .5)]
    folds, fit_count = [], 0
    with threadpool_limits(limits=1):
        for repeat, seed in enumerate(REPEATS):
            for fold, (tr, te) in enumerate(grouped_splits(D['X'], groups, 5, seed)):
                if time.monotonic()-start > 900: raise TimeoutError('Advanced experiment hard timeout')
                inner = np.full((len(configs), len(tr), 4), np.nan)
                for a, b in grouped_splits(D['X'][tr], groups[tr], 3, 20261019+repeat*10+fold):
                    for i, c in enumerate(configs):
                        X = packs[c['pack']]
                        model = ResearchModel(c).fit(X[tr[a]], Y[tr[a]], groups[tr[a]])
                        inner[i, b] = model.predict(X[tr[b]]); fit_count += 1
                for i, c in enumerate(configs):
                    X = packs[c['pack']]
                    fitted = ResearchModel(c).fit(X[tr], Y[tr], groups[tr])
                    predictions[i, repeat, te] = fitted.predict(X[te]); fit_count += 1
                loss = np.nanmean(abs(inner-Y[None, tr]), axis=1)
                minimum = np.argmin(loss, axis=0)
                half_inner = .5*inner[members]+.5*inner[0]
                half_test = .5*predictions[members, repeat][:, te]+.5*predictions[0, repeat, te]
                half_loss = np.nanmean(abs(half_inner-Y[None, tr]), axis=1)
                conservative = np.argmin(half_loss, axis=0)
                for t in range(4):
                    outputs['advanced_nested_min'][repeat, te, t] = predictions[minimum[t], repeat, te, t]
                    best = conservative[t]
                    outputs['conservative_nested'][repeat, te, t] = half_test[best, :, t] if half_loss[best, t] <= .95*loss[0, t] else predictions[0, repeat, te, t]
                outputs['fixed_half_ensemble'][repeat, te] = .5*np.median(predictions[members, repeat][:, te], axis=0)+.5*predictions[0, repeat, te]
                weights = {}
                for penalty in [1, 10]:
                    # The low-variance stack uses the mean and the same small fixed pool.
                    pool = [0]+members
                    w = convex_weights(inner[pool], Y[tr], penalty)
                    outputs[f'convex_stack_{penalty}'][repeat, te] = np.tensordot(w, predictions[pool, repeat][:, te], axes=(0, 0))
                    weights[str(penalty)] = {'config_ids': [configs[i]['id'] for i in pool], 'weights': w.tolist()}
                folds.append({'repeat': repeat, 'fold': fold, 'train_ids': [D['ids'][i] for i in tr],
                              'test_ids': [D['ids'][i] for i in te], 'stacking': weights,
                              'minimum_selected_configs': [configs[i]['id'] for i in minimum]})
                dump(output/'advanced-progress.json', {'completed_outer_folds': len(folds), 'total_outer_folds': 25,
                     'fits': fit_count, 'seconds': round(time.monotonic()-start, 2)})
                print(json.dumps({'stage': 'advanced', 'completed': len(folds), 'fits': fit_count,
                                  'seconds': round(time.monotonic()-start, 2)}), flush=True)
    summaries = {}
    for name, pred in [*[(c['id'], predictions[i]) for i, c in enumerate(configs)], *outputs.items()]:
        summaries[name] = {}
        for t, m in enumerate(METRICS):
            keep = np.isfinite(Y[:, t]); y = np.tile(Y[keep, t], 5); p = pred[:, keep, t].ravel()
            repeat_mae = [float(np.mean(abs(Y[keep, t]-v[keep, t]))) for v in pred]
            baseline_mae = [float(np.mean(abs(Y[keep, t]-v[keep, t]))) for v in base]
            summaries[name][m] = {**metrics(y, p, m), 'unique_labeled_rows': int(keep.sum()),
                'repeat_mae': repeat_mae, 'relative_mae_improvement_vs_mean': float(1-np.mean(repeat_mae)/np.mean(baseline_mae)),
                'repeats_better_than_mean': int(np.sum(np.array(repeat_mae) < baseline_mae))}
    np.savez_compressed(output/'advanced-oof.npz', **{f'pred_{i}': predictions[i] for i in range(len(configs))}, **outputs)
    dump(output/'advanced-folds.json', folds)
    results = {'created_at': now(), 'protocol_sha256': sha(output/'advanced-protocol.json'),
        'configurations': len(configs), 'fit_count': fit_count, 'summaries': summaries,
        'paired_uncertainty': {name: paired_group_bootstrap(Y, pred, base, groups) for name, pred in outputs.items()},
        'elapsed_seconds': round(time.monotonic()-start, 3),
        'scope': 'Adaptive exploratory round after inspecting round-one outcomes; common folds allow paired comparisons but are not an independent fresh test.',
        'production_model_promotion': False}
    dump(output/'advanced.json', results)
    return results
