"""Local upstream linkage and separate laboratory/field feedback; no external connection implied."""
from datetime import datetime
import json
from typing import Literal

from fastapi import HTTPException
from pydantic import Field, field_validator, model_validator

from ..domain.contracts_v2 import DemandRequest, Model, metric_registry
from ..services import latest_dataset, require_recipe
from ..storage import Dataset, Observation, now
from .demands import resolve_demand
from .materials import material_version
from .records import DecisionRecord, append_record, digest, get_record


class UpstreamRequest(Model):
    request_id: str = Field(min_length=8, max_length=160)
    decision_id: str = Field(min_length=1, max_length=160)
    segment_id: str = Field(min_length=1, max_length=160)
    demand: DemandRequest


class SelectionRequest(Model):
    idempotency_key: str = Field(min_length=8, max_length=160)
    decision_snapshot_id: str
    candidate_id: str
    selected_by: str = Field(min_length=1, max_length=160)
    note: str = Field(min_length=1, max_length=1000)


class FeedbackBase(Model):
    idempotency_key: str = Field(min_length=8, max_length=160)
    decision_snapshot_id: str
    candidate_id: str
    material_version: str
    data_scope: Literal['demo', 'official'] = 'demo'
    observed_at: datetime
    source_reference: str = Field(min_length=1, max_length=1000)
    note: str = Field(default='', max_length=1000)

    @field_validator('observed_at')
    @classmethod
    def timezone_declared(cls, value):
        if value.tzinfo is None:
            raise ValueError('反馈时间须含时区')
        return value


class LabFeedback(FeedbackBase):
    metric: Literal['DS', 'strain', 'TSR', 'residual', 'stability', 'VV', 'VMA', 'flow']
    value: float = Field(ge=0)
    unit: str
    test_group: str = Field(min_length=1, max_length=160)
    test_method: str = Field(min_length=1, max_length=500)
    conditions: dict[str, str | float | None]
    sample_count: int = Field(ge=1, le=10000)

    @field_validator('value', mode='before')
    @classmethod
    def scalar_not_boolean(cls, value):
        if isinstance(value, bool):
            raise ValueError('反馈数值不能是布尔值')
        return value

    @model_validator(mode='after')
    def correct_unit(self):
        definition = metric_registry()['metrics'][self.metric]
        if self.unit != definition['unit'] or (self.unit == '%' and self.value > 100):
            raise ValueError('实验室反馈的单位或数值范围不一致')
        return self


class FieldFeedback(FeedbackBase):
    section_id: str = Field(min_length=1, max_length=160)
    service_days: int = Field(ge=0)
    site_conditions: dict[str, str | float | None]
    performance_note: str = Field(min_length=1, max_length=2000)


class FeedbackReview(Model):
    state: Literal['approved', 'rejected']
    reviewer: str = Field(min_length=1, max_length=160)
    note: str = Field(min_length=1, max_length=1000)
    conditions_confirmed: bool = False
    use_for_decision: bool = False


def idempotent_existing(session, record_id, fingerprint):
    existing = session.get(DecisionRecord, record_id)
    if existing is None:
        return None
    if existing.payload.get('request_fingerprint') != fingerprint:
        raise HTTPException(409, '幂等键已用于其他内容')
    return get_record(session, record_id)


def receive_upstream(session, request: UpstreamRequest):
    payload = request.model_dump(mode='json', by_alias=True)
    fingerprint = digest(payload)
    record_id = 'upst_' + digest(request.request_id)[:28]
    existing = idempotent_existing(session, record_id, fingerprint)
    if existing:
        return existing
    demand = request.demand.model_copy(deep=True)
    if demand.decision_id not in [None, request.decision_id] or demand.segment_id not in [None, request.segment_id]:
        raise HTTPException(422, '上游与需求内部的决策或区段ID不一致')
    demand.decision_id, demand.segment_id = request.decision_id, request.segment_id
    resolution = resolve_demand(session, demand)
    return append_record(session, 'upstream_request', {'request_fingerprint': fingerprint, 'upstream_request': payload,
                         'resolution_id': resolution['id'], 'resolution_sha256': resolution['sha256'],
                         'integration_scope': 'local_contract_mock', 'status': 'awaiting_requirement_confirmation'}, record_id=record_id)


def return_selection(session, upstream_id, request: SelectionRequest):
    upstream = get_record(session, upstream_id, 'upstream_request')
    body = request.model_dump(mode='json')
    fingerprint = digest({'upstream_id': upstream_id, **body})
    record_id = 'sele_' + digest(request.idempotency_key)[:28]
    existing = idempotent_existing(session, record_id, fingerprint)
    if existing:
        return existing
    decision = get_record(session, request.decision_snapshot_id, 'material_decision')
    from .freshness import decision_freshness
    if not decision_freshness(session, decision['id'])['current']:
        raise HTTPException(409, '选择快照已过期，请重新确认需求并生成候选')
    bound = upstream['upstream_request']
    if decision['demand']['request']['decision_id'] != bound['decision_id'] or decision['demand']['request']['segment_id'] != bound['segment_id']:
        raise HTTPException(409, '选择快照不属于同一上游决策和区段')
    if decision['demand']['resolution_id'] != upstream['resolution_id']:
        raise HTTPException(409, '选择快照不属于此上游需求版本')
    row = next((r for r in decision['results'] if r['id'] == request.candidate_id), None)
    if row is None or not row['passes_known_requirements']:
        raise HTTPException(422, '只能返回本次决策中满足可比较要求、待工程审核的候选')
    return append_record(session, 'upstream_selection', {'request_fingerprint': fingerprint, **body,
                         'decision_id': bound['decision_id'], 'segment_id': bound['segment_id'],
                         'maintenance_method': decision['demand']['request']['scene']['maintenance_method'],
                         'material_version': row['scheme']['material_version'], 'context_kind': decision['scope']['context_kind'],
                         'status': 'selected_for_engineer_review', 'engineering_release_approved': False},
                         parent_id=upstream_id, record_id=record_id)


