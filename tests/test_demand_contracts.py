"""Input integrity for the new engineering demand boundary."""
from pydantic import ValidationError
import pytest

from app.domain.contracts_v2 import DemandRequest, PerformanceRequirement


def requirement(**changes):
    data = dict(metric='DS', operator='>', value=8000, unit='次/mm',
                source={'kind': 'project_target', 'reference': '测试项目要求'})
    data.update(changes)
    return data


def test_scene_keeps_missing_and_empty_inventory_distinct():
    request = DemandRequest(name='待补工程信息')
    assert request.constraints.rap_min_pct is None
    assert request.scene.climate.code is None
    assert request.inventory.source_codes is None
    assert DemandRequest(name='空库存', inventory={'source_codes': []}).inventory.source_codes == []


def test_known_unsupported_targets_are_retained():
    request = DemandRequest(name='疲劳需求', requested_metrics=['fatigue_life', 'dynamic_modulus', 'PG_grade'],
                            project_targets=[requirement(metric='fatigue_life', value=100000, unit='次'),
                                             requirement(metric='PG_grade', value='PG 64-22', operator='grade', unit='grade')])
    assert request.requested_metrics == ['fatigue_life', 'dynamic_modulus', 'PG_grade']
    assert request.project_targets[1].value == 'PG 64-22'
    with pytest.raises(ValidationError, match='未知指标'):
        DemandRequest(name='拼写错误', requested_metrics=['fatique'])


@pytest.mark.parametrize('changes', [
    {'value': True}, {'value': float('nan')}, {'value': '8000'}, {'unit': 'MPa'},
    {'operator': 'between', 'upper': 7000}, {'upper': 9000},
    {'metric': 'TSR', 'unit': '%', 'value': 120},
])
def test_invalid_numeric_or_dimension_does_not_enter_decision(changes):
    with pytest.raises(ValidationError):
        PerformanceRequirement(**requirement(**changes))


def test_project_cannot_promote_demo_requirements():
    with pytest.raises(ValidationError, match='正式项目'):
        DemandRequest(name='正式项目', project_targets=[requirement(comparison_basis='legacy_workbook_numeric_demo')])
    with pytest.raises(ValidationError, match='适用性'):
        PerformanceRequirement(**requirement(source={'kind': 'normative', 'reference': '未核对条款'}))
