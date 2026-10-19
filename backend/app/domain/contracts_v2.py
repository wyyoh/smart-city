"""Scene-to-demand contracts; known unsupported requirements remain first-class inputs."""
import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..settings import ROOT


def metric_registry():
    return json.loads((ROOT / 'configs/metric_registry_v2.json').read_text(encoding='utf-8'))


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, str_strip_whitespace=True, populate_by_name=True)


class ContextValue(Model):
    code: str | None = Field(default=None, alias='class', max_length=120)
    source: str | None = Field(default=None, max_length=500)


class Distress(Model):
    type: str | None = Field(default=None, max_length=120)
    severity: str | None = Field(default=None, max_length=120)
    mechanism: str | None = Field(default=None, max_length=500)


class SceneContext(Model):
    maintenance_method: str | None = Field(default=None, max_length=160)
    layer: str | None = Field(default=None, max_length=120)
    structure_type: str | None = Field(default=None, max_length=120)
    climate: ContextValue = Field(default_factory=ContextValue)
    traffic: ContextValue = Field(default_factory=ContextValue)
    distress: Distress = Field(default_factory=Distress)


class Inventory(Model):
    source_codes: list[str] | None = None
    product_versions: list[str] | None = None
    gradation_family: str | None = Field(default=None, max_length=80)

    @field_validator('source_codes', 'product_versions')
    @classmethod
    def clean_identifiers(cls, values):
        if values is None:
            return None
        if len(values) > 500 or any(not v.strip() for v in values):
            raise ValueError('库存标识必须非空，数量不能超过500')
        return sorted(set(v.strip() for v in values))


class Construction(Model):
    equipment: list[str] | None = None
    mixing_window: str | None = Field(default=None, max_length=500)
    compaction_window: str | None = Field(default=None, max_length=500)
    source: str | None = Field(default=None, max_length=500)


class ResourceConstraints(Model):
    budget: float | None = Field(default=None, ge=0)
    budget_unit: str | None = Field(default=None, max_length=80)
    schedule_days: float | None = Field(default=None, ge=0)
    rap_min_pct: float | None = Field(default=None, ge=0, le=100)
    carbon_cap: float | None = Field(default=None, ge=0)
    carbon_unit: str | None = Field(default=None, max_length=80)


class RequirementSource(Model):
    kind: Literal['enterprise_reference', 'constructed_demo', 'project_target', 'project_approved', 'normative']
    reference: str = Field(min_length=1, max_length=1000)
    confirmed: bool = False

    @model_validator(mode='after')
    def approval_declaration(self):
        if self.kind in ['project_approved', 'normative'] and not self.confirmed:
            raise ValueError('批准项目要求或规范要求须明确声明已确认其适用性')
        return self


class PerformanceRequirement(Model):
    metric: str
    operator: Literal['>', '>=', '<', '<=', 'between', 'grade'] = '>'
    value: float | str
    upper: float | None = None
    unit: str
    test_method: str | None = Field(default=None, max_length=500)
    conditions: dict[str, str | float | None] = Field(default_factory=dict)
    comparison_basis: str | None = Field(default=None, max_length=160)
    source: RequirementSource

    @field_validator('value', mode='before')
    @classmethod
    def reject_boolean(cls, value):
        if isinstance(value, bool):
            raise ValueError('性能值不能是布尔值')
        return value

    @model_validator(mode='after')
    def validate_semantics(self):
        definition = metric_registry()['metrics'].get(self.metric)
        if definition is None:
            raise ValueError('未知指标名称，请先核对指标注册表；已知但暂不支持的需求可以保留')
        if self.unit != definition['unit']:
            raise ValueError('单位与指标注册表不一致；不同试验口径不自动换算')
        if definition['value_type'] == 'grade':
            if self.operator != 'grade' or not isinstance(self.value, str) or not self.value.strip() or self.upper is not None:
                raise ValueError('等级目标使用grade和非空等级表达，不作为标量阈值')
        else:
            if not isinstance(self.value, (int, float)) or not math.isfinite(self.value) or self.value < 0:
                raise ValueError('标量性能目标须为有限非负数')
            if self.operator == 'grade':
                raise ValueError('标量指标不使用grade运算符')
            if self.operator == 'between' and (self.upper is None or self.upper < self.value):
                raise ValueError('区间需要有效上下限')
            if self.operator != 'between' and self.upper is not None:
                raise ValueError('只有区间目标可以包含upper')
            if self.unit == '%' and (self.value > 100 or (self.upper is not None and self.upper > 100)):
                raise ValueError('百分数目标不得超出0至100')
        return self


class DemandRequest(Model):
    schema_version: Literal['2.0'] = '2.0'
    name: str = Field(min_length=1, max_length=160)
    decision_id: str | None = Field(default=None, max_length=160)
    segment_id: str | None = Field(default=None, max_length=160)
    context_kind: Literal['constructed_demo', 'project'] = 'project'
    demo_case_id: Literal['C1', 'C2', 'C3', 'C4', 'C5'] | None = None
    scene: SceneContext = Field(default_factory=SceneContext)
    inventory: Inventory = Field(default_factory=Inventory)
    construction: Construction = Field(default_factory=Construction)
    constraints: ResourceConstraints = Field(default_factory=ResourceConstraints)
    requested_metrics: list[str] = Field(default_factory=list, max_length=20)
    project_targets: list[PerformanceRequirement] = Field(default_factory=list, max_length=20)

    @field_validator('requested_metrics')
    @classmethod
    def known_metrics(cls, values):
        unknown = set(values) - set(metric_registry()['metrics'])
        if unknown:
            raise ValueError('未知指标：' + ', '.join(sorted(unknown)))
        return list(dict.fromkeys(values))

    @model_validator(mode='after')
    def context_sources(self):
        if self.context_kind == 'project' and self.demo_case_id is not None:
            raise ValueError('正式项目不可套用构造验证案例')
        if self.context_kind == 'project' and any(
            t.source.kind == 'constructed_demo' or t.comparison_basis == 'legacy_workbook_numeric_demo'
            for t in self.project_targets
        ):
            raise ValueError('正式项目不能使用构造演示要求或历史数值演示口径')
        return self


class RequirementOverride(Model):
    target_id: str = Field(min_length=1, max_length=160)
    requirement: PerformanceRequirement
    reason: str = Field(min_length=1, max_length=1000)


class DemandConfirmation(Model):
    expected_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    confirmed_by: str = Field(min_length=1, max_length=160)
    note: str = Field(default='', max_length=1000)
    overrides: list[RequirementOverride] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def unique_overrides(self):
        ids = [x.target_id for x in self.overrides]
        if len(set(ids)) != len(ids):
            raise ValueError('同一目标只能覆盖一次')
        return self
