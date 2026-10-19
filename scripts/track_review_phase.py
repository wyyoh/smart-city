"""Record actual progress separately from the frozen v0.2 and v0.3 plans."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = ROOT / 'artifacts/review-phase/execution_progress.json'


def track(task_id, status, evidence=(), note=None):
    data = json.loads(PROGRESS.read_text(encoding='utf-8'))
    task = data['tasks'][task_id]
    stamp = datetime.now(timezone(timedelta(hours=8))).isoformat()
    if task['started_at'] is None:
        task['started_at'] = stamp
    if status == 'complete':
        assert evidence, 'Completion requires saved evidence.'
        task['evidence'] = []
        for relative in evidence:
            path = (ROOT / relative).resolve()
            path.relative_to(ROOT)
            task['evidence'].append({'path': path.relative_to(ROOT).as_posix(),
                                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        task['completed_at'] = stamp
    task['status'] = status
    if note:
        task.setdefault('notes', []).append(note)
    data['updated_at'] = stamp
    data['summary'] = {'completed': sum(t['status'] == 'complete' for t in data['tasks'].values()),
                       'total': len(data['tasks']),
                       'in_progress': [k for k, t in data['tasks'].items() if t['status'] == 'in_progress']}
    PROGRESS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return data['summary']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('task_id')
    parser.add_argument('status', choices=['in_progress', 'complete'])
    parser.add_argument('--evidence', action='append', default=[])
    parser.add_argument('--note')
    args = parser.parse_args()
    print(json.dumps(track(args.task_id, args.status, args.evidence, args.note)))
