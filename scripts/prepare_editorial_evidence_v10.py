"""Collect existing case and research evidence for the editorial revision."""
from pathlib import Path
import gzip
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT/'artifacts/polish-v7/runs/20261022T045051Z'
OUT = ROOT/'artifacts/editorial-v10'
METRICS = ['DS', 'strain', 'TSR', 'residual']


def load(name):
    path = RUN/name
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if name.endswith('.gz') else data)


def main():
    cases = []
    for case in ['C1', 'C2', 'C3', 'C4', 'C5']:
        record = load(case+'.json.gz')
        decision = record['decision']
        rows = []
        for identity in decision['comparison']['feasible_ids']:
            row = next(r for r in decision['results'] if r['id'] == identity)
            fields = {k: v['value'] for k, v in row['scheme']['fields'].items()}
            rows.append({
                'id': row['id'], 'display_id': row['display_id'], 'source': fields['source_code'],
                'product': fields['product'], 'gradation': fields['gradation'],
                'oil_pct': fields['oil_stone_ratio_pct'], 'rap_nominal_pct': fields['rap_nominal_pct'],
                'values': {k: next(c['value'] for c in row['checks'] if c['metric'] == k) for k in METRICS},
                'front': row['pareto_front'], 'rank': row['preference_rank'],
                'source_fields': row['scheme']['fields'],
            })
        cases.append({'id': case, 'title': record['title'], 'request': record['run_request'],
                      'scene': decision['demand']['request']['scene'],
                      'targets': decision['demand']['targets'],
                      'priority': decision['demand']['priority'],
                      'summary': decision['summary'], 'pool': decision['pool_summary'],
                      'diagnosis': decision['diagnosis']['status'], 'candidates': rows,
                      'baseline_feasible': len(record['baseline']['feasible_ids']),
                      'same_feasible_set': record['baseline']['same_feasible_set'],
                      'snapshot': (RUN/(case+'.json.gz')).relative_to(ROOT).as_posix()})
    complete = load('C5-complete-numeric.json.gz')['decision']
    draft = load('C2-design-draft.json.gz')
    research = {
        'metric_names': ['动稳定度 DS', '最大弯拉应变', '冻融劈裂比 TSR', '残留稳定度'],
        'units': ['次/mm', 'με', '百分点', '百分点'],
        'mean_baseline_mae': [1565.867, 286.594, 3.540, 2.889],
        'original_pipeline_mae': [1681.512, 313.601, 3.782, 3.170],
        'conservative_ensemble_mae': [1545.025, 273.002, 3.494, 2.963],
        'rounds_improved': ['4/5', '5/5', '4/5', '0/5'],
        'source': 'docs/research-v04-report.md',
        'sample_sizes': [85, 72, 81, 79], 'eligible_operation_keys': 100,
        'proxy_source_groups': 37, 'complete_four_metric_records': 59,
        'hypotheses': 1098, 'inside_declared_support': 731,
    }
    report = (ROOT/research['source']).read_text(encoding='utf-8')
    for group in ['mean_baseline_mae', 'original_pipeline_mae', 'conservative_ensemble_mae']:
        assert all(f'{value:.3f}' in report for value in research[group])
    first = json.loads((ROOT/'artifacts/research-v04/benchmark.json').read_text(encoding='utf-8'))
    second = json.loads((ROOT/'artifacts/research-v04/advanced.json').read_text(encoding='utf-8'))
    for key, source, model in [
        ('mean_baseline_mae', second, 'basic:mean:'),
        ('original_pipeline_mae', first, 'legacy_nested'),
        ('conservative_ensemble_mae', second, 'fixed_half_ensemble'),
    ]:
        research[key] = [source['summaries'][model][metric]['mae'] for metric in METRICS]
    research['relative_improvement_pct'] = [
        second['summaries']['fixed_half_ensemble'][m]['relative_mae_improvement_vs_mean']*100 for m in METRICS]
    assert [len(c['candidates']) for c in cases] == [2, 2, 5, 1, 0]
    assert all(c['same_feasible_set'] for c in cases)
    assert len(complete['diagnosis']['certificates']) == 4
    assert draft['measured_performance'] is None
    assert draft['parent_recipe_id'] == 'mix_ec30ff644f3111c570bc'
    data = {'cases': cases, 'complete_numeric': {
        'pool': complete['pool_summary'], 'summary': complete['summary'],
        'diagnosis': complete['diagnosis'],
    }, 'draft': {k: draft[k] for k in [
        'parent_recipe_id', 'hypothesis_id', 'actual_changes', 'locked_fields',
        'demand_context', 'measured_performance']}, 'research': research}
    paths = [RUN/(c+'.json.gz') for c in ['C1', 'C2', 'C3', 'C4', 'C5', 'C5-complete-numeric', 'C2-design-draft']]
    paths += [ROOT/'docs/research-v04-report.md', ROOT/'artifacts/polish-v7/completion.json',
              ROOT/'artifacts/submission-v8/verification.json', ROOT/'artifacts/research-v04/benchmark.json',
              ROOT/'artifacts/research-v04/advanced.json']
    data['sources'] = [{'path': p.relative_to(ROOT).as_posix(),
                        'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'evidence.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'cases': [{c['id']: [(r['source'], r['display_id'], r['values']) for r in c['candidates']]} for c in cases],
                      'source_files': len(paths)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
