"""Offline diagnostics, honest hidden-label replay and constrained hypotheses."""
from __future__ import annotations

from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path
import time
import warnings

import numpy as np
from scipy.spatial.distance import cdist
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from .benchmark import grouped_splits, metrics, preregister
from .data import METRICS, dump, freeze_inputs, load_data, sha
from .estimators import ResearchModel, configurations, feature_map
from ..storage import now


def config(family, features='basic', **params):
    return next(c for c in configurations() if c['family'] == family and c['features'] == features and c['params'] == params)


def fixed_models():
    return [config('mean'), config('ridge', 'curve', alpha=100), config('ridge', 'compact', alpha=10),
            config('task_kernel', strength=0, factor=3, noise=.5),
            config('task_kernel', strength=.3, factor=3, noise=.5)]


def stage_start(output, name):
    output = Path(output)
    preregister(output)
    if (output/f'{name}.json').exists(): raise FileExistsError(f'{name} exists; use a new output directory.')
    dump(output/f'{name}-start.json', {'started_at': now(), 'protocol_sha256': sha(output/'protocol.json'),
                                      'code_sha256': sha(__file__)})
    warnings.filterwarnings('ignore', message='Mean of empty slice', category=RuntimeWarning)
    return time.monotonic()


def run_diagnostics(database, output):
    output = Path(output); start = stage_start(output, 'diagnostics')
    D = load_data(database); X, Y, groups = D['X'], D['Y'], D['groups']
    unique = np.array(sorted(set(groups))); models = fixed_models()
    learning, negative, intervals = [], [], []
    fits = 0
    with threadpool_limits(limits=1):
        for seed in range(20261019, 20261024):
            rng = np.random.default_rng(seed); shuffled = rng.permutation(unique)
            test_groups = shuffled[:7]; cal_groups = shuffled[7:17]; train_groups = shuffled[17:]
            te = np.flatnonzero(np.isin(groups, test_groups))
            alltrain = np.flatnonzero(~np.isin(groups, test_groups))
            for fraction in [.25, .5, .75, 1]:
                n = max(4, math.ceil(len(shuffled[7:])*fraction))
                tr = np.flatnonzero(np.isin(groups, shuffled[7:][:n]))
                for c in models:
                    fitted = ResearchModel(c).fit(X[tr], Y[tr], groups[tr]); fits += 1
                    train_pred, test_pred = fitted.predict(X[tr]), fitted.predict(X[te])
                    learning.append({'seed': seed, 'fraction': fraction, 'train_groups': n,
                        'train_rows': len(tr), 'test_rows': len(te), 'config': c['id'],
                        'train_mae': np.nanmean(abs(Y[tr]-train_pred), axis=0).tolist(),
                        'test_mae': np.nanmean(abs(Y[te]-test_pred), axis=0).tolist(),
                        'scope': 'Fixed-config exploratory learning curve; not a second independent validation set.'})
            tr = np.flatnonzero(np.isin(groups, train_groups)); ca = np.flatnonzero(np.isin(groups, cal_groups))
            for c in [models[1], models[3], models[4]]:
                fitted = ResearchModel(c).fit(X[tr], Y[tr], groups[tr]); fits += 1
                scale = np.maximum(np.nanstd(Y[tr], axis=0), 1e-6)
                cal_errors = abs(Y[ca]-fitted.predict(X[ca]))/scale
                group_errors = np.array([np.nanmax(cal_errors[groups[ca] == g]) for g in cal_groups])
                rank = math.ceil((len(cal_groups)+1)*.9)
                radius = float(np.sort(group_errors)[rank-1])
                test_errors = abs(Y[te]-fitted.predict(X[te]))/scale
                group_covered = [bool(np.nanmax(test_errors[groups[te] == g]) <= radius) for g in test_groups]
                row_covered = np.nanmax(test_errors, axis=1) <= radius
                complete = np.isfinite(Y[te]).all(axis=1)
                intervals.append({'seed': seed, 'config': c['id'], 'train_groups': train_groups.tolist(),
                    'calibration_groups': cal_groups.tolist(), 'test_groups': test_groups.tolist(),
                    'calibration_rank': rank, 'radius_normalized': radius,
                    'width_by_metric': dict(zip(METRICS, (2*radius*scale).tolist())),
                    'test_groups_count': len(test_groups), 'covered_groups_count': sum(group_covered),
                    'observed_task_group_coverage': float(np.mean(group_covered)),
                    'complete_four_metric_test_rows': int(complete.sum()),
                    'complete_four_metric_covered_rows': int(row_covered[complete].sum()),
                    'complete_four_metric_row_coverage': float(row_covered[complete].mean()) if complete.any() else None,
                    'assumptions': 'Joint maximum over observed tasks and recipes within a group; source-group exchangeability is unconfirmed. Missing targets cannot be checked. No engineering or distribution-shift coverage guarantee.'})
        # Negative controls randomize training label vectors only, never test outcomes.
        for perm in range(20):
            rng = np.random.default_rng(30261019+perm)
            tr, te = grouped_splits(X, groups, 5, 20261019+perm)[0]
            randomized = Y[tr][rng.permutation(len(tr))]
            for c in [models[2], models[4]]:
                fitted = ResearchModel(c).fit(X[tr], randomized, groups[tr]); fits += 1
                pred = fitted.predict(X[te])
                negative.append({'permutation': perm, 'config': c['id'],
                    'mae': np.nanmean(abs(Y[te]-pred), axis=0).tolist(),
                    'r2': [float(r2_score(Y[te, t][np.isfinite(Y[te, t])], pred[:, t][np.isfinite(Y[te, t])])) for t in range(4)],
                    'scope': 'Training-label-vector randomization diagnostic; no permutation p-value or exact group-block null inference.'})
    result = {'created_at': now(), 'learning_curves': learning, 'negative_controls': negative,
              'joint_interval_runs': intervals, 'fit_count': fits, 'elapsed_seconds': round(time.monotonic()-start, 3),
              'production_model_promotion': False, 'independent_material_tests': 0}
    dump(output/'diagnostics.json', result)
    print(json.dumps({'stage': 'diagnostics', 'learning_runs': len(learning), 'negative_controls': len(negative), 'joint_intervals': len(intervals), 'fits': fits}), flush=True)
    return result


