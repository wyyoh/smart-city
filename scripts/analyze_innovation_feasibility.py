"""Read frozen evidence and diagnose proposed innovation mechanisms.

Writes only its own analysis receipt. Does not train, recommend, or change app data.
"""
import hashlib
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path

from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]


def load(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def main():
    paths = [
        'design/competition_alignment_evidence_v2.json',
        'configs/cases.json',
        'artifacts/models/model_cards.json',
    ]
    evidence, config, cards = [load(p) for p in paths]
    pool = evidence['diagnostic_pool']
    case = next(c for c in config['cases'] if c['id'] == 'C5')
    targets = case['targets']
    metrics = list(targets)
    assert pool and all(
        isinstance(r['metrics'].get(m), (int, float))
        for r in pool for m in metrics
    )

    def survivors(subset):
        return [r['id'] for r in pool if all(
            r['metrics'][m] > targets[m] for m in subset
        )]

    conflicts = []
    for size in range(1, len(metrics) + 1):
        for subset in itertools.combinations(metrics, size):
            if survivors(subset):
                continue
            # For monotone conjunctions, all one-deletion subsets being feasible
            # is sufficient to prove inclusion minimality within this frozen pool.
            deletions = [subset[:i] + subset[i + 1:] for i in range(size)]
            witnesses = [survivors(part) for part in deletions]
            if all(witnesses):
                conflicts.append({
                    'requirements': list(subset),
                    'surviving_candidates': [],
                    'one_requirement_removed': [
                        {'remaining_requirements': list(part), 'candidate_ids': ids}
                        for part, ids in zip(deletions, witnesses)
                    ],
                })

    correlations = []
    for a, b in itertools.combinations(metrics, 2):
        rho = float(spearmanr(
            [r['metrics'][a] for r in pool],
            [r['metrics'][b] for r in pool],
        ).statistic)
        correlations.append({'metrics': [a, b], 'spearman_rho': rho})

    common_ids = set.intersection(*[
        {row['recipe_id'] for row in model['oof_predictions']}
        for model in cards['models']
    ])
    receipt = {
        'status': 'analysis_only_v2_features_not_implemented',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'source_sha256': {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths
        },
        'frozen_diagnostic_pool_sha256': evidence['diagnostic_pool_sha256'],
        'case': case['id'],
        'targets': targets,
        'operator': 'strictly_greater_than',
        'candidate_count': len(pool),
        'single_requirement_candidate_counts': {
            m: len(survivors([m])) for m in metrics
        },
        'all_requirements_candidate_count': len(survivors(metrics)),
        'requirement_subsets_checked': 2 ** len(metrics) - 1,
        'minimal_infeasible_requirement_sets': conflicts,
        'within_pool_correlations': correlations,
        'common_model_eligible_recipe_ids': len(common_ids),
        'diagnostic_pool_ids_common_model_eligible': len(
            common_ids & {r['id'] for r in pool}
        ),
        'model_evidence': [
            {
                'metric': m['metric'], 'n': m['n'], 'groups': m['groups'],
                'selected_outer_mae': m['outer_selected']['mae'],
                'dummy_outer_mae': m['models']['dummy']['mae'],
                'outer_selection_beats_dummy_mae': m['outer_selection_beats_dummy_mae'],
                'deployment_status': m['deployment_status'],
            }
            for m in cards['models']
        ],
        'limitations': [
            'Conflict results apply only to four declared numeric thresholds in the frozen pool.',
            'These thresholds describe a constructed demo, not approved project requirements.',
            'Test conditions, ingredient mass bases, and engineering applicability remain unverified.',
            'Operational recipe keys and source-profile groups are not confirmed independent physical batches.',
            'Correlations are descriptive, without independence-based significance or causal claims.',
            'No automatic target relaxation, new formulation validation, or active-learning gain is demonstrated.',
            'Common OOF IDs establish data eligibility only; existing per-metric folds are not a shared multitask evaluation.',
        ],
    }
    output = ROOT / 'artifacts/innovation-feasibility-diagnostic.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'output': str(output),
        'pool_size': len(pool),
        'single_requirement_candidates': receipt['single_requirement_candidate_counts'],
        'minimal_conflicts': [c['requirements'] for c in conflicts],
        'common_model_eligible_ids': len(common_ids),
        'application_data_changed': False,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
