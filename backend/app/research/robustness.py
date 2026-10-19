"""Acquisition-baseline sensitivity and reusable offline research candidates."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import time

import joblib
import numpy as np
from scipy.spatial.distance import cdist
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from .advanced import advanced_configs, prepare_packs
from .data import METRICS, dump, load_data, sha
from .estimators import ResearchModel, feature_map
from .optimization import config
from ..storage import now


def run_baseline_sensitivity(database, output):
    output = Path(output)
    if (output/'baseline-sensitivity.json').exists(): raise FileExistsError('Sensitivity run already exists.')
    prior = json.loads((output/'protocol.json').read_text(encoding='utf-8'))['sequential_replay']
    protocol = {'created_at': now(), 'seeds': list(range(20261019, 20261119)),
        'policies': ['random_uniform_group', 'random_uniform_recipe', 'space_filling'],
        'budgets': [10, 20, 30], 'initial_groups': 6, 'code_sha256': sha(__file__),
        'scope': 'Conditional finite-pool initialization sensitivity, not 100 independent material datasets.',
        'reason': 'Check whether an apparent acquisition gain depends on choosing uniform groups versus uniform records as the random baseline.',
        'targets': prior['targets'], 'fitting': 'Space-filling scaler and imputer use revealed design rows only; random policies do not fit a surrogate.'}
    dump(output/'baseline-sensitivity-protocol.json', protocol)
    start = time.monotonic(); D = load_data(database)
    keep = np.isfinite(D['Y']).all(axis=1)
    X, truth, groups = D['X'][keep], D['Y'][keep], D['groups'][keep]
    ids = np.array(D['ids'])[keep]; unique = np.array(sorted(set(groups)))
    target = np.array([prior['targets'][m] for m in METRICS]); runs = []
    for seed in protocol['seeds']:
        initial = np.random.default_rng(seed).permutation(unique)[:6]
        for budget in protocol['budgets']:
            for policy in protocol['policies']:
                observed = set(initial); spent = 0; history = []
                rng = np.random.default_rng(seed)
                while spent < budget:
                    available = [g for g in unique if g not in observed and int(np.sum(groups == g)) <= budget-spent]
                    if not available: break
                    candidate = np.flatnonzero(np.isin(groups, available))
                    if policy == 'random_uniform_group': group = str(rng.choice(available))
                    elif policy == 'random_uniform_recipe': group = str(groups[rng.choice(candidate)])
                    else:
                        revealed = np.flatnonzero(np.isin(groups, list(observed)))
                        raw = feature_map(X, 'basic')
                        imputer = SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True)
                        scaler = StandardScaler()
                        Zr = scaler.fit_transform(imputer.fit_transform(raw[revealed]))
                        Zc = scaler.transform(imputer.transform(raw[candidate]))
                        distance = cdist(Zc, Zr).min(axis=1)
                        group = str(groups[candidate[np.argmax(distance)]])
                    query = np.flatnonzero(groups == group)
                    before = sorted(observed); observed.add(group); spent += len(query)
                    # The only hidden-label read is after selecting and paying for the group.
                    actual = truth[query]
                    history.append({'queried_group': group, 'visible_groups_before_query': before,
                        'recipe_ids_revealed': ids[query].tolist(), 'panel_cost': len(query), 'panels_spent': spent,
                        'newly_found_feasible': int(np.all(actual > target, axis=1).sum())})
                runs.append({'seed': seed, 'policy': policy, 'budget': budget, 'initial_groups': initial.tolist(),
                    'panels_spent': spent, 'additional_feasible_found': sum(h['newly_found_feasible'] for h in history), 'history': history})
    summaries = {}
    for policy in protocol['policies']:
        summaries[policy] = {}
        for budget in protocol['budgets']:
            rows = [r for r in runs if r['policy'] == policy and r['budget'] == budget]
            values = np.array([r['additional_feasible_found'] for r in rows])
            summaries[policy][str(budget)] = {'feasible_mean': float(values.mean()), 'feasible_std': float(values.std()),
                'panels_spent_mean': float(np.mean([r['panels_spent'] for r in rows])), 'per_seed_found': values.tolist()}
    differences = {}
    for baseline in protocol['policies'][:2]:
        differences[baseline] = {}
        for budget in protocol['budgets']:
            a = np.array(summaries['space_filling'][str(budget)]['per_seed_found'])
            b = np.array(summaries[baseline][str(budget)]['per_seed_found'])
            differences[baseline][str(budget)] = {'mean_additional_feasible_difference': float(np.mean(a-b)),
                'win_tie_loss_seeds': [int(np.sum(a > b)), int(np.sum(a == b)), int(np.sum(a < b))],
                'scope': 'Monte Carlo initialization sensitivity conditional on one selected fixed historical pool.'}
    result = {'created_at': now(), 'protocol_sha256': sha(output/'baseline-sensitivity-protocol.json'),
              'runs': runs, 'summaries': summaries, 'paired_differences': differences,
              'elapsed_seconds': round(time.monotonic()-start, 3), 'surrogate_fit_count': 0,
              'independent_material_tests': 0, 'independent_historical_cohorts': 1}
    dump(output/'baseline-sensitivity.json', result)
    print(json.dumps({'stage': 'baseline_sensitivity', 'campaigns': len(runs), 'seconds': result['elapsed_seconds']}), flush=True)
    return result


class FixedHalfEnsemble:
    def fit(self, data):
        configs = advanced_configs()
        self.configs = [configs[0]]+[c for c in configs if (c['family'] == 'ridge' and c['params'].get('alpha') == 100)
                      or (c['family'] == 'svr' and c['params'].get('C') == .5)]
        packs, _ = prepare_packs(data)
        self.models = [ResearchModel(c).fit(packs[c['pack']], data['Y'], data['groups']) for c in self.configs]
        return self

    def predict(self, data):
        packs, _ = prepare_packs(data)
        predictions = np.array([m.predict(packs[c['pack']]) for m, c in zip(self.models, self.configs)])
        return .5*predictions[0]+.5*np.median(predictions[1:], axis=0)


def fit_candidates(database, output):
    output = Path(output); folder = output/'models'
    if (output/'candidate-model-cards.json').exists(): raise FileExistsError('Research candidate artifacts already exist.')
    folder.mkdir(exist_ok=True)
    D = load_data(database)
    first = json.loads((output/'benchmark.json').read_text(encoding='utf-8'))
    advanced = json.loads((output/'advanced.json').read_text(encoding='utf-8'))
    cards = []
    with threadpool_limits(limits=1):
        joint = FixedHalfEnsemble().fit(D)
        payload = {'model': joint, 'status': 'research_only', 'dataset': D['metadata'],
                   'training_ids': D['ids'], 'engineering_release_allowed': False,
                   'production_replacement': False, 'scope': 'Full-data fit; historical identities were seen during training.'}
        joblib.dump(payload, folder/'fixed_half_ensemble.joblib')
        restored = joblib.load(folder/'fixed_half_ensemble.joblib')
        assert np.array_equal(restored['model'].predict(D), joint.predict(D))
        cards.append({'artifact': 'models/fixed_half_ensemble.joblib', 'kind': 'adaptive_conservative_ensemble',
                      'validation': advanced['summaries']['fixed_half_ensemble'],
                      'uncertainty': advanced['paired_uncertainty']['fixed_half_ensemble'],
                      'eligible_for_engineering_release': False, 'status': 'research_only'})
        for name, c in [('low_rank', config('reduced_rank', 'compact', alpha=100, rank=1)),
                        ('svr', config('svr', 'compact', C=.5)), ('water_ridge', config('ridge', alpha=100))]:
            model = ResearchModel(c).fit(D['X'], D['Y'], D['groups'])
            joblib.dump({'model': model, 'config': c, 'status': 'research_only', 'dataset': D['metadata'],
                         'training_ids': D['ids'], 'engineering_release_allowed': False}, folder/f'{name}.joblib')
            assert np.array_equal(joblib.load(folder/f'{name}.joblib')['model'].predict(D['X']), model.predict(D['X']))
            cards.append({'artifact': f'models/{name}.joblib', 'config': c,
                          'validation': first['summaries'][c['id']], 'status': 'post_hoc_exploratory_research_only',
                          'eligible_for_engineering_release': False})
        search = json.loads((output/'formulation-search.json').read_text(encoding='utf-8'))
        selected = [h for h in search['hypotheses'] if h['id'] in search['shortlist_for_review_only']]
        recipes, X = [], []
        for h in selected:
            r = deepcopy(D['recipes'][h['parent_index']]); r['id'] = h['id']; r['kind'] = 'research_untested'
            r['oil_stone_ratio_pct'] = h['oil_stone_ratio_pct']
            grade = r['payload']['gradation']; grade['curve'] = h['design_X'][7:]
            grade['design_oil_stone_ratio_pct'] = h['oil_stone_ratio_pct']
            for component, weight in zip(grade['components'], h['nominal_component_weights']): component['nominal_weight'] = weight
            recipes.append(r); X.append(h['design_X'])
        predictions = joint.predict({'recipes': recipes, 'X': np.array(X)})
        dump(output/'shortlist-ensemble-crosscheck.json', {'scope': 'Second weak surrogate crosscheck; neither model validates an untested material.',
            'hypotheses': [{'id': h['id'], 'source_code': h['source_code'], 'old_surrogate_prediction': h['prediction'],
                            'conservative_ensemble_prediction': dict(zip(METRICS, p.tolist())),
                            'measured_performance': None, 'engineering_release_allowed': False} for h, p in zip(selected, predictions)]})
    result = {'created_at': now(), 'models': cards,
              'artifact_sha256': {p.name: sha(p) for p in folder.glob('*.joblib')},
              'serialization_prediction_roundtrip': 'exact', 'independent_material_tests': 0,
              'promotion': 'None. Stable low-temperature signal remains below the preregistered 5% candidate threshold, and all new formulations lack independent measurements.'}
    dump(output/'candidate-model-cards.json', result)
    print(json.dumps({'stage': 'fit_candidates', 'artifacts': len(cards), 'promoted': 0}), flush=True)
    return result