def choose_next(policy, candidate_indices, revealed, X, mean, std, targets, scale, rng):
    """This boundary has no hidden-label argument. Deterministic ties use row order."""
    candidates = np.asarray(candidate_indices)
    if policy == 'random': return int(rng.choice(candidates))
    if policy == 'space_filling':
        return int(candidates[np.argmax(cdist(X[candidates], X[revealed]).min(axis=1))])
    margin = (mean[candidates]-targets)/scale
    spread = std[candidates]/scale
    if policy == 'predicted_mean': value = margin.min(axis=1)
    elif policy == 'lower_confidence': value = (margin-spread).min(axis=1)
    elif policy == 'upper_confidence': value = (margin+spread).min(axis=1)
    elif policy == 'boundary_uncertainty':
        value = -np.min(abs(mean[candidates]-targets)/np.maximum(std[candidates], 1e-6), axis=1)
    else: raise ValueError(policy)
    return int(candidates[np.argmax(value)])


def run_replay(database, output):
    output = Path(output); start = stage_start(output, 'replay')
    protocol = json.loads((output/'protocol.json').read_text(encoding='utf-8'))['sequential_replay']
    D = load_data(database); complete = np.isfinite(D['Y']).all(axis=1)
    # Completeness defines this retrospective cohort; target VALUES are hidden until query.
    X, truth, groups = D['X'][complete], D['Y'][complete], D['groups'][complete]
    ids = np.array(D['ids'])[complete]
    unique = np.array(sorted(set(groups)))
    targets = np.array([protocol['targets'][m] for m in METRICS])
    fixed = config('task_kernel', strength=.3, factor=3, noise=.5)
    runs, fits = [], 0
    with threadpool_limits(limits=1):
        for seed in protocol['seeds']:
            initial_groups = np.random.default_rng(seed).permutation(unique)[:protocol['initial_groups']]
            for policy in protocol['policies']:
                observed_groups = set(initial_groups)
                rng = np.random.default_rng(seed)
                visible = np.full_like(truth, np.nan)
                revealed = np.flatnonzero(np.isin(groups, list(observed_groups)))
                visible[revealed] = truth[revealed]
                initial_feasible = int(np.all(visible[revealed] > targets, axis=1).sum())
                history = []
                for step in range(protocol['max_additional_group_queries']):
                    candidates = np.flatnonzero(~np.isin(groups, list(observed_groups)))
                    if not len(candidates): break
                    fitted = ResearchModel(fixed).fit(X[revealed], visible[revealed], groups[revealed]); fits += 1
                    mean, std = fitted.predict_with_std(X)
                    transform = fitted.scaler.transform(fitted.imputer.transform(feature_map(X, fixed['features'])))
                    scale = np.maximum(np.nanstd(visible[revealed], axis=0), 1e-6)
                    selected = choose_next(policy, candidates, revealed, transform, mean, std, targets, scale, rng)
                    group = groups[selected]
                    query = np.flatnonzero(groups == group)
                    # Only here can the label oracle be accessed.
                    visible[query] = truth[query]
                    observed_groups.add(group)
                    revealed = np.flatnonzero(np.isin(groups, list(observed_groups)))
                    history.append({'step': step+1, 'selected_recipe_id': str(ids[selected]), 'queried_group': str(group),
                        'revealed_ids': ids[query].tolist(), 'revealed_actual_values': truth[query].tolist(),
                        'newly_found_feasible': int(np.all(visible[query] > targets, axis=1).sum()),
                        'additional_feasible_found': int(np.all(visible[revealed] > targets, axis=1).sum())-initial_feasible,
                        'additional_recipe_panels_tested': len(revealed)-int(np.isin(groups, initial_groups).sum()),
                        'visible_groups_before_query': sorted(observed_groups-{group})})
                hits = [h['step'] for h in history if h['newly_found_feasible']]
                runs.append({'seed': seed, 'policy': policy, 'initial_groups': initial_groups.tolist(),
                    'initial_feasible_count': initial_feasible, 'first_additional_feasible_step': min(hits) if hits else None,
                    'history': history})
            dump(output/'replay-progress.json', {'completed_seeds': seed-protocol['seeds'][0]+1, 'runs': len(runs), 'fits': fits})
            print(json.dumps({'stage': 'replay', 'seed': seed, 'runs': len(runs), 'fits': fits}), flush=True)
    summaries = {}
    for policy in protocol['policies']:
        selected = [r for r in runs if r['policy'] == policy]
        budgets = {}
        for budget in [5, 10, 15]:
            found, panels = [], []
            for r in selected:
                h = r['history'][min(budget, len(r['history']))-1]
                found.append(h['additional_feasible_found']); panels.append(h['additional_recipe_panels_tested'])
            budgets[str(budget)] = {'feasible_mean': float(np.mean(found)), 'feasible_std': float(np.std(found)),
                                    'recipe_panels_mean': float(np.mean(panels)), 'per_seed_found': found}
        summaries[policy] = {'budgets_group_queries': budgets,
                            'first_additional_feasible_steps': [r['first_additional_feasible_step'] for r in selected]}
    result = {'created_at': now(), 'complete_rows': len(truth), 'source_groups': len(unique),
        'constructed_targets': protocol['targets'], 'seeds': protocol['seeds'], 'runs': runs, 'summaries': summaries,
        'fit_count': fits, 'elapsed_seconds': round(time.monotonic()-start, 3),
        'limitations': ['Retrospective complete-case cohort selected using label availability; not a new or representative population.',
                       'A query reveals all historical records in one source group to prevent same-group leakage.',
                       'Group queries are not physical test counts; recipe-panel counts are also reported and can differ across policies.',
                       'Identical observed initial groups and budgets across policies; seed runs share the same finite historical pool.',
                       'Known original measurements are the only oracle; no surrogate or invented performance is used as truth.',
                       'Targets are constructed demonstrations; these results do not validate a new formulation or general laboratory savings.'],
        'independent_material_tests': 0}
    dump(output/'replay.json', result)
    return result


