from typing import Literal

from pydantic import Field, model_validator

from ..domain.contracts_v2 import Model

LockedField = Literal['oil_stone_ratio_pct', 'nominal_component_weights']
Metric = Literal['DS', 'strain', 'TSR', 'residual']


class CaseRunRequest(Model):
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{8,80}$')
    evidence_view: Literal['all', 'complete_numeric_demo'] = 'all'
    rap_min_pct: float | None = Field(default=None, ge=0, le=100)
    adjustment_reason: str = Field(default='', max_length=1000)
    target_overrides: dict[Metric, float] = Field(default_factory=dict, max_length=4)
    based_on_decision_id: str | None = Field(default=None, max_length=100)
    expected_decision_sha256: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def validate_adjustment(self):
        if any(v < 0 for v in self.target_overrides.values()):
            raise ValueError('性能目标不能为负数')
        if (self.target_overrides or self.rap_min_pct is not None) and not self.adjustment_reason:
            raise ValueError('调整要求时请填写理由')
        if bool(self.based_on_decision_id) != bool(self.expected_decision_sha256):
            raise ValueError('原决策编号和指纹须同时提供')
        return self


class AdjustmentPreview(Model):
    expected_decision_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    rap_min_pct: float | None = Field(default=None, ge=0, le=100)
    target_overrides: dict[Metric, float] = Field(default_factory=dict, max_length=4)

    @model_validator(mode='after')
    def nonnegative(self):
        if any(v < 0 for v in self.target_overrides.values()):
            raise ValueError('性能目标不能为负数')
        return self


class PreferenceRequest(Model):
    decision_id: str = Field(min_length=1, max_length=100)
    expected_decision_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    priority_order: list[str] = Field(min_length=1, max_length=12)
    reason: str = Field(default='比较相同硬要求下的指标优先顺序', min_length=1, max_length=1000)
    persist: bool = False
    request_id: str | None = Field(default=None, pattern=r'^[a-zA-Z0-9_-]{8,80}$')

    @model_validator(mode='after')
    def validate_order(self):
        if len(set(self.priority_order)) != len(self.priority_order):
            raise ValueError('偏好指标不能重复')
        if self.persist and not self.request_id:
            raise ValueError('保存偏好时需要请求编号')
        return self


class DraftRequest(Model):
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{8,80}$')
    origin_decision_id: str = Field(min_length=1, max_length=100)
    expected_decision_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    parent_recipe_id: str = Field(min_length=1, max_length=100)
    hypothesis_id: str = Field(min_length=1, max_length=100)
    locked_fields: list[LockedField] = Field(default_factory=list, max_length=2)
    design_intent: str = Field(min_length=1, max_length=2000)
    research_scope_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def unique_locks(self):
        if len(set(self.locked_fields)) != len(self.locked_fields):
            raise ValueError('锁定字段不能重复')
        return self
