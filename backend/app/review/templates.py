"""Collect external evidence without inventing participants or approving authenticity."""
from datetime import datetime
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from ..domain.contracts_v2 import Model
from ..domain.contracts_v2 import metric_registry


class ProjectEvidence(Model):
    project_id: str | None = None
    scene_reference: str | None = None
    requirement_document: str | None = None
    clause: str | None = None
    approver_reference: str | None = None


class MaterialEvidence(Model):
    candidate_id: str | None = None
    batch_reference: str | None = None
    recipe_reference: str | None = None
    rap_mass_basis: str | None = None


class TestEvidence(Model):
    metric: str | None = None
    method: str | None = None
    conditions: dict[str, str | float | int] = Field(default_factory=dict)
    raw_file_reference: str | None = None


class HumanTask(Model):
    participant_id: str = Field(min_length=1)
    actor: Literal['human']
    task: Literal['routine_selection', 'conflict_review', 'variant_validation']
    workflow: Literal['manual', 'B1', 'V2']
    background: str = Field(min_length=1)
    order: int = Field(ge=1)
    started_at: datetime
    ended_at: datetime
    interruption_seconds: float = Field(default=0, ge=0)
    operations: int = Field(ge=0)
    omission_count: int = Field(ge=0)
    trace_complete: bool
    log_reference: str = Field(min_length=1)

    @model_validator(mode='after')
    def valid_interval(self):
        if self.started_at.tzinfo is None or self.ended_at.tzinfo is None:
            raise ValueError('测时必须含时区')
        duration = (self.ended_at - self.started_at).total_seconds()
        if duration <= 0 or self.interruption_seconds >= duration:
            raise ValueError('结束时间应晚于开始时间，中断应小于任务总时长')
        return self


class ExternalEvidence(Model):
    schema_version: Literal['3.0'] = '3.0'
    record_kind: Literal['external_validation'] = 'external_validation'
    status: Literal['unfilled', 'draft', 'collected'] = 'unfilled'
    project: ProjectEvidence = Field(default_factory=ProjectEvidence)
    materials: list[MaterialEvidence] = Field(default_factory=list)
    tests: list[TestEvidence] = Field(default_factory=list)
    human_tasks: list[HumanTask] = Field(default_factory=list)


def validation_template():
    return ExternalEvidence(materials=[MaterialEvidence()], tests=[TestEvidence()]).model_dump(mode='json')


def check_external_evidence(value):
    try:
        data = ExternalEvidence.model_validate(value)
    except ValidationError as error:
        return {'schema_valid': False, 'collection_complete': False, 'authenticity_verified': False,
                'issues': [{'field': '.'.join(str(k) for k in e['loc']), 'message': e['msg']} for e in error.errors()],
                'human_participants': None, 'note': '字段检查不证明证据真实性，不写入选材或训练库。'}
    issues = []
    for field, item in data.project.model_dump().items():
        if not item or not item.strip():
            issues.append({'field': 'project.' + field, 'message': '等待项目原始依据'})
    for index, material in enumerate(data.materials):
        for field, item in material.model_dump().items():
            if not item or not item.strip():
                issues.append({'field': f'materials.{index}.{field}', 'message': '等待材料台账确认'})
    if not data.materials:
        issues.append({'field': 'materials', 'message': '等待材料身份记录'})
    for index, test in enumerate(data.tests):
        for field in ['metric', 'method', 'raw_file_reference']:
            if not getattr(test, field) or not getattr(test, field).strip():
                issues.append({'field': f'tests.{index}.{field}', 'message': '等待试验原始依据'})
        if not test.conditions:
            issues.append({'field': f'tests.{index}.conditions', 'message': '等待试验条件'})
        definition = metric_registry()['metrics'].get(test.metric or '')
        if definition is None:
            issues.append({'field': f'tests.{index}.metric', 'message': '指标需在注册表中明确口径'})
        else:
            for key in set(definition['condition_keys']) - {'test_method'}:
                if test.conditions.get(key) in [None, '']:
                    issues.append({'field': f'tests.{index}.conditions.{key}', 'message': '等待该指标关键试验条件'})
    if not data.tests:
        issues.append({'field': 'tests', 'message': '等待独立试验记录'})
    participants = sorted({t.participant_id for t in data.human_tasks})
    cells = [(t.participant_id, t.task, t.workflow) for t in data.human_tasks]
    if len(cells) != len(set(cells)):
        issues.append({'field': 'human_tasks', 'message': '同一参与者同一任务同一流程重复，不能重复计数'})
    for participant in participants:
        for task in ['routine_selection', 'conflict_review', 'variant_validation']:
            workflows = {t.workflow for t in data.human_tasks if t.participant_id == participant and t.task == task}
            orders = [t.order for t in data.human_tasks if t.participant_id == participant and t.task == task]
            if workflows != {'manual', 'B1', 'V2'} or len(orders) != len(set(orders)):
                issues.append({'field': 'human_tasks', 'message': f'{participant}的{task}需要三流程成对记录和不同顺序编号'})
    if not participants:
        issues.append({'field': 'human_tasks', 'message': '真人参与数为0，真人收益尚未测量'})
    times = [{'participant_id': t.participant_id, 'task': t.task, 'workflow': t.workflow,
              'effective_seconds': (t.ended_at - t.started_at).total_seconds() - t.interruption_seconds}
             for t in data.human_tasks]
    return {'schema_valid': True, 'collection_complete': not issues and data.status == 'collected',
            'authenticity_verified': False, 'status': data.status, 'issues': issues,
            'human_participants': len(participants), 'human_effective_times': times,
            'note': '仅检查已填字段、配对与时间逻辑；真实身份、文件内容、方法适用和行业收益需独立审核。不写入选材或训练库。'}