def checked_components(recipe):
    grade = recipe['payload'].get('gradation')
    if not grade: return None, 'no_disclosed_component_profile'
    if 'component_curve_requires_review' in recipe['payload']['flags']: return None, 'component_curve_requires_review'
    components = grade['components']
    w = np.array([c.get('nominal_weight') or 0 for c in components], dtype=float)
    curves = np.array([c.get('curve') for c in components], dtype=float)
    if curves.shape != (len(w), 12) or not np.isfinite(curves).all(): return None, 'missing_component_curve'
    if (w < 0).any() or abs(w.sum()-1) > 1e-7: return None, 'weights_not_a_normalized_nominal_basis'
    if max(abs(w@curves-np.array(grade['curve']))) > 1e-6: return None, 'recorded_blend_not_reconciled'
    return (w, curves, components), None


def pareto_indices(values):
    """Maximization; exact ties remain nondominated."""
    values = np.asarray(values)
    return [i for i, row in enumerate(values) if not np.any(np.all(values >= row, axis=1) & np.any(values > row, axis=1))]


def propose_local(data):
    X = data['X']; hypotheses, blocked = [], []
    for i, (recipe, row) in enumerate(zip(data['recipes'], X)):
        components, issue = checked_components(recipe)
        if issue:
            blocked.append({'parent_id': recipe['id'], 'reason': issue}); continue
        w, curves, component_rows = components
        variations = []
        for delta in [-.2, -.1, .1, .2]:
            new = row.copy(); new[0] = round(row[0]+delta, 6)
            # Oil-ratio search stays in the observed same-NMAS catalogue range.
            reference = X[X[:, 2] == row[2]]
            if new[0] < reference[:, 0].min() or new[0] > reference[:, 0].max(): continue
            variations.append(('oil_ratio', new, w.copy(), {'oil_stone_ratio_delta_percentage_points': delta}))
        # Transfer a nominal 2% between two disclosed, active NEW aggregate stocks.
        active = [j for j, c in enumerate(component_rows) if w[j] > .02 and 'RAP' not in c['type'] and c['type'] != '矿粉']
        for a, b in itertools.permutations(active, 2):
            changed = w.copy(); changed[a] -= .02; changed[b] += .02
            curve = changed@curves
            if (changed < 0).any() or (curve < -1e-8).any() or (curve > 100+1e-8).any() or (np.diff(curve) > 1e-7).any(): continue
            new = row.copy(); new[7:] = curve
            variations.append(('nominal_blend', new, changed, {'transfer_nominal_fraction': .02, 'from_component': a, 'to_component': b}))
        for kind, new, weights, change in variations:
            digest = hashlib.sha256(json.dumps([recipe['id'], new.tolist(), weights.tolist()], sort_keys=True).encode()).hexdigest()[:16]
            hypotheses.append({'id': 'hyp_'+digest, 'parent_id': recipe['id'], 'parent_index': i,
                'source_code': recipe['source'], 'gradation': recipe['gradation'], 'product': recipe['product'],
                'kind': kind, 'design_X': new.tolist(), 'oil_stone_ratio_pct': float(new[0]),
                'rap_nominal_pct': float(new[1]), 'nominal_component_weights': weights.tolist(),
                'component_sources': [{'row': c['row'], 'type': c['type'], 'size': c['size']} for c in component_rows],
                'change': change, 'measured_performance': None, 'inherits_parent_measurements': False,
                'engineering_state': 'pending_material_basis_and_independent_tests',
                'unknowns': ['RAP mass basis and reclaimed/effective binder quantities', 'material batch identity and test conditions',
                             'modifier/additive composition and construction feasibility'],
                'nominal_weight_sum': float(weights.sum()), 'nominal_rap_fraction_unchanged': bool(np.isclose(sum(weights[j] for j, c in enumerate(component_rows) if 'RAP' in c['type']), sum(w[j] for j, c in enumerate(component_rows) if 'RAP' in c['type']))),
                'engineering_release_allowed': False})
    return hypotheses, blocked


