"""Record evidence-backed execution separately from the frozen development plan."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROGRESS = ROOT / 'artifacts/next-phase/execution_progress.json'


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['initialize', 'start', 'complete', 'show'])
    parser.add_argument('--task')
    parser.add_argument('--evidence', nargs='*', default=[])
    parser.add_argument('--note', default='')
    args = parser.parse_args()
    plan_path = ROOT / 'planning/next_phase_backlog_v2.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if PROGRESS.exists():
        progress = json.loads(PROGRESS.read_text(encoding='utf-8'))
    else:
        progress = {
            'plan_sha256': hashlib.sha256(plan_path.read_bytes()).hexdigest(), 'started_at': now(),
            'status': 'active', 'source_plan': 'planning/next_phase_backlog_v2.json',
            'time_note': 'Timestamps and wall_elapsed_seconds describe automated execution; human effective hours remain unknown.',
            'tasks': {t['id']: {'title': t['title'], 'priority': t['priority'], 'status': 'planned',
                                'started_at': None, 'completed_at': None, 'actual_hours': None,
                                'completion_evidence': [], 'notes': []} for t in plan['tasks']},
        }
    assert progress['plan_sha256'] == hashlib.sha256(plan_path.read_bytes()).hexdigest(), 'Plan changed; reconcile execution explicitly.'
    if args.action in ['start', 'complete']:
        definition = next(t for t in plan['tasks'] if t['id'] == args.task)
        task = progress['tasks'][args.task]
        assert all(progress['tasks'][dep]['status'] == 'complete' for dep in definition['dependencies']), 'Dependencies incomplete.'
        if args.action == 'start':
            assert task['status'] != 'complete', 'Task already complete.'
            if definition['priority'] == 'core':
                assert not any(t['status'] == 'in_progress' and t['priority'] == 'core'
                               for key, t in progress['tasks'].items() if key != args.task), 'Core WIP limit is one.'
            task['status'] = 'in_progress'
            task['started_at'] = task['started_at'] or now()
        else:
            assert task['status'] == 'in_progress' and args.evidence, 'Start task and supply verified evidence first.'
            evidence = []
            for relative in args.evidence:
                path = (ROOT / relative).resolve()
                path.relative_to(ROOT)
                assert path.is_file(), f'Evidence must be an existing file: {relative}'
                evidence.append({'path': relative, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            task['status'], task['completed_at'] = 'complete', now()
            task['wall_elapsed_seconds'] = round((datetime.fromisoformat(task['completed_at']) - datetime.fromisoformat(task['started_at'])).total_seconds(), 3)
            task['completion_evidence'] = evidence
        if args.note:
            task['notes'].append(args.note)
    progress['updated_at'] = now()
    progress['summary'] = {
        'core_completed': sum(t['status'] == 'complete' and t['priority'] == 'core' for t in progress['tasks'].values()),
        'core_total': 21,
        'research_completed': sum(t['status'] == 'complete' and t['priority'] != 'core' for t in progress['tasks'].values()),
        'in_progress': [key for key, t in progress['tasks'].items() if t['status'] == 'in_progress'],
    }
    if progress['summary']['core_completed'] == progress['summary']['core_total']:
        progress['status'] = 'complete_core_prototype_scope'
        progress['core_completed_at'] = progress.get('core_completed_at') or now()
        progress['research_disposition'] = 'deferred_by_user_capacity_choice'
        progress['human_validation'] = 'N18 completed as disclosed AI proxy; human timing and industry benefit remain unmeasured.'
    if args.action != 'show':
        PROGRESS.parent.mkdir(parents=True, exist_ok=True)
        PROGRESS.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(progress['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
