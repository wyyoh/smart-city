"""An auditable review view of frozen evidence; it never grants engineering release."""
from collections import Counter

from fastapi import HTTPException

from ..domain.contracts_v2 import metric_registry
from ..decision.diagnosis import verify_certificate
from ..decision.freshness import decision_freshness
from ..decision.records import digest, get_record
from ..storage import now
from .labels import label

METRIC_NAMES = {'DS': '动稳定度', 'strain': '弯拉应变', 'TSR': 'TSR', 'residual': '残留稳定度',
                'PG_high': '高温PG', 'PG_low': '低温等级', 'fatigue': '疲劳寿命', 'dynamic_modulus': '动态模量'}


def target_review(target, definitions):
    definition = definitions[target['metric']]
    condition_keys = sorted(set(definition['condition_keys']) - {'test_method'})
    missing_conditions = [key for key in condition_keys if target.get('conditions', {}).get(key) in [None, '']]
    issues = []
    if target['source']['kind'] in ['constructed_demo', 'enterprise_reference']:
        issues.append('构造或企业参考要求，项目适用尚待核定')
    if not target['source'].get('confirmed'):
        issues.append('要求出处尚未声明确认')
    if not target.get('test_method'):
        issues.append('试验方法待确认')
    if missing_conditions:
        issues.append('目标条件待补齐：' + '、'.join(label(key) for key in missing_conditions))
    if not definition['numeric_demo_supported']:
        issues.append(definition.get('capability_gap', '现有数据未支持该指标'))
    return {'target_id': target['target_id'], 'metric': target['metric'],
            'label': definition.get('label') or METRIC_NAMES.get(target['metric'], target['metric']),
            'operator': target['operator'], 'value': target['value'], 'upper': target.get('upper'), 'unit': target['unit'],
            'source': target['source'], 'source_confirmation_scope': '本地输入声明，未经独立核验',
            'test_method': target.get('test_method'), 'conditions': target.get('conditions', {}),
            'required_condition_keys': condition_keys, 'missing_conditions': missing_conditions,
            'issues': issues, 'status': 'needs_evidence' if issues else 'declared_complete_pending_review'}


def candidate_review(row):
    fields = row['scheme']['fields']
    checks = []
    for check in row['checks']:
        eligibility = check.get('eligibility', {})
        evidence = row['evidence'].get(check['metric'], {})
        raw = evidence.get('raw_labels', [])
        checks.append({'target_id': check['target_id'], 'metric': check['metric'], 'state': check['state'],
                       'value': check.get('value'), 'unit': check.get('unit'),
                       'engineering_applicability': eligibility.get('status', 'unknown'),
                       'unresolved_dimensions': eligibility.get('unresolved_dimensions', []),
                       'reason': check.get('reason'), 'test_method': evidence.get('method'),
                       'recorded_conditions': evidence.get('structured_conditions', evidence.get('conditions')),
                       'source_kind': evidence.get('source_kind'), 'source_count': len(raw),
                       'source_preview': [{'sheet': s['sheet'], 'cell': s['cell'], 'value': s['value'],
                                           'raw_value': s.get('raw_value'), 'transform': s.get('transform')} for s in raw[:6]],
                       'observation_id': evidence.get('observation_id'),
                       'source_reference': evidence.get('source_reference')})
    unknown_fields = [key for key, value in fields.items() if value.get('value') is None or value.get('status') in ['unknown', 'mass_basis_unconfirmed']]
    return {'id': row['id'], 'display_id': row['display_id'], 'status': row['status'],
            'material_version': row['scheme']['material_version'], 'kind': row['scheme']['kind'],
            'fields': fields, 'component_basis': row['scheme']['component_basis'],
            'material_unknowns': unknown_fields, 'checks': checks,
            'state_counts': dict(Counter(c['state'] for c in checks)),
            'passes_known_requirements': row['passes_known_requirements'],
            'identity_review': '工作簿操作键和产品标识，独立配方、料源与批次身份待外部核实',
            'engineering_release_approved': False}