def run_search(database, output):
    output = Path(output); start = stage_start(output, 'formulation-search')
    D = load_data(database); X, Y, groups = D['X'], D['Y'], D['groups']
    hypotheses, blocked = propose_local(D)
    fixed = config('task_kernel', strength=.3, factor=3, noise=.5)
    with threadpool_limits(limits=1):
        model = ResearchModel(fixed).fit(X, Y, groups)
        C = np.array([h['design_X'] for h in hypotheses])
        mean, std = model.predict_with_std(C)
        parent_mean = model.predict(X)
        Z = model.scaler.transform(model.imputer.transform(feature_map(X, fixed['features'])))
        CZ = model.scaler.transform(model.imputer.transform(feature_map(C, fixed['features'])))
        reference = cdist(Z, Z); reference[groups[:, None] == groups[None, :]] = np.inf
        radius = float(np.quantile(reference.min(axis=1), .95))
        distance = cdist(CZ, Z).min(axis=1)
    targets = np.array([6000, 2200, 85, 85])
    scale = np.maximum(np.nanstd(Y, axis=0), 1e-6)
    for j, h in enumerate(hypotheses):
        i = h['parent_index']
        curve_reference = X[(X[:, 2] == X[i, 2]) & np.isfinite(X[:, 7:]).all(axis=1), 7:]
        observed_envelope = len(curve_reference) >= 3 and bool(np.all(C[j, 7:] >= curve_reference.min(axis=0)-1e-8) and np.all(C[j, 7:] <= curve_reference.max(axis=0)+1e-8))
        h.update({'prediction': dict(zip(METRICS, mean[j].tolist())), 'model_std_not_calibrated': dict(zip(METRICS, std[j].tolist())),
            'predicted_change_vs_parent_prediction': dict(zip(METRICS, (mean[j]-parent_mean[i]).tolist())),
            'distance_to_observed_design': float(distance[j]), 'cross_group_distance_reference_p95': radius,
            'within_basic_design_distance_support': bool(distance[j] <= radius+1e-8),
            'within_observed_same_nmas_curve_envelope': observed_envelope,
            'observed_envelope_is_specification': False,
            'research_priority_score': float(np.min((mean[j]-targets)/scale)-.5*np.max(std[j]/scale)),
            'model_state': 'full_data_fit_research_only', 'numeric_predicted_all_targets': bool(np.all(mean[j] > targets)),
            'validation_required_before_any_performance_claim': True})
    supported = [j for j, h in enumerate(hypotheses) if h['within_basic_design_distance_support'] and h['within_observed_same_nmas_curve_envelope']]
    front = pareto_indices(mean[supported])
    for j in supported: hypotheses[j]['predicted_pareto_member'] = False
    for j in front: hypotheses[supported[j]]['predicted_pareto_member'] = True
    ordered = sorted((hypotheses[j] for j in supported), key=lambda h: (-h['research_priority_score'], h['id']))
    shortlist, used = [], set()
    for h in ordered:
        if h['parent_id'] in used: continue
        shortlist.append(h['id']); used.add(h['parent_id'])
        if len(shortlist) == 10: break
    result = {'created_at': now(), 'config': fixed, 'parent_labeled_rows': len(Y),
        'hypothesis_count': len(hypotheses), 'supported_hypothesis_count': len(supported),
        'predicted_pareto_count': len(front), 'blocked_parent_count': len(blocked), 'blocked_parents': blocked,
        'hypotheses': hypotheses, 'shortlist_for_review_only': shortlist,
        'engineering_released_formulations': 0, 'independent_material_tests': 0,
        'elapsed_seconds': round(time.monotonic()-start, 3),
        'limitations': ['The surrogate is weak and fitted to all historical labels; predictions and Pareto membership are research hypotheses.',
                       'No score turns an untested new formulation into a measured or compliant one.',
                       'Only nominal ingredient fractions are conserved; actual dry-aggregate/RAP binder mass accounting requires laboratory confirmation.',
                       'No unknown modifiers, rejuvenator dosages, cost or carbon values are invented.',
                       'Observed curve envelope is a support diagnostic, not a standard or project acceptance envelope.']}
    dump(output/'formulation-search.json', result)
    dump(output/'laboratory-plan.json', laboratory_plan(D, result))
    print(json.dumps({'stage': 'search', 'hypotheses': len(hypotheses), 'supported': len(supported), 'blocked_parents': len(blocked), 'released': 0}), flush=True)
    return result


