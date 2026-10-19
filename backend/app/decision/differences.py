"""Explain actual input -> rule -> requirement -> candidate -> conclusion differences."""
from .records import digest, get_record


def flattened(value, prefix=''):
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            output.update(flattened(item, prefix + '.' + key if prefix else key))
        return output
    return {prefix: value}


def differences(before, after):
    left, right = flattened(before), flattened(after)
    return [{'field': key, 'before': left.get(key), 'after': right.get(key)}
            for key in sorted(set(left) | set(right)) if left.get(key) != right.get(key)]


def compare_decisions(before, after):
    old, new = before['demand'], after['demand']
    inputs = differences({k: v for k, v in old['request'].items() if k not in ['name', 'decision_id', 'segment_id']},
                         {k: v for k, v in new['request'].items() if k not in ['name', 'decision_id', 'segment_id']})
    def rules(demand):
        return sorted([{'id': r['id'], 'version': r['version']} for r in demand['rules']['matches']], key=lambda r: r['id'])
    def targets(demand):
        result = {}
        for target in demand['targets']:
            result.setdefault(target['metric'], []).append({k: v for k, v in target.items() if k not in ['target_id', 'derived_by']})
        return result
    old_targets, new_targets = targets(old), targets(new)
    target_changes = [{'metric': key, 'before': old_targets.get(key, []), 'after': new_targets.get(key, [])}
                      for key in sorted(set(old_targets) | set(new_targets)) if old_targets.get(key) != new_targets.get(key)]
    left, right = {r['id']: r for r in before['results']}, {r['id']: r for r in after['results']}
    def outcome(row):
        return {'status': row['status'], 'checks': sorted([{'metric': c['metric'], 'state': c['state']} for c in row['checks']], key=lambda c: (c['metric'], c['state']))}
    changes = [{'id': key, 'display_id': right[key]['display_id'], 'before': outcome(left[key]), 'after': outcome(right[key])}
               for key in sorted(set(left) & set(right)) if outcome(left[key]) != outcome(right[key])]
    result = {'before_id': before['id'], 'after_id': after['id'], 'before_sha256': before['sha256'], 'after_sha256': after['sha256'],
              'input_changes': inputs, 'rule_changes': [] if rules(old) == rules(new) else [{'before': rules(old), 'after': rules(new)}],
              'target_changes': target_changes,
              'candidate_changes': {'added': sorted(set(right) - set(left)), 'removed': sorted(set(left) - set(right)), 'outcome_changes': changes},
              'conclusion_changes': differences({'diagnosis': before['diagnosis']['status'], 'review_first_ids': before['comparison']['review_first_ids']},
                                                 {'diagnosis': after['diagnosis']['status'], 'review_first_ids': after['comparison']['review_first_ids']}),
              'manual_overrides': new.get('overrides', []), 'requires_engineer_confirmation': bool(inputs or target_changes),
              'note': '解释两份冻结快照的真实差异；变化是场景规则或人工修改的结果，不是因果效应估计。'}
    result['changed'] = bool(inputs or result['rule_changes'] or target_changes or changes or result['candidate_changes']['added'] or result['candidate_changes']['removed'] or result['conclusion_changes'])
    result['sha256'] = digest(result)
    return result


def get_difference(session, before_id, after_id):
    return compare_decisions(get_record(session, before_id, 'material_decision'), get_record(session, after_id, 'material_decision'))
