"""Check capacity, dependencies, traceability, and preserved baseline inputs."""
from collections import Counter
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def main():
    plan = read('planning/next_phase_backlog_v2.json')
    protocol = read('planning/innovation_validation_plan_v2.json')
    manifest = read('planning/next_phase_manifest_v2.json')
    page = read('planning/next_phase_page_blocks_v2.json')
    requirements = read('design/competition_requirements_v2.json')['requirements']
    old_tasks = read('planning/v02_alignment_backlog.json')['tasks']
    tasks = plan['tasks']
    by_id = {t['id']: t for t in tasks}
    assert len(by_id) == len(tasks) == 25, 'Task identities must be unique.'
    required_ids = {r['id'] for r in requirements}
    visited, active = set(), set()

    def visit(code):
        assert code not in active, f'Dependency cycle: {code}'
        if code in visited:
            return
        active.add(code)
        t = by_id[code]
        for dep in t['dependencies']:
            assert dep in by_id, f'Unknown dependency: {dep}'
            d = by_id[dep]
            assert d['finish_week'] <= t['start_week'], f'Inverted schedule: {dep} -> {code}'
            if t['priority'] == 'core':
                assert d['priority'] == 'core', f'Core depends on conditional research: {code}'
            visit(dep)
        active.remove(code)
        visited.add(code)

    weekly = {'core': Counter(), 'conditional_research': Counter()}
    hours = Counter()
    for t in tasks:
        visit(t['id'])
        assert t['owner'] == 'single_developer'
        assert t['estimate_hours'] > 0 and t['acceptance'] and t['planned_artifacts']
        assert set(t['requirements']) <= required_ids
        assert not t['completion_evidence'] and t['actual_hours'] is None
        allocations = t['week_allocations']
        assert sum(allocations.values()) == t['estimate_hours']
        assert min(map(int, allocations)) == t['start_week']
        assert max(map(int, allocations)) == t['finish_week']
        for week, amount in allocations.items():
            assert 1 <= int(week) <= 6 and amount > 0
            weekly[t['priority']][int(week)] += amount
        hours[t['priority']] += t['estimate_hours']
        if t['priority'] == 'conditional_research':
            assert t['condition'] and t['fallback'] and t['status'] == 'planned_conditional'
        else:
            assert t['status'] == 'planned'
    assert hours == {'core': 72, 'conditional_research': 30}
    assert sum(t['priority'] == 'core' for t in tasks) == 21
    for week, cap in plan['week_capacity'].items():
        w = int(week)
        assert weekly['core'][w] == cap['core_hours'] == 12
        assert weekly['conditional_research'][w] == cap['conditional_research_hours'] == 5
        assert cap['core_hours'] + cap['buffer_hours'] == cap['baseline_capacity'] == 15
        assert cap['baseline_capacity'] + cap['conditional_research_hours'] == cap['upper_capacity'] == 20
    cap = plan['capacity']
    assert sum(c['buffer_hours'] for c in plan['week_capacity'].values()) == cap['core_buffer_hours'] == 18
    assert cap['core_planned_hours'] + cap['core_buffer_hours'] == cap['baseline_total_hours'] == 90
    assert cap['baseline_total_hours'] + cap['conditional_research_hours'] == cap['upper_total_hours'] == 120
    assert plan['confirmed_constraints']['hours_per_week_range'] == [15, 20]
    for g in plan['milestones']:
        assert g['status'] == 'planned'
        assert all(by_id[x]['priority'] == 'core' and by_id[x]['finish_week'] <= g['week'] for x in g['gate_tasks'])
    assert set(plan['prior_alignment_crosswalk']) == {t['id'] for t in old_tasks}
    for value in plan['prior_alignment_crosswalk'].values():
        assert all(x in by_id for key in ['scheduled', 'conditional'] for x in value.get(key, []))
    covered = {r for t in tasks if t['priority'] == 'core' for r in t['requirements']}
    assert {r['id'] for r in requirements if r['kind'] != 'bonus'} <= covered
    assert len(protocol['negative_cases']) == 12
    assert len({n['id'] for n in protocol['negative_cases']}) == 12
    assert protocol['status'] == 'proposed_protocol_not_executed'
    assert protocol['material_passport']['verification_status'] == 'UNVERIFIED'
    for e in protocol['evaluations']:
        assert set(e['task_ids']) <= set(by_id)
    for path, expected_hash in plan['source_integrity'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected_hash, f'Baseline changed: {path}'
    doc = Path(manifest['local_document'])
    assert hashlib.sha256(doc.read_bytes()).hexdigest() == manifest['document_sha256']
    if manifest.get('page_id'):
        assert manifest['page_synced_document_sha256'] == manifest['document_sha256'], 'Page synchronization needs reconciliation.'
    assert '\n\n'.join(page['blocks']) == doc.read_text(encoding='utf-8').split('\n\n', 1)[1].strip()
    assert len(page['blocks']) == manifest['page_blocks'] <= 95
    receipt = {
        'status': 'passed', 'scope': 'planning_consistency_only_not_product_or_research_acceptance',
        'tasks': len(tasks), 'core_tasks': 21, 'conditional_tasks': 4,
        'weekly_core_hours': dict(weekly['core']), 'weekly_conditional_hours': dict(weekly['conditional_research']),
        'core_hours': 72, 'buffer_hours': 18, 'conditional_hours': 30,
        'dependency_graph': 'acyclic', 'core_has_no_research_dependency': True,
        'all_basic_and_technical_requirements_traced': True,
        'prior_alignment_tasks_crosswalk_complete': True,
        'protected_inputs_unchanged': len(plan['source_integrity']),
        'implementation_tasks_completed': 0, 'experiments_executed': 0,
        'page_source_blocks': len(page['blocks']),
    }
    (ROOT / 'planning/next_phase_plan_checks_v2.json').write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n'
    )
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