def laboratory_plan(data, search):
    by_id = {h['id']: h for h in search['hypotheses']}
    families = []
    for key in search['shortlist_for_review_only'][:3]:
        h = by_id[key]; parent = data['recipes'][h['parent_index']]
        siblings = [v for v in search['hypotheses'] if v['parent_id'] == h['parent_id']]
        oil = sorted([v for v in siblings if v['kind'] == 'oil_ratio'], key=lambda v: abs(v['change']['oil_stone_ratio_delta_percentage_points']))[:2]
        blend = [v for v in siblings if v['kind'] == 'nominal_blend'][:2]
        families.append({'source_code': parent['source'], 'parent_id': parent['id'],
                         'nominal_material_identity': {'product': parent['product'], 'gradation': parent['gradation']},
                         'controls': ['freshly prepared parent formulation; do not reuse historical measurements as a concurrent control'],
                         'proposed_hypothesis_ids': [v['id'] for v in oil+blend], 'formulation_count_including_control': 1+len(oil+blend),
                         'independent_preparation_batches_per_formulation_proposed': 3})
    return {'created_at': now(), 'status': 'proposal_not_executed', 'human_or_laboratory_results_fabricated': False,
        'stage_0_required': ['Confirm material source and batch identity, RAP denominator, old binder content and available/activated binder accounting.',
                             'Obtain project-specific target clauses, accepted gradation envelope and material/process restrictions.',
                             'Select laboratory methods and defining temperature, loading, aging and conditioning; record actual specimen counts under the selected methods.',
                             'Verify all disclosed ingredient sieve curves and normalized mass balance on the confirmed physical basis.',
                             'Freeze formulation IDs, target definitions, analysis and holdout batch IDs before measuring outcomes.'],
        'pilot': {'material_families': families[:1], 'scope': 'One family first; three independent preparation batches per formulation proposed, not three dependent specimens presented as independent batches.'},
        'extension_if_pilot_supports': families[1:],
        'blocking_design': 'Block by raw-material lot and preparation day; randomize within block, blind test IDs when practical. Prepare parent and variants concurrently.',
        'outcomes': METRICS, 'primary_analysis': 'Report paired within-block differences, measurement variability, feasibility across all required metrics, and performance of truly held-out batches. Do not choose the best variant and reuse its same measurements as independent validation.',
        'stop_rules': ['Stop and reconcile any mass-balance, method/condition or material-identity mismatch.',
                       'Do not expand a variant that fails a mandatory project metric or construction constraint.',
                       'If differences are smaller than batch/test variability, retain the simpler verified control and collect more informative data.'],
        'prospective_sample_size': 'Three preparation batches is a pilot proposal, not a powered proof or a standards-mandated count; use pilot variability and a predeclared practically relevant margin to plan confirmatory replication.',
        'execution_receipt_template': {'laboratory': None, 'method': None, 'conditions': None, 'material_batch': None,
                                       'preparation_batch': None, 'specimen_count': None, 'raw_data_reference': None,
                                       'operator': None, 'started_at': None, 'finished_at': None},
        'independent_material_tests_executed': 0}