def submit_feedback(session, request: LabFeedback | FieldFeedback):
    body = request.model_dump(mode='json')
    kind = 'lab_feedback' if isinstance(request, LabFeedback) else 'field_feedback'
    fingerprint = digest(body)
    record_id = kind[:4] + '_' + digest(request.idempotency_key)[:28]
    existing = idempotent_existing(session, record_id, fingerprint)
    if existing:
        return existing
    decision = get_record(session, request.decision_snapshot_id, 'material_decision')
    row = next((r for r in decision['results'] if r['id'] == request.candidate_id), None)
    if row is None or row['scheme']['material_version'] != request.material_version:
        raise HTTPException(409, '反馈材料版本与冻结候选不一致')
    if request.data_scope == 'official' and decision['scope']['context_kind'] == 'constructed_demo':
        raise HTTPException(422, '演示决策的反馈须保留演示范围；正式资料请建立正式项目记录')
    return append_record(session, kind, {'request_fingerprint': fingerprint, 'feedback': body, 'state': 'submitted',
                         'data_scope': request.data_scope, 'use_for_decision': False, 'training_eligibility': 'not_granted',
                         'note': '现场反馈不自动替代实验室试验；审核与训练发布均为独立步骤。'},
                         parent_id=decision['id'], dataset_id=decision['scope']['dataset']['id'], record_id=record_id)


def review_feedback(session, feedback_id, request: FeedbackReview):
    feedback = get_record(session, feedback_id)
    if feedback['kind'] not in ['lab_feedback', 'field_feedback']:
        raise HTTPException(422, '此记录不是反馈')
    fingerprint = digest(request.model_dump(mode='json'))
    record_id = 'revw_' + digest(feedback_id)[:28]
    existing = idempotent_existing(session, record_id, fingerprint)
    if existing:
        return existing
    body = feedback['feedback']
    observation_id = None
    if request.use_for_decision:
        if request.state != 'approved' or not request.conditions_confirmed or feedback['kind'] != 'lab_feedback':
            raise HTTPException(422, '只有批准且确认条件的实验室反馈可声明进入选材证据')
        needed = set(metric_registry()['metrics'][body['metric']]['condition_keys']) - {'test_method'}
        if any(body['conditions'].get(k) is None or body['conditions'].get(k) == '' for k in needed):
            raise HTTPException(422, '实验室反馈的关键试验条件尚未完整确认')
        from ..services import recipe_detail
        current = recipe_detail(session, body['candidate_id'])
        if material_version(current) != body['material_version']:
            raise HTTPException(409, '当前材料版本已变化，不能跨版本应用反馈')
        observation_id = 'obs_v2_' + digest(feedback_id)[:28]
        payload = {'recipe_id': body['candidate_id'], 'metric': body['metric'], 'value': body['value'], 'unit': body['unit'],
                   'test_group': body['test_group'], 'method': body['test_method'],
                   'conditions': json.dumps(body['conditions'], ensure_ascii=False, sort_keys=True), 'structured_conditions': body['conditions'],
                   'source_reference': body['source_reference'], 'sample_count': body['sample_count'],
                   'idempotency_key': feedback_id, 'data_scope': body['data_scope'], 'supersedes_id': None, 'note': body['note'],
                   'review': {'state': 'approved', 'reviewer': request.reviewer, 'note': request.note, 'conditions_confirmed': True,
                              'use_for_recommendation': True, 'reviewed_at': now()}, 'v2_feedback_id': feedback_id}
        session.add(Observation(id=observation_id, recipe_id=body['candidate_id'], idempotency_key=feedback_id, state='approved',
                                metric=body['metric'], value=body['value'], unit=body['unit'], data_scope=body['data_scope'],
                                use_for_recommendation=True, payload=payload))
        recipe = require_recipe(session, body['candidate_id'])
        dataset = session.get(Dataset, recipe.dataset_id)
        dataset.revision += 1
        session.add(dataset)
    return append_record(session, 'feedback_review', {'request_fingerprint': fingerprint, 'feedback_id': feedback_id,
                         **request.model_dump(mode='json'), 'observation_id': observation_id,
                         'training_eligibility': 'not_granted', 'model_retraining': 'not_triggered',
                         'scope_note': '现场反馈仅供工程跟踪；新微调正式训练资格与受控再训练本期不开放。'},
                         parent_id=feedback_id, record_id=record_id)
