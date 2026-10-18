from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
import math

METRICS = {
    'DS': {'label': '动稳定度', 'unit': '次/mm'},
    'strain': {'label': '最大弯拉应变', 'unit': 'με'},
    'TSR': {'label': '冻融劈裂强度比', 'unit': '%'},
    'residual': {'label': '残留稳定度比', 'unit': '%'},
    'stability': {'label': '稳定度', 'unit': 'kN'},
    'VV': {'label': '空隙率', 'unit': '%'},
    'VMA': {'label': '矿料间隙率', 'unit': '%'},
    'flow': {'label': '流值', 'unit': 'mm'},
}
CORE_METRICS = ['DS', 'strain', 'TSR', 'residual']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, str_strip_whitespace=True)


class Target(StrictModel):
    metric: str
    operator: Literal['>', '>=', '<', '<=', 'between'] = '>'
    value: float
    upper: float | None = None
    source_kind: Literal['enterprise_reference', 'project_target', 'demo_assumption'] = 'project_target'
    reference: str | None = None
    test_method: str | None = None
    conditions: str | None = None

    @model_validator(mode='after')
    def valid_bounds(self):
        if self.metric not in METRICS:
            raise ValueError('不支持该指标，请补充对应试验与单位契约')
        if self.operator == 'between' and (self.upper is None or self.upper < self.value):
            raise ValueError('区间目标必须给出有效的上下限')
        if self.value < 0:
            raise ValueError('性能目标不能为负数')
        refs = {'DS':(800,'设计流程!E11'),'strain':(2000,'设计流程!E12'),'TSR':(75,'设计流程!E10'),'residual':(85,'设计流程!E10')}
        if self.source_kind == 'enterprise_reference' and (self.metric not in refs or
                self.operator != '>' or (self.value,self.reference) != refs[self.metric]):
            raise ValueError('企业流程参考必须与登记值及出处一致；修改后请标为项目目标')
        return self


class Scenario(StrictModel):
    name: str = Field(min_length=1, max_length=160)
    maintenance_method: str = Field(min_length=1, max_length=160)
    layer: str = Field(min_length=1, max_length=120)
    distress_type: str = Field(min_length=1, max_length=120)
    climate_zone: str | None = None
    traffic_level: str | None = None
    targets: list[Target] = Field(min_length=1, max_length=12)
    candidate_ids: list[str] | None = None
    available_sources: list[str] | None = None
    rap_min_pct: float = Field(default=0, ge=0, le=100)
    priority: str = 'DS'
    case_id: str | None = None
    context_kind: Literal['constructed_demo', 'project'] = 'project'
    budget: float | None = Field(default=None, ge=0)

    @model_validator(mode='after')
    def unique_targets(self):
        if len({t.metric for t in self.targets}) != len(self.targets):
            raise ValueError('同一指标请使用一张目标卡，区间目标使用between')
        if self.priority not in METRICS:
            raise ValueError('排序指标不可用')
        return self


class VariantInput(StrictModel):
    oil_stone_ratio_pct: float | None = Field(default=None, gt=0, le=20)
    rap_nominal_pct: float | None = Field(default=None, ge=0, le=100)
    product: str | None = Field(default=None, min_length=1, max_length=100)
    note: str = Field(min_length=1, max_length=1000)


class ObservationInput(StrictModel):
    recipe_id: str
    metric: Literal['DS', 'strain', 'TSR', 'residual', 'stability', 'VV', 'VMA', 'flow']
    value: float = Field(ge=0)
    unit: str
    test_group: str = Field(min_length=1, max_length=160)
    method: str = Field(min_length=1, max_length=160)
    conditions: str = Field(min_length=1, max_length=1000)
    source_reference: str = Field(min_length=1, max_length=1000)
    sample_count: int = Field(ge=1, le=10000)
    idempotency_key: str = Field(min_length=8, max_length=160)
    data_scope: Literal['demo', 'official'] = 'demo'
    supersedes_id: str | None = None
    note: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def consistent_unit(self):
        if self.unit != METRICS[self.metric]['unit']:
            raise ValueError('单位与指标契约不一致，TSR需明确按百分数录入')
        if self.metric in ['VV', 'VMA'] and self.value > 100:
            raise ValueError('百分数应在0至100之间')
        return self


class ReviewInput(StrictModel):
    state: Literal['approved', 'rejected']
    reviewer: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=1, max_length=1000)
    conditions_confirmed: bool = False
    use_for_recommendation: bool = False

    @model_validator(mode='after')
    def reviewed_conditions(self):
        if self.use_for_recommendation and (self.state != 'approved' or not self.conditions_confirmed):
            raise ValueError('作为推荐依据前必须批准并确认试验条件适用')
        return self


def satisfies(value: float, target: Target) -> bool:
    if not math.isfinite(value):
        return False
    return {'>': lambda: value > target.value, '>=': lambda: value >= target.value,
            '<': lambda: value < target.value, '<=': lambda: value <= target.value,
            'between': lambda: target.value <= value <= target.upper}[target.operator]()