def validate_results(database, output):
    output = Path(output); start = stage_start(output, 'validation')
    freeze_inputs(output)
    D = load_data(database); n = len(D['Y'])
    folds = json.loads((output/'fold-manifest.json').read_text(encoding='utf-8'))
    arrays = np.load(output/'oof-predictions.npz')
    benchmark = json.loads((output/'benchmark.json').read_text(encoding='utf-8'))
    configs = configurations()
    for repeat in range(5):
        seen = []
        for fold in [f for f in folds if f['repeat'] == repeat]:
            assert not set(fold['train_groups']) & set(fold['test_groups'])
            assert not set(fold['train_ids']) & set(fold['test_ids'])
            seen.extend(fold['test_ids'])
        assert sorted(seen) == sorted(D['ids']) and len(seen) == n
    for t, metric in enumerate(METRICS):
        keep = np.isfinite(D['Y'][:, t]); truth = np.tile(D['Y'][keep, t], 5)
        for i, c in enumerate(configs):
            pred = arrays[f'pred_{i}'][:, keep, t].ravel()
            expected = benchmark['summaries'][c['id']][metric]['mae']
            assert math.isclose(float(np.mean(abs(truth-pred))), expected, rel_tol=1e-12)
    replay = json.loads((output/'replay.json').read_text(encoding='utf-8'))
    for r in replay['runs']:
        seen = set(r['initial_groups'])
        for step in r['history']:
            assert step['queried_group'] not in seen
            assert set(step['visible_groups_before_query']) == seen
            seen.add(step['queried_group'])
    search = json.loads((output/'formulation-search.json').read_text(encoding='utf-8'))
    for h in search['hypotheses']:
        assert h['measured_performance'] is None and not h['inherits_parent_measurements'] and not h['engineering_release_allowed']
        assert min(h['nominal_component_weights']) >= 0 and abs(sum(h['nominal_component_weights'])-1) < 1e-7
        assert h['nominal_rap_fraction_unchanged']
        assert np.isfinite(h['design_X']).all()
        assert (np.diff(h['design_X'][7:]) <= 1e-7).all()
    reproduction = output/'reproduction/oof-predictions.npz'
    reproduced = False
    if reproduction.exists():
        again = np.load(reproduction)
        assert set(again.files) == set(arrays.files)
        assert all(np.array_equal(arrays[key], again[key]) for key in arrays.files)
        reproduced = True
    fallacies = [
        {'type': 'Simpson paradox', 'status': 'CAUTION', 'finding': 'Per-metric, per-repeat and group-macro errors exposed; pooled improvements may differ from group behavior.'},
        {'type': 'Ecological fallacy', 'status': 'CAUTION', 'finding': 'Historical operational keys and source-code proxies are not independent physical recipes, batches or regions.'},
        {'type': 'Berkson selection', 'status': 'CAUTION', 'finding': 'Official workbook is a selected historical collection; complete-case replay is more selected still.'},
        {'type': 'Collider bias', 'status': 'CAUTION', 'finding': 'Measured outcomes never enter design predictors; selection on availability can still distort associations.'},
        {'type': 'Base-rate neglect', 'status': 'CHECKED', 'finding': 'Threshold pass/fail prevalence and false-pass counts reported; trivial thresholds cannot establish skill.'},
        {'type': 'Regression to mean', 'status': 'CAUTION', 'finding': 'New variants need concurrent freshly prepared controls; historical extremes cannot prove improvement.'},
        {'type': 'Survivorship bias', 'status': 'CAUTION', 'finding': 'Missing labels and flagged inputs retained in audit; complete-case replay scope explicitly limited.'},
        {'type': 'Look-elsewhere', 'status': 'CAUTION', 'finding': 'All 81 configurations, repeats and negatives published. Post-hoc winner is exploratory; no uncorrected significance claims.'},
        {'type': 'Forking paths', 'status': 'CHECKED', 'finding': 'Protocol/configurations frozen before execution. All later analyses are diagnostics or exploratory; new experiments require new output directories.'},
        {'type': 'Correlation causation', 'status': 'CAUTION', 'finding': 'Multi-task correlations, surrogate changes and retrospective query counts are not causal material or laboratory gains.'},
        {'type': 'Reverse causality', 'status': 'CHECKED', 'finding': 'Design-only pre-test features; no causal attribution or post-test predictors.'}]
    result = {'material_passport': {'origin_skill': 'academic-research-suite/experiment-agent', 'mode': 'validate',
                'version_label': 'research_v04_validation_1', 'verification_status': 'VERIFIED' if reproduced else 'ANALYZED'},
        'created_at': now(), 'checks': {'frozen_production_inputs_unchanged': True, 'group_and_recipe_disjointness_all_25_folds': True,
                                     'all_81_configuration_mae_recomputed': True, 'hidden_label_replay_group_audit': True,
                                     'all_hypotheses_preserve_unknown_measurements_and_nominal_constraints': True,
                                     'full_benchmark_exact_reproduction': reproduced},
        'fallacy_coverage': '11/11', 'fallacy_scan': fallacies, 'independent_material_tests': 0,
        'elapsed_seconds': round(time.monotonic()-start, 3),
        'verdict_scope': 'Reproducible computation and internal data separation only, not material validity or engineering performance.'}
    dump(output/'validation.json', result)
    print(json.dumps(result['checks']), flush=True)
    return result
