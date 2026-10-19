from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from app.research_workbench.experiments import OUTPUT, build_source_audit, run_study

parser = argparse.ArgumentParser()
parser.add_argument('command', choices=['audit', 'study'])
parser.add_argument('--output', type=Path, default=OUTPUT)
args = parser.parse_args()
if args.command == 'audit':
    value = build_source_audit(args.output)
    print({k: value[k] for k in ['input_alias_groups', 'groups_with_observed_conflict', 'masked_curve_alias_groups']})
else:
    run_study(args.output)
