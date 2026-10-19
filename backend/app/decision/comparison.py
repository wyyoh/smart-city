"""Compare feasible candidates using transparent priority and nondominance only."""


def compare_feasible(results, demand):
    feasible = [r for r in results if r['passes_known_requirements']]
    targets = {t['target_id']: t for t in demand['targets'] if t['operator'] in ['>', '>=', '<', '<=']}
    target_order = sorted(targets, key=lambda key: (demand['priority'].index(targets[key]['metric'])
                                                  if targets[key]['metric'] in demand['priority'] else 100, key))
    def preference(result):
        checks = {c['target_id']: c for c in result['checks']}
        return tuple(checks[key]['value'] * (1 if targets[key]['operator'] in ['>', '>='] else -1) for key in target_order)
    ordered = sorted(feasible, key=lambda r: (tuple(-v for v in preference(r)), r['id']))
    previous, rank = None, 0
    for result in ordered:
        values = preference(result)
        if values != previous:
            rank += 1
        previous = values
        result['preference_rank'] = rank
        result['tied_with'] = [other['id'] for other in ordered if other['id'] != result['id'] and preference(other) == values]
        result['dominated_by'] = [other['id'] for other in feasible if all(a >= b for a, b in zip(preference(other), values))
                                   and any(a > b for a, b in zip(preference(other), values))]
        result['pareto_front'] = not result['dominated_by']
    return {'feasible_ids': [r['id'] for r in ordered],
            'front_ids': [r['id'] for r in ordered if r['pareto_front']],
            'review_first_ids': [r['id'] for r in ordered if r['preference_rank'] == 1],
            'target_order': target_order, 'rule': '先满足全部硬要求，再按场景优先指标作字典序比较；同值并列，另列非支配集。',
            'unknown_preferences': ['全寿命成本', '碳排放', '寿命与现场表现'],
            'note': '偏好顺序不补偿硬要求失败；演示中的数值可行不等于工程适用。'}
