"""Offline research CLI; production databases/models are never modified."""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))

from app.research.benchmark import preregister, run_benchmark
from app.research.data import audit, dump, load_data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['freeze', 'benchmark', 'advanced', 'cost-replay', 'baselines', 'fit-candidates', 'diagnostics', 'replay', 'search', 'validate'])
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/research-v04')
    parser.add_argument('--database', type=Path, default=ROOT/'artifacts/next-phase/baseline/workbench-v01.sqlite')
    args = parser.parse_args()
    if args.command == 'freeze':
        protocol = preregister(args.output)
        dump(args.output/'data-audit.json', audit(load_data(args.database)))
        print(f'Frozen protocol: {len(protocol["configurations"])} configurations, 25 outer folds, 3 inner folds.')
    elif args.command == 'benchmark': run_benchmark(args.database, args.output)
    elif args.command == 'advanced':
        from app.research.advanced import run_advanced
        run_advanced(args.database, args.output)
    elif args.command == 'cost-replay':
        from app.research.cost_replay import run_cost_replay
        run_cost_replay(args.database, args.output)
    elif args.command in ['baselines', 'fit-candidates']:
        from app.research.robustness import run_baseline_sensitivity, fit_candidates
        (run_baseline_sensitivity if args.command == 'baselines' else fit_candidates)(args.database, args.output)
    else:
        from app.research.optimization import run_diagnostics, run_replay, run_search, validate_results
        {'diagnostics': run_diagnostics, 'replay': run_replay, 'search': run_search, 'validate': validate_results}[args.command](args.database, args.output)


if __name__ == '__main__': main()
