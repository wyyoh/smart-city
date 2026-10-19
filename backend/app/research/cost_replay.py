"""Adaptive cost-matched historical replay; no laboratory results are invented."""
from __future__ import annotations

import json
from pathlib import Path
import time

import numpy as np
from scipy.spatial.distance import cdist
from scipy.stats import rankdata
from threadpoolctl import threadpool_limits

from .data import dump, load_data, sha
from .estimators import ResearchModel, feature_map
from .optimization import choose_next, config
from ..storage import now


def run_cost_replay(database, output):
    output = Path(output)
    if (output/'cost-replay.json').exists(): raise FileExistsError('Cost replay already exists.')
    prior = json.loads((output/'protocol.json').read_text(encoding='utf-8'))['sequential_replay']
    policies = ['random_uniform_group', 'space_filling', 'predicted_mean', 'upper_confidence', 'boundary_uncertainty', 'diversity_ucb']
    protocol = {'created_at': now(), 'adaptive_round': 2, 'scope': 'Exploratory historical cohort; no fresh holdout or physical tests.',
                'reason': 'Equal group-query budgets can consume different numbers of historical recipe panels. Match record-panel budgets explicitly.',
                'seeds': prior['seeds'], 'budgets_additional_recipe_panels': [10, 20, 30],
                'initial_groups': 6, 'policies': policies, 'targets': prior['targets'],
                'cost': 'One historical recipe with four recorded target labels is one panel. Whole-source groups are revealed together and cost their number of panels.',
                'budget_rule': 'Only select a group whose full panel cost fits remaining budget. Report actual spent and unspent panels.',
                'diversity_ucb': 'Equal rank-weight of distance to visible designs and minimum normalized predicted upper margin.',
                'random_baseline': 'Uniform over available source groups, not over rows; duplicates do not get extra random selection weight.',
                'code_sha256': sha(__file__)}
    dump(output/'cost-replay-protocol.json', protocol)
    start = time.monotonic(); D = load_data(database)
    complete = np.isfinite(D['Y']).all(axis=1)
    X, truth, groups = D['X'][complete], D['Y'][complete], D['groups'][complete]
    ids = np.array(D['ids'])[complete]; unique = np.array(sorted(set(groups)))
    targets = np.array([prior['targets'][m] for m in ['DS', 'strain', 'TSR', 'residual']])
    fixed = config('task_kernel', strength=.3, factor=3, noise=.5)
    runs, fits = [], 0
    with threadpool_limits(limits=1):
        for seed in prior['seeds']:
            initial = np.random.default_rng(seed).permutation(unique)[:6]
            initial_rows = np.flatnonzero(np.isin(groups, initial))
            for budget in [10, 20, 30]:
                for policy in policies:
                    observed = set(initial); visible = np.full_like(truth, np.nan)
                    visible[initial_rows] = truth[initial_rows]
                    rng = np.random.default_rng(seed); spent = 0; history = []
                    while spent < budget:
                        available = [g for g in unique if g not in observed and np.sum(groups == g) <= budget-spent]
                        if not available: break
                        candidate = np.flatnonzero(np.isin(groups, available))
                        revealed = np.flatnonzero(np.isin(groups, list(observed)))
                        fitted = ResearchModel(fixed).fit(X[revealed], visible[revealed], groups[revealed]); fits += 1
                        mean, std = fitted.predict_with_std(X)
                        Z = fitted.scaler.transform(fitted.imputer.transform(feature_map(X, fixed['features'])))
                        scale = np.maximum(np.nanstd(visible[revealed], axis=0), 1e-6)
                        if policy == 'random_uniform_group':
                            selected_group = str(rng.choice(available)); selected = int(np.flatnonzero(groups == selected_group)[0])
                        elif policy == 'diversity_ucb':
                            diversity = cdist(Z[candidate], Z[revealed]).min(axis=1)
                            upper = ((mean[candidate]+std[candidate]-targets)/scale).min(axis=1)
                            value = rankdata(diversity)+rankdata(upper)
                            selected = int(candidate[np.argmax(value)])
                        else: selected = choose_next(policy, candidate, revealed, Z, mean, std, targets, scale, rng)
                        group = str(groups[selected]); query = np.flatnonzero(groups == group)
                        before = sorted(observed)
                        # Oracle boundary: no other hidden target values are read by a policy.
                        visible[query] = truth[query]; observed.add(group); spent += len(query)
                        history.append({'queried_group': group, 'visible_groups_before_query': before,
                            'recipe_ids_revealed': ids[query].tolist(), 'actual_values_revealed': truth[query].tolist(),
                            'panel_cost': len(query), 'panels_spent': spent,
                            'newly_found_feasible': int(np.all(visible[query] > targets, axis=1).sum())})
                    found = sum(h['newly_found_feasible'] for h in history)
                    first = next((h['panels_spent'] for h in history if h['newly_found_feasible']), None)
                    runs.append({'seed': seed, 'policy': policy, 'budget': budget, 'initial_groups': initial.tolist(),
                        'panels_spent': spent, 'unspent_panels': budget-spent, 'additional_feasible_found': found,
                        'first_additional_feasible_panels': first, 'group_queries': len(history), 'history': history})
            print(json.dumps({'stage': 'cost_replay', 'seed': seed, 'runs': len(runs), 'fits': fits}), flush=True)
    summaries = {}
    for policy in policies:
        summaries[policy] = {}
        for budget in [10, 20, 30]:
            chosen = [r for r in runs if r['policy'] == policy and r['budget'] == budget]
            summaries[policy][str(budget)] = {'feasible_mean': float(np.mean([r['additional_feasible_found'] for r in chosen])),
                'panels_spent_mean': float(np.mean([r['panels_spent'] for r in chosen])),
                'group_queries_mean': float(np.mean([r['group_queries'] for r in chosen])),
                'per_seed_found': [r['additional_feasible_found'] for r in chosen],
                'first_additional_feasible_panels': [r['first_additional_feasible_panels'] for r in chosen]}
    result = {'created_at': now(), 'protocol_sha256': sha(output/'cost-replay-protocol.json'),
        'runs': runs, 'summaries': summaries, 'fit_count': fits, 'elapsed_seconds': round(time.monotonic()-start, 3),
        'cohort_rows': len(truth), 'cohort_groups': len(unique), 'independent_material_tests': 0,
        'limits': ['Adaptive second round on the same selected historical cohort; not confirmatory external evidence.',
                  'Record-panel budgets do not equal laboratory cost, physical specimens, or person-hours.',
                  'Correlated seed runs and constructed thresholds prohibit claiming general test savings from these averages.']}
    dump(output/'cost-replay.json', result)
    return result
