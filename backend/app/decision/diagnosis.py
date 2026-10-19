"""Pool-scoped certificates use known failures; unknown is never treated as false."""
from itertools import combinations
from .records import digest


def covers(rows, targets):
    return bool(rows) and all(set(row['failed_targets']) & set(targets) for row in rows)


def witness(rows, remaining):
    eligible = [r for r in rows if not set(r['failed_targets']) & set(remaining)]
    strict = [r for r in eligible if all(next(c['state'] for c in r['checks'] if c['target_id'] == key) == 'satisfied' for key in remaining)]
    row = min(strict or eligible, key=lambda r: r['id'])
    return {'candidate_id': row['id'], 'display_id': row['display_id'],
            'kind': 'all_remaining_satisfied' if strict else 'not_ruled_out_unknown',
            'remaining_checks': [{'target_id': c['target_id'], 'state': c['state'], 'value': c.get('value')}
                                 for c in row['checks'] if c['target_id'] in remaining]}


def diagnose(results, demand, pool_sha256):
    base = {'pool_sha256': pool_sha256, 'confirmation_sha256': demand['sha256'],
            'scope_note': '仅对本次冻结候选池、当前证据及声明口径成立；不推断材料物理规律，不自动放宽项目目标。'}
    if not demand['ready_for_candidate_retrieval']:
        return {**base, 'status': 'invalid_scene', 'message': '需求存在未解决项', 'certificates': []}
    if not results:
        return {**base, 'status': 'pool_empty', 'message': '检索范围为空，请检查库存、级配或明确不相容条件', 'certificates': []}
    if any(r['passes_known_requirements'] for r in results):
        return {**base, 'status': 'numeric_feasible' if demand['request']['context_kind'] == 'constructed_demo' else 'evidence_feasible',
                'message': '有满足当前可比较要求的候选，工程发布仍须审核和试验', 'certificates': []}
    if any(not r['failed_targets'] for r in results):
        return {**base, 'status': 'evidence_insufficient', 'message': '有候选尚未被已知失败排除；缺测或不可比不能证明无解', 'certificates': []}
    active = sorted(set(key for row in results for key in row['failed_targets']))
    subsets, exhaustive = [], len(active) <= 12
    if exhaustive:
        for size in range(1, len(active) + 1):
            for keys in combinations(active, size):
                if not any(set(existing).issubset(keys) for existing in subsets) and covers(results, keys):
                    subsets.append(list(keys))
    else:
        keys = active[:]
        for key in active:
            reduced = [k for k in keys if k != key]
            if covers(results, reduced):
                keys = reduced
        subsets.append(keys)
    definitions = {t['target_id']: {k: t.get(k) for k in ['metric', 'operator', 'value', 'upper', 'unit', 'source']} for t in demand['targets']}
    certificates = []
    for keys in subsets:
        witnesses = [{'removed_target': key, **witness(results, [k for k in keys if k != key])} for key in keys]
        certificate = {**base, 'target_ids': keys, 'requirements': [definitions.get(k, {'metric': k}) for k in keys],
                       'infeasibility_proven_by': 'each_candidate_has_a_known_failure_in_subset',
                       'minimality_status': 'verified_inclusion_minimal' if all(w['kind'] == 'all_remaining_satisfied' for w in witnesses) else 'minimal_known_failure_cover_only',
                       'deletion_witnesses': witnesses,
                       'candidate_failures': [{'candidate_id': r['id'], 'failed_in_subset': sorted(set(r['failed_targets']) & set(keys))} for r in results]}
        certificate['certificate_sha256'] = digest(certificate)
        certificates.append(certificate)
    return {**base, 'status': 'known_conflict', 'message': '冻结池内每个候选至少有一项已知失败，当前要求联合无解',
            'enumeration_complete': exhaustive, 'certificates': certificates,
            'actions': ['核查目标及方法条件是否录入正确', '补充独立候选或新版本试验', '如需变更正式要求，由工程师另行确认并保留理由']}


def verify_certificate(certificate, results, pool_sha256, confirmation_sha256):
    errors = []
    if certificate['pool_sha256'] != pool_sha256 or certificate['confirmation_sha256'] != confirmation_sha256:
        errors.append('version_binding')
    if digest({k: v for k, v in certificate.items() if k != 'certificate_sha256'}) != certificate['certificate_sha256']:
        errors.append('hash')
    keys = certificate['target_ids']
    if not covers(results, keys):
        errors.append('not_infeasible')
    for key in keys:
        remaining = [k for k in keys if k != key]
        if covers(results, remaining):
            errors.append('not_minimal')
        item = next((w for w in certificate['deletion_witnesses'] if w['removed_target'] == key), None)
        row = next((r for r in results if item and r['id'] == item['candidate_id']), None)
        if row is None or set(row['failed_targets']) & set(remaining):
            errors.append('invalid_witness')
        elif item['kind'] == 'all_remaining_satisfied' and any(c['state'] != 'satisfied' for c in row['checks'] if c['target_id'] in remaining):
            errors.append('unknown_witness_claimed_satisfied')
    if {r['candidate_id']: r['failed_in_subset'] for r in certificate['candidate_failures']} != {r['id']: sorted(set(r['failed_targets']) & set(keys)) for r in results}:
        errors.append('candidate_coverage')
    return {'valid': not errors, 'errors': errors}
