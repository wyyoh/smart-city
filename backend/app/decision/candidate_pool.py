"""Retrieve the full catalogue and freeze exact membership and visible evidence."""
from copy import deepcopy
import re

from fastapi import HTTPException
from pydantic import Field
from typing import Literal

from ..domain.contracts_v2 import Model, metric_registry
from ..services import catalog, latest_dataset
from .materials import material_version
from .records import append_record, digest, get_record
from .rules import rulebook
from .eligibility import construction_eligibility
from .cases import casebook


class PoolRequest(Model):
    confirmation_id: str = Field(min_length=1)
    evidence_view: Literal['all', 'complete_numeric_demo'] = 'all'


def gradation_family(value):
    match = re.match(r'^(AC|SMA|OGFC)-\d+', value)
    return match.group(0) if match else value


def scope_exclusions(recipe, request):
    inventory = request['inventory']
    reasons = []
    if inventory['source_codes'] is not None and recipe['source'] not in inventory['source_codes']:
        reasons.append('source_not_in_inventory')
    if inventory['product_versions'] is not None and material_version(recipe) not in inventory['product_versions']:
        reasons.append('product_version_not_in_inventory')
    if inventory['gradation_family'] and gradation_family(recipe['gradation']) != inventory['gradation_family']:
        reasons.append('gradation_family_mismatch')
    application = recipe['payload'].get('applicability', {})
    for key in ['maintenance_method', 'layer', 'structure_type']:
        allowed = application.get(key)
        value = request['scene'].get(key)
        if allowed is not None and value is not None and value not in (allowed if isinstance(allowed, list) else [allowed]):
            reasons.append(key + '_incompatible')
    for item in construction_eligibility(recipe, request)['dimensions']:
        if item['status'] == 'inapplicable' and item['dimension'] + '_incompatible' not in reasons:
            reasons.append(item['dimension'] + '_incompatible')
    return reasons


def freeze_pool(session, request: PoolRequest):
    demand = get_record(session, request.confirmation_id, 'demand_confirmation')
    if not demand['ready_for_candidate_retrieval']:
        raise HTTPException(409, '需求仍有未解决项，请先补充并重新确认')
    if demand['versions']['rules_sha256'] != rulebook()['sha256'] or demand['versions']['metrics_sha256'] != digest(metric_registry()):
        raise HTTPException(409, '规则或指标版本已变化，请重新解析确认')
    if demand['versions'].get('case_scenarios_sha256') != casebook()['sha256']:
        raise HTTPException(409, '构造案例版本已变化，请重新解析确认')
    if request.evidence_view == 'complete_numeric_demo' and demand['request']['context_kind'] != 'constructed_demo':
        raise HTTPException(422, '完整数值诊断池仅供明确限定的构造演示')
    ds = latest_dataset(session)
    recipes = sorted(catalog(session, context_kind=demand['request']['context_kind']), key=lambda r: r['id'])
    included, excluded = [], []
    metrics = {t['metric'] for t in demand['targets']}
    for recipe in recipes:
        reasons = scope_exclusions(recipe, demand['request'])
        if request.evidence_view == 'complete_numeric_demo' and any(recipe['metrics'].get(m) is None for m in metrics):
            reasons.append('incomplete_numeric_demo_scope')
        if reasons:
            excluded.append({'id': recipe['id'], 'display_id': recipe['display_id'], 'source': recipe['source'],
                             'gradation': recipe['gradation'], 'material_version': material_version(recipe), 'reasons': reasons})
        else:
            included.append(deepcopy(recipe))
    scope = {'context_kind': demand['request']['context_kind'], 'inventory': demand['request']['inventory'],
             'scene': demand['request']['scene'], 'construction': demand['request']['construction'],
             'evidence_view': request.evidence_view, 'catalogue_total': len(recipes),
             'dataset': {'id': ds.id, 'sha256': ds.sha256, 'revision': ds.revision},
             'scope_note': '结论仅针对本次冻结目录、库存、级配及证据视图；不是所有可设计材料的结论。',
             'inventory_confirmed': demand['request']['inventory']['source_codes'] is not None and demand['request']['inventory']['product_versions'] is not None,
             'evidence_view_note': '排除缺少任一所需数值的记录，仅诊断完整数值子池。' if request.evidence_view == 'complete_numeric_demo' else '保留缺测和适用性未知候选，未知不能证明无解。'}
    ids = [r['id'] for r in included]
    return append_record(session, 'candidate_pool', {
        'schema_version': '2.0', 'confirmation_id': demand['id'], 'confirmation_sha256': demand['sha256'],
        'scope': scope, 'candidate_ids': ids, 'excluded': excluded,
        'candidates': included, 'evidence_sha256': digest(included),
        'pool_sha256': digest({'scope': scope, 'candidate_ids': ids, 'excluded': excluded, 'evidence': digest(included)}),
        'summary': {'catalogue_total': len(recipes), 'included': len(included), 'excluded': len(excluded)},
    }, parent_id=demand['id'], dataset_id=ds.id)
