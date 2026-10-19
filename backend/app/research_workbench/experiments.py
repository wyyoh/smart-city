"""Source-cell audit and a small predeclared, head-wise baseline fallback study."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import time

import numpy as np
from sqlmodel import Session, create_engine, select
from threadpoolctl import threadpool_limits

from ..decision.records import digest
from ..research.benchmark import grouped_splits, metrics, paired_group_bootstrap
from ..research.data import METRICS, audit, dump, load_data, sha
from ..research.estimators import ResearchModel
from ..research.optimization import config
from ..research.robustness import FixedHalfEnsemble
from ..settings import ROOT
from ..storage import Measurement, SourceRow, now

OUTPUT = ROOT/'artifacts/research-workbench'
DATABASE = ROOT/'artifacts/next-phase/baseline/workbench-v01.sqlite'


def protect_previous(output=OUTPUT):
    previous = ROOT/'artifacts/research-v04'
    receipt = json.loads((previous/'completion.json').read_text(encoding='utf-8'))
    for relative, expected in receipt['research_file_sha256'].items():
        if sha(previous/relative) != expected: raise ValueError('Previous research evidence changed: '+relative)
    for key in ['document_sha256', 'code_sha256']:
        for relative, expected in receipt[key].items():
            if sha(ROOT/relative) != expected: raise ValueError('Previous research source changed: '+relative)
    frozen = {'prior_completion_sha256': sha(previous/'completion.json'),
              'workbook_sha256': sha(ROOT/'再生沥青混合料实验数据表.xlsx'),
              'legacy_cards_sha256': sha(ROOT/'artifacts/models/model_cards.json')}
    path = Path(output)/'protected-inputs.json'
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != frozen: raise ValueError('Protected inputs no longer match.')
    else: dump(path, frozen)
    return frozen


def build_source_audit(output=OUTPUT):
    output = Path(output); protect_previous(output)
    D = load_data(DATABASE); summary = audit(D)
    recipes = {r['id']: r for r in D['recipes']}
    row_indices = {rid: i for i, rid in enumerate(D['ids'])}
    engine = create_engine('sqlite://', creator=lambda: sqlite3.connect(DATABASE.as_uri()+'?mode=ro', uri=True))
    with Session(engine) as session:
        measured = session.exec(select(Measurement).where(Measurement.dataset_id == D['metadata']['dataset_id'])).all()
        measurements = {(m.recipe_id, m.metric): m for m in measured}
        issues = []
        for collision in summary['exact_design_collisions']:
            entries = []
            for rid in collision['ids']:
                recipe = recipes[rid]; labels = {}
                for metric in METRICS:
                    record = measurements.get((rid, metric))
                    if not record: continue
                    cells = []
                    for raw in record.payload.get('raw_labels', []):
                        original = session.get(SourceRow, f"{D['metadata']['dataset_id']}:{raw['sheet']}:{raw['row']}")
                        cached = original.payload.get('cells', {}).get(raw['cell'], {}) if original else {}
                        cells.append({**raw, 'cached_formula': cached.get('formula'), 'source_row_exists': original is not None})
                    labels[metric] = {'value': record.value, 'unit': record.unit, 'references': cells,
                                      'aggregation': record.payload.get('aggregation'),
                                      'suspected_derived_mean': record.payload.get('suspected_derived_mean', False),
                                      'test_conditions': 'unverified'}
                grade = recipe['payload'].get('gradation') or {}
                entries.append({'id': rid, 'source_code': recipe['source'], 'gradation': recipe['gradation'],
                    'product': recipe['product'], 'oil_stone_ratio_pct': recipe['oil_stone_ratio_pct'],
                    'rap_nominal_pct': recipe['rap_nominal_pct'], 'source_group': str(D['groups'][row_indices[rid]]),
                    'curve_reference': grade.get('curve_reference'), 'curve_input_masked': 'component_curve_requires_review' in recipe['payload']['flags'],
                    'raw_recorded_curve': grade.get('curve'), 'labels': labels})
            conflicts = [m for m, span in collision['label_ranges'].items() if span is not None and span > .01]
            issues.append({'id': 'issue_'+digest(sorted(collision['ids']))[:16], 'recipe_ids': collision['ids'],
                'state': 'needs_source_confirmation' if conflicts else 'input_alias_without_observed_label_conflict',
                'conflicting_metrics': conflicts, 'label_ranges': collision['label_ranges'], 'entries': entries,
                'questions': [
                    {'field': 'physical_material_and_batch_identity', 'question': '这些操作键是否同一实物材料或独立批次？请给出原料、料堆与批次对应。', 'answer': None, 'reference': None},
                    {'field': 'method_and_conditions', 'question': '请确认试验方法版本、温度、荷载、老化/冻融及压实条件，是否可直接比较。', 'answer': None, 'reference': None},
                    {'field': 'composition_and_rap_basis', 'question': '请确认实际组分、改性/再生剂及掺量、RAP分母和旧/有效结合料口径。', 'answer': None, 'reference': None},
                    {'field': 'label_aggregation', 'question': '请核对试件、均值和组比值关系，说明原表标签及公式的适用范围。', 'answer': None, 'reference': None}],
                'interpretation': '相同已知模型输入不代表材料实物相同；输入曲线被遮蔽时也会产生别名。差异需核对，不自动认定原表错误。'})
    engine.dispose()
    issues.sort(key=lambda item: (-(item['label_ranges'].get('DS') or 0), item['id']))
    result = {'created_at': now(), 'dataset': D['metadata'], 'input_alias_groups': len(issues),
        'groups_with_observed_conflict': sum(bool(i['conflicting_metrics']) for i in issues),
        'masked_curve_alias_groups': sum(any(e['curve_input_masked'] for e in i['entries']) for i in issues),
        'issues': issues, 'confirmation_answers_filled': 0, 'source_records_modified': False,
        'note': '原表、原始标签与既有模型不变。此清单用于补齐证据，不能用来按结果删除不利记录。'}
    dump(output/'source-audit.json', result)
    return result


def pool_configs():
    return [config('ridge', alpha=100), config('ridge', 'curve', alpha=1000),
            config('svr', 'compact', C=.5), config('reduced_rank', 'compact', alpha=100, rank=1)]


def study_protocol():
    return {'version': 'head-fallback-1', 'seeds': list(range(20261030, 20261040)), 'outer_folds': 5,
        'inner_folds': 3, 'learners': pool_configs(), 'weights': [.25, .5, .75],
        'selection': 'For each task, choose the lowest inner OOF MAE from fixed mean/learner blends. Accept only with >=5% inner improvement and negative 95th percentile of paired source-group resampled MAE difference; otherwise predict training-label mean.',
        'bootstrap_draws': 1000, 'max_wall_seconds': 900,
        'comparators': ['same-fold mean', 'unconditional inner best blend', 'fixed half mean/median learner pool', 'previous frozen conservative ensemble refit inside each fold'],
        'scope': 'Adaptive follow-up on the same historical workbook using new internal splits. No independent new material data; gate is not a formal risk guarantee or engineering approval.',
        'measured_thresholds_used_for_gate': False,
        'primary_metrics': ['per-task MAE and RMSE', 'per-task fallback/acceptance frequency', 'same-NMAS subgroup MAE'],
        'external_material_tests': 0}


def subset(D, indices):
    return {'X': D['X'][indices], 'Y': D['Y'][indices], 'groups': D['groups'][indices],
            'recipes': [D['recipes'][i] for i in indices]}


def decide_heads(Y, base, candidates, groups, rng):
    loss = np.nanmean(abs(candidates-Y[None]), axis=1)
    base_loss = np.nanmean(abs(base-Y), axis=0)
    selected = np.argmin(loss, axis=0)
    unique = np.array(sorted(set(groups)))
    draws = rng.integers(0, len(unique), size=(1000, len(unique)))
    accepted, details = [], []
    for t, best in enumerate(selected):
        delta = abs(candidates[best, :, t]-Y[:, t])-abs(base[:, t]-Y[:, t])
        totals = np.array([np.nansum(delta[groups == g]) for g in unique])
        counts = np.array([np.isfinite(Y[groups == g, t]).sum() for g in unique])
        boot = totals[draws].sum(axis=1)/np.maximum(counts[draws].sum(axis=1), 1)
        upper = float(np.quantile(boot, .95))
        improvement = float(1-loss[best, t]/max(base_loss[t], 1e-9))
        passed = improvement >= .05 and upper < 0
        accepted.append(passed)
        details.append({'metric': METRICS[t], 'candidate_index': int(best), 'inner_mae': float(loss[best, t]),
                        'baseline_inner_mae': float(base_loss[t]), 'relative_inner_improvement': improvement,
                        'descriptive_group_bootstrap_upper': upper, 'model_used': bool(passed)})
    return selected, accepted, details


def run_study(output=OUTPUT):
    output = Path(output); protected = protect_previous(output)
    if (output/'head-fallback.json').exists(): raise FileExistsError('Study exists. Use a new output directory for a rerun.')
    protocol = {**study_protocol(), 'created_at': now(), 'code_sha256': sha(__file__), 'protected_inputs': protected}
    dump(output/'head-fallback-protocol.json', protocol)
    D = load_data(DATABASE); X, Y, groups = D['X'], D['Y'], D['groups']
    methods = ['mean', 'inner_min_blend', 'head_gated', 'fixed_half_small_pool', 'previous_v04_ensemble']
    predictions = {m: np.full((10, len(Y), 4), np.nan) for m in methods}
    accepted_rows = np.zeros((10, len(Y), 4), dtype=bool)
    fold_records = []; fits = 0; start = time.monotonic()
    with threadpool_limits(limits=1):
        for repeat, seed in enumerate(protocol['seeds']):
            for fold, (tr, te) in enumerate(grouped_splits(X, groups, 5, seed)):
                if time.monotonic()-start > 900: raise TimeoutError('Head fallback study hard timeout')
                inner_base = np.full((len(tr), 4), np.nan)
                inner = np.full((4, len(tr), 4), np.nan)
                for a, b in grouped_splits(X[tr], groups[tr], 3, seed+fold):
                    inner_base[b] = np.nanmean(Y[tr[a]], axis=0)
                    for i, c in enumerate(protocol['learners']):
                        model = ResearchModel(c).fit(X[tr[a]], Y[tr[a]], groups[tr[a]])
                        inner[i, b] = model.predict(X[tr[b]]); fits += 1
                base = np.broadcast_to(np.nanmean(Y[tr], axis=0), (len(te), 4)).copy()
                fitted_pred = []
                for c in protocol['learners']:
                    fitted_pred.append(ResearchModel(c).fit(X[tr], Y[tr], groups[tr]).predict(X[te])); fits += 1
                fitted_pred = np.array(fitted_pred)
                candidate_inner = np.array([(1-w)*inner_base+w*p for p in inner for w in protocol['weights']])
                candidate_test = np.array([(1-w)*base+w*p for p in fitted_pred for w in protocol['weights']])
                selected, accepted, details = decide_heads(Y[tr], inner_base, candidate_inner, groups[tr], np.random.default_rng(seed+fold*31))
                predictions['mean'][repeat, te] = base
                predictions['fixed_half_small_pool'][repeat, te] = .5*base+.5*np.median(fitted_pred, axis=0)
                old = FixedHalfEnsemble().fit(subset(D, tr))
                predictions['previous_v04_ensemble'][repeat, te] = old.predict(subset(D, te)); fits += len(old.models)
                for t in range(4):
                    predictions['inner_min_blend'][repeat, te, t] = candidate_test[selected[t], :, t]
                    predictions['head_gated'][repeat, te, t] = candidate_test[selected[t], :, t] if accepted[t] else base[:, t]
                    accepted_rows[repeat, te, t] = accepted[t]
                fold_records.append({'repeat': repeat, 'seed': seed, 'fold': fold,
                    'train_ids': [D['ids'][i] for i in tr], 'test_ids': [D['ids'][i] for i in te],
                    'train_groups': sorted(set(groups[tr])), 'test_groups': sorted(set(groups[te])), 'heads': details})
            dump(output/'study-progress.json', {'repeat_complete': repeat+1, 'folds_complete': len(fold_records), 'fits': fits})
            print(json.dumps({'stage': 'head_fallback', 'repeat_complete': repeat+1, 'fits': fits,
                              'seconds': round(time.monotonic()-start, 2)}), flush=True)
    scores = {}
    for name, pred in predictions.items():
        assert np.isfinite(pred).all()
        scores[name] = {}
        for t, m in enumerate(METRICS):
            keep = np.isfinite(Y[:, t]); truth = np.tile(Y[keep, t], 10)
            repeated = [float(np.mean(abs(p[keep, t]-Y[keep, t]))) for p in pred]
            baseline = [float(np.mean(abs(p[keep, t]-Y[keep, t]))) for p in predictions['mean']]
            scores[name][m] = {**metrics(truth, pred[:, keep, t].ravel(), m), 'unique_labeled_rows': int(keep.sum()),
                'repeat_mae': repeated, 'relative_mae_improvement': float(1-np.mean(repeated)/np.mean(baseline)),
                'repeats_better_than_mean': int(np.sum(np.array(repeated) < baseline)),
                'nmas_subgroups': {str(int(n)): {'n': int(np.sum(keep & (X[:, 2] == n))),
                    'mae': float(np.mean(abs(pred[:, keep & (X[:, 2] == n), t]-Y[None, keep & (X[:, 2] == n), t])))}
                    for n in sorted(set(X[keep, 2]))}}
    np.savez_compressed(output/'head-fallback-oof.npz', **predictions, accepted=accepted_rows)
    dump(output/'head-fallback-folds.json', fold_records)
    result = {'created_at': now(), 'protocol_sha256': sha(output/'head-fallback-protocol.json'), 'dataset': D['metadata'],
        'fits': fits, 'outer_folds': len(fold_records), 'scores': scores,
        'head_acceptance_fraction': {m: float(accepted_rows[:, np.isfinite(Y[:, t]), t].mean()) for t, m in enumerate(METRICS)},
        'paired_differences': {name: paired_group_bootstrap(Y, p, predictions['mean'], groups) for name, p in predictions.items() if name != 'mean'},
        'elapsed_seconds': round(time.monotonic()-start, 3), 'production_model_promoted': False,
        'limits': ['New folds on the same historical workbook are internal follow-up, not external validation.',
                   'Fallback is a research model-selection rule; it does not guarantee improved error or engineering safety.',
                   'Means and predictions do not validate any new formulation.', 'All four task errors and same-NMAS subgroup errors are reported, including regressions.']}
    dump(output/'head-fallback.json', result)
    return result
