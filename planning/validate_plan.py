"""Read-only validation of the development backlog and its resource constraints."""
from collections import Counter
import json
from pathlib import Path

path = Path(__file__).resolve().parent / 'development_backlog_v1.json'
plan = json.loads(path.read_text(encoding='utf-8'))
tasks = plan['tasks']
by_id = {task['id']:task for task in tasks}
assert len(by_id) == len(tasks), 'duplicate task IDs'
weekly, priorities = Counter(), Counter()
visited, active = set(), set()


def visit(code):
    assert code not in active, f'dependency cycle at {code}'
    if code in visited:
        return
    active.add(code)
    current = by_id[code]
    for predecessor in current['dependencies']:
        assert predecessor in by_id, f'missing predecessor {predecessor}'
        dependency = by_id[predecessor]
        assert dependency['week'] <= current['week'], f'week inversion {code}'
        if current['priority'] == 'P0':
            assert dependency['priority'] == 'P0', f'core depends on optional task: {code}'
        visit(predecessor)
    for optional in current['optional_inputs']:
        assert optional in by_id, f'missing optional input {optional}'
        assert by_id[optional]['week'] <= current['week']
    active.remove(code)
    visited.add(code)


for task in tasks:
    visit(task['id'])
    assert task['estimate_hours'] > 0 and task['artifacts'] and task['acceptance']
    assert task['owner'] == 'single_developer'
    if task['priority'] != 'P0':
        assert task['condition'] and task['fallback']
    weekly[task['week']] += task['estimate_hours']
    priorities[task['priority']] += task['estimate_hours']

for key, budget in plan['week_capacity'].items():
    assert weekly[int(key)] == budget['planned_hours']
    assert budget['planned_hours'] + budget['buffer_hours'] == budget['capacity_hours']
assert dict(priorities) == plan['priority_hours']
capacity = plan['capacity_assumptions']
assert sum(weekly.values()) == capacity['planned_hours']
assert sum(b['buffer_hours'] for b in plan['week_capacity'].values()) == capacity['buffer_hours']
assert capacity['planned_hours'] + capacity['buffer_hours'] == capacity['total_hours']
for milestone in plan['milestones']:
    assert all(code in by_id and by_id[code]['week'] <= milestone['week'] for code in milestone['gate_tasks'])
print(json.dumps({'validation':'passed','tasks':len(tasks),'weekly_hours':dict(weekly),'priority_hours':dict(priorities),'planned_hours':capacity['planned_hours'],'buffer_hours':capacity['buffer_hours']},ensure_ascii=False))
