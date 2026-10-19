"""Conservative next actions, without a probabilistic optimal-experiment claim."""
from ..domain.contracts_v2 import metric_registry


def build_test_plan(results, demand, pool_sha256):
    registry = metric_registry()['metrics']
    definitions = {t['target_id']: t for t in demand['targets']}
    cards = []
    # A known hard failure is not a candidate that merely needs its missing tests completed.
    eligible = sorted([r for r in results if not r['failed_targets']], key=lambda r: (len(r['unknown_targets']), r.get('preference_rank', 1000), r['id']))
    for row in eligible:
        for check in sorted(row['checks'], key=lambda c: (demand['priority'].index(c['metric']) if c['metric'] in demand['priority'] else 100, c['target_id'])):
            target = definitions.get(check['target_id'])
            if target is None:
                if check['state'] in ['missing', 'incomparable']:
                    cards.append({'candidate_id': row['id'], 'display_id': row['display_id'], 'target_id': check['target_id'],
                                  'metric': check['metric'], 'action': 'collect_resource_evidence', 'test_method': None, 'conditions_to_confirm': [],
                                  'reason': check['reason'], 'stop_condition': '出现已知硬要求失败时停止为其补齐可行性证据，重新检查场景或材料版本', 'pool_sha256': pool_sha256})
                continue
            unresolved = check['eligibility']['unresolved_dimensions']
            if check['state'] == 'satisfied' and not unresolved:
                continue
            action = 'confirm_applicability' if check['state'] == 'satisfied' else 'obtain_comparable_test'
            cards.append({'candidate_id': row['id'], 'display_id': row['display_id'], 'target_id': check['target_id'],
                          'metric': check['metric'], 'action': action, 'test_method': target['test_method'],
                          'conditions_to_confirm': sorted(set(unresolved + ['condition.'+k for k in registry[target['metric']]['condition_keys'] if k != 'test_method' and target['conditions'].get(k) is None])),
                          'required_conditions': target['conditions'], 'requirement_source': target['source'],
                          'reason': '数值已满足演示目标，先核实原试验与工程适用；无法核实时另行试验' if action == 'confirm_applicability' else
                                    '该要求影响当前可行性判断，优先取得同方法条件的有效证据；不使用预测值补齐实测',
                          'stop_condition': '任一当前硬要求出现已知失败则停止补齐；全部要求及工艺证据满足后转工程师审核，不能直接批准施工',
                          'pool_sha256': pool_sha256})
    return {'strategy': 'explainable_base_rules', 'status': 'software_workflow_only', 'cards': cards,
            'excluded_known_failure_ids': [r['id'] for r in results if r['failed_targets']],
            'order_basis': '先处理未被失败排除且缺项较少的候选，再按场景指标优先序核验。',
            'note': '基础核验行动清单；未验证节约试验数量、最优试验设计或决策价值策略增益。'}