def build_review(session, decision_id, candidate_id=None):
    decision = get_record(session, decision_id, 'material_decision')
    demand = decision['demand']
    rows = decision['results']
    by_id = {r['id']: r for r in rows}
    if candidate_id and candidate_id not in by_id:
        raise HTTPException(404, '候选不属于此冻结决策')
    ids = [candidate_id] if candidate_id else [i for i in decision['comparison']['review_first_ids'] if i in by_id][:3]
    if not ids and not candidate_id:
        ids = [r['id'] for r in rows if not r['failed_targets']][:3]
    candidates = [candidate_review(by_id[i]) for i in ids]
    definitions = metric_registry()['metrics']
    requirements = [target_review(t, definitions) for t in demand['targets']]
    freshness = decision_freshness(session, decision_id)
    certificate_checks = [verify_certificate(c, rows, decision['pool_sha256'], decision['confirmation_sha256'], demand)
                          for c in decision['diagnosis']['certificates']]
    blocked = []
    if not freshness['current']:
        blocked.append({'id': 'stale', 'title': '重新确认输入和冻结范围', 'reason': '；'.join(freshness['reasons']),
                        'needed': ['新的需求确认与候选池'], 'owner_role': '选材工程师'})
    if demand['request']['context_kind'] == 'constructed_demo':
        blocked.append({'id': 'scene', 'title': '取得真实项目场景与要求', 'reason': '本次为团队构造演示，目标和场景未经项目确认。',
                        'needed': ['工法、层位、结构、气候、交通及病害依据', '适用要求文件、条款和批准依据'], 'owner_role': '养护工程师'})
    incomplete = [r for r in requirements if r['issues']]
    if incomplete:
        blocked.append({'id': 'requirements', 'title': '核对目标出处、方法与条件',
                        'reason': f'{len(incomplete)}项要求仍有待确认内容；本地确认声明不能替代项目批准。',
                        'needed': ['逐目标文件和条款', '试验方法与关键条件', '有依据的审核记录'],
                        'target_ids': [r['target_id'] for r in incomplete], 'owner_role': '项目与材料工程师'})
    if candidates:
        blocked.append({'id': 'identity', 'title': '确认材料身份和组成口径', 'reason': '独立配方、料源、批次及未披露组成需原始台账确认。',
                        'needed': ['配方与试件编号', 'RAP质量基准', '改性剂与助剂资料或未披露说明'],
                        'candidate_ids': ids, 'owner_role': '材料工程师'})
        nonapplicable = [c for c in candidates if any(x['engineering_applicability'] != 'applicable' for x in c['checks'])]
        if nonapplicable:
            blocked.append({'id': 'applicability', 'title': '补齐同口径试验与施工证据',
                            'reason': '存在方法、条件、施工或资源适用性未知/不匹配的记录。',
                            'needed': ['原始试验方法与条件', '设备和施工窗口', '无法核实时安排独立同口径试验'],
                            'candidate_ids': [c['id'] for c in nonapplicable], 'owner_role': '试验与施工工程师'})
    if decision['diagnosis']['status'] == 'evidence_insufficient':
        blocked.append({'id': 'missing', 'title': '先补证据，再判断联合可行', 'reason': '含缺测或不可比记录，当前不能证明整个范围无解。',
                        'needed': ['缺测项目及其适用条件'], 'owner_role': '材料工程师'})
    if decision['diagnosis']['certificates']:
        blocked.append({'id': 'conflict', 'title': '复核冲突要求或扩充独立候选',
                        'reason': '当前证书只证明指定候选范围内的冲突；调整正式要求需要批准依据。',
                        'needed': ['删除见证原值', '项目目标复核或新增独立候选'], 'owner_role': '项目与材料工程师'})
    blocked.append({'id': 'release', 'title': '工程师审核与独立验证',
                    'reason': '原型不执行工程批准；软件自测不证明现场性能。',
                    'needed': ['实际审核记录', '独立材料试验及适用施工核验'], 'owner_role': '项目负责人'})
    body = {'schema_version': '3.0', 'review_version': 'review-3.0.0', 'generated_at': now(),
            'decision_id': decision['id'], 'decision_sha256': decision['sha256'],
            'decision_created_at': decision['created_at'], 'name': demand['request']['name'],
            'context_kind': demand['request']['context_kind'], 'scene': demand['request']['scene'],
            'scope': decision['scope'], 'pool_summary': decision['pool_summary'],
            'pool_sha256': decision['pool_sha256'], 'confirmation_sha256': decision['confirmation_sha256'],
            'requirements': requirements, 'diagnosis': decision['diagnosis'],
            'certificate_checks': certificate_checks, 'freshness': freshness,
            'numerical_summary': {'feasible_count': len(decision['comparison']['feasible_ids']),
                                  'candidate_count': len(rows),
                                  'states': dict(Counter(c['state'] for r in rows for c in r['checks'])),
                                  'rule': decision['comparison']['rule']},
            'focus_candidates': candidates, 'focus_selection': '指定候选' if candidate_id else '至多三个优先复核或无已知失败候选',
            'all_candidates_url': f'/v2/records/{decision_id}',
            'actions': blocked, 'test_plan': decision.get('test_plan', {}),
            'engineering_release_approved': False, 'status': 'stale' if not freshness['current'] else 'awaiting_external_review',
            'source_note': '冻结决策中的来源；目标确认与审核人均为本地声明，独立真实性和工程适用尚待核验。',
            'value_validation': {'actor': 'AI software self-test', 'human_participants': 0,
                                  'human_timing': None, 'industry_efficiency_benefit': None},
            'model_note': '现有四项模型外层MAE未优于均值基线；研究预测未参与硬约束通过判定。',
            'export_note': '本复核单按冻结快照生成，附生成时的当前性检查；之后输入变化应重新获取复核单。'}
    body['review_sha256'] = digest(body)
    return body
