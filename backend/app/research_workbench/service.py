"""Verified research snapshots and append-only proposals; never material approval."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import html
import json
from pathlib import Path
import sqlite3

import numpy as np
from fastapi import HTTPException
from scipy.spatial.distance import cdist
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sqlmodel import Session, create_engine, select

from ..decision.records import DecisionRecord, append_record, digest, get_record
from ..research.data import load_data
from ..research.estimators import feature_map
from ..services import latest_dataset
from ..settings import ROOT
from ..storage import Measurement

REGISTRY_PATH = ROOT/'configs/research_workbench_v5.json'
_JSON_CACHE = {}
_DATA_CACHE = {}
LABELS = {'DS': ('动稳定度', '次/mm'), 'strain': ('最大弯拉应变', 'με'),
          'TSR': ('冻融劈裂比', '%'), 'residual': ('残留稳定度比', '%')}


def registry():
    if not REGISTRY_PATH.exists(): raise HTTPException(503, '研究证据尚未登记，请先完成研究登记。')
    return json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))


def verified_path(key):
    entry = registry()['evidence'].get(key)
    if not entry: raise HTTPException(404, '研究资料不存在。')
    path = (ROOT/entry['path']).resolve()
    if not path.is_relative_to(ROOT.resolve()): raise HTTPException(403, '研究资料路径超出项目范围。')
    if not path.is_file(): raise HTTPException(503, '研究证据文件缺失，请恢复登记时的文件。')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry['sha256']:
        raise HTTPException(409, '研究证据指纹已改变，请核对并重新登记。')
    return entry, path, raw


def artifact(key):
    entry, _, raw = verified_path(key)
    cache_key = (key, entry['sha256'])
    if cache_key not in _JSON_CACHE: _JSON_CACHE[cache_key] = json.loads(raw.decode('utf-8'))
    return _JSON_CACHE[cache_key]


def scope():
    registered = registry()
    return {'dataset': registered['dataset'], 'evidence_sha256': {k: v['sha256'] for k, v in registered['evidence'].items()},
            'prior_completion_sha256': registered['prior_completion_sha256']}


def compatibility(session):
    expected = registry()['dataset']; current = latest_dataset(session)
    fields = ['id', 'sha256', 'revision']
    observed = {f: getattr(current, f) for f in fields}
    matches = all(expected['dataset_'+f] == observed[f] for f in fields)
    return {'matches': matches, 'current': observed,
            'reason': None if matches else '当前数据版本与研究快照不同。历史结果可查看，新试验计划需在重新验证后生成。'}


def overview(session):
    registered = registry(); search = artifact('candidate_pool'); audit = artifact('source_audit')
    first, ensemble, study = artifact('benchmark'), artifact('ensemble'), artifact('head_study')
    verification = artifact('study_verification')
    current = compatibility(session)
    def metric_rows(baseline, chosen, field):
        return [{'metric': m, 'label': LABELS[m][0], 'unit': LABELS[m][1],
                 'baseline_mae': baseline[m]['mae'], 'candidate_mae': chosen[m]['mae'],
                 'relative_improvement': chosen[m][field], 'repeats_better_than_mean': chosen[m]['repeats_better_than_mean']}
                for m in LABELS]
    rows = metric_rows(study['scores']['mean'], study['scores']['head_gated'], 'relative_mae_improvement')
    for row in rows: row['head_acceptance_fraction'] = study['head_acceptance_fraction'][row['metric']]
    return {'scope': scope(), 'scope_sha256': digest(scope()), 'compatibility': current,
        'status': 'research_only', 'production_model_promoted': False, 'independent_material_tests': 0,
        'counts': {'hypotheses': search['hypothesis_count'], 'within_observed_support': search['supported_hypothesis_count'],
                   'input_alias_groups': audit['input_alias_groups'], 'observed_conflict_groups': audit['groups_with_observed_conflict'],
                   'masked_curve_alias_groups': audit['masked_curve_alias_groups'], 'source_cells': verification['source_references_checked']},
        'sources': sorted(set(h['source_code'] for h in search['hypotheses'])),
        'latest_experiment': {'outer_folds': study['outer_folds'], 'repeats': 10, 'rows': rows,
            'exact_reproduction': verification['all_predictions_and_head_acceptance_exactly_reproduced'],
            'note': '同一历史工作簿的新内部分组。门控仍有指标退步，没有替换正式模型。'},
        'previous_experiment': {'repeats': 5, 'rows': metric_rows(first['summaries']['basic:mean:'], ensemble['summaries']['fixed_half_ensemble'], 'relative_mae_improvement_vs_mean'),
                                'note': '上一轮保守集成，独立列出；不能跨不同划分直接比较误差。'},
        'evidence': [{'id': key, 'title': e['title'], 'sha256': e['sha256'], 'url': '/v4/research/evidence/'+key}
                     for key, e in registered['evidence'].items() if e['downloadable']],
        'limits': ['候选配方未实测；预测不参与硬约束通过判定。', '名义RAP及组分份额需确认物理质量基准。',
                   '试验计划数量是配方数量，实际试件数、费用和工期尚待实验室确认。']}


def filtered_candidates(filters):
    rows = artifact('candidate_pool')['hypotheses']
    source, kind, q = filters.get('source', ''), filters.get('kind', 'all'), filters.get('q', '').casefold()
    supported = filters.get('supported_only', True)
    selected = [r for r in rows if (not source or r['source_code'] == source)
                and (kind == 'all' or r['kind'] == kind)
                and (not supported or (r['within_basic_design_distance_support'] and r['within_observed_same_nmas_curve_envelope']))
                and (not q or q in ' '.join([r['id'], r['source_code'], r['gradation'], r['product']]).casefold())]
    return sorted(selected, key=lambda r: (r['source_code'], r['gradation'], r['id']))


def summary(row):
    if row['kind'] == 'oil_ratio':
        label = f"油石比 {row['change']['oil_stone_ratio_delta_percentage_points']:+.2f} 个百分点"
    else:
        a, b = row['change']['from_component'], row['change']['to_component']
        label = f"新集料第{a+1}项向第{b+1}项转移名义2个百分点"
    return {key: row[key] for key in ['id', 'parent_id', 'source_code', 'gradation', 'product', 'kind', 'oil_stone_ratio_pct', 'rap_nominal_pct']} | {
        'change_label': label, 'within_observed_support': row['within_basic_design_distance_support'] and row['within_observed_same_nmas_curve_envelope'],
        'measured_performance': None, 'engineering_release_allowed': False}


def candidate_list(filters, offset, limit):
    rows = filtered_candidates(filters)
    return {'total': len(rows), 'offset': offset, 'limit': limit, 'items': [summary(r) for r in rows[offset:offset+limit]],
            'scope_sha256': digest(scope()), 'filters': filters}


def frozen_data():
    entry, path, _ = verified_path('baseline')
    key = entry['sha256']
    if key not in _DATA_CACHE: _DATA_CACHE[key] = load_data(path)
    return _DATA_CACHE[key]


def find_candidate(candidate_id):
    row = next((h for h in artifact('candidate_pool')['hypotheses'] if h['id'] == candidate_id), None)
    if not row: raise HTTPException(404, '未找到此研究配方。')
    return row


def candidate_detail(candidate_id):
    row = find_candidate(candidate_id); data = frozen_data()
    parent = next(r for r in data['recipes'] if r['id'] == row['parent_id'])
    entry, path, _ = verified_path('baseline')
    engine = create_engine('sqlite://', creator=lambda: sqlite3.connect(path.as_uri()+'?mode=ro', uri=True))
    with Session(engine) as s:
        labels = s.exec(select(Measurement).where(Measurement.dataset_id == data['metadata']['dataset_id'], Measurement.recipe_id == parent['id'])).all()
        parent_labels = {m.metric: {'value': m.value, 'unit': m.unit, 'references': m.payload.get('raw_labels', [])} for m in labels if m.metric in LABELS}
    engine.dispose()
    grade = parent['payload']['gradation']
    components = [{'row': c['row'], 'type': c['type'], 'size': c['size'], 'before': c['nominal_weight'],
                   'after': weight, 'delta_percentage_points': 100*(weight-c['nominal_weight'])}
                  for c, weight in zip(grade['components'], row['nominal_component_weights'])]
    return {'candidate': deepcopy(row), 'summary': summary(row), 'components': components,
        'parent': {'id': parent['id'], 'source_code': parent['source'], 'gradation': parent['gradation'],
                   'product': parent['product'], 'oil_stone_ratio_pct': parent['oil_stone_ratio_pct'], 'metrics': parent_labels,
                   'curve_reference': grade.get('curve_reference')},
        'interpretation': '父方案历史记录单独列示。新配方尚无实测依据，全量拟合预测不能继承父方案达标结论。'}


def select_diverse_designs(observed_X, pool, parent_groups, budget, pinned):
    """Only pre-test design coordinates and source-group proxies enter selection."""
    if not pool: raise HTTPException(422, '当前筛选范围没有待测配方。')
    ordered = sorted(pool, key=lambda r: r['id']); index = {r['id']: i for i, r in enumerate(ordered)}
    if any(key not in index for key in pinned): raise HTTPException(422, '手动加入的配方不在当前筛选范围，请重新选择。')
    if len(set(pinned)) != len(pinned) or len(pinned) > budget: raise HTTPException(422, '手动配方不能重复或超过计划数量。')
    imputer = SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True)
    scaler = StandardScaler()
    base = scaler.fit_transform(imputer.fit_transform(feature_map(observed_X, 'compact')))
    X = np.array([r['design_X'] for r in ordered])
    Z = scaler.transform(imputer.transform(feature_map(X, 'compact')))
    distance = cdist(Z, base).min(axis=1)
    initial_distance = distance.copy()
    selected, seen_groups, details = [], set(), []
    def append(i, manual):
        nonlocal distance
        group = parent_groups[ordered[i]['parent_id']]
        details.append({'candidate_id': ordered[i]['id'], 'manual': manual, 'source_group_proxy': group,
                        'nearest_known_design_distance': float(initial_distance[i]),
                        'distance_before_selection': float(distance[i]),
                        'reason': '手动加入的待测配方' if manual else '优先分散来源代理组，再选择与已知及已选设计差异较大的配方'})
        selected.append(i); seen_groups.add(group)
        distance = np.minimum(distance, cdist(Z, Z[i:i+1]).ravel())
    for key in pinned: append(index[key], True)
    while len(selected) < min(budget, len(ordered)):
        available = [i for i in range(len(ordered)) if i not in selected]
        new_groups = [i for i in available if parent_groups[ordered[i]['parent_id']] not in seen_groups]
        options = new_groups or available
        chosen = max(options, key=lambda i: (float(distance[i]), -i))
        append(chosen, False)
    return [ordered[i] for i in selected], details


def save_plan(session, request):
    body = request.model_dump(); fingerprint = digest(body); record_id = 'rplan_'+request.request_id
    existing = session.get(DecisionRecord, record_id)
    if existing:
        if existing.kind != 'research_test_plan' or existing.payload.get('request_fingerprint') != fingerprint:
            raise HTTPException(409, '此请求编号已用于其他内容，请生成新编号。')
        return get_record(session, record_id, 'research_test_plan')
    if request.scope_sha256 != digest(scope()): raise HTTPException(409, '研究证据版本已改变，请刷新后重新生成。')
    compatible = compatibility(session)
    if not compatible['matches']: raise HTTPException(409, compatible['reason'])
    # A new plan is bound to every registered file, including downloaded reports.
    for evidence_id in registry()['evidence']:
        verified_path(evidence_id)
    data = frozen_data(); groups = dict(zip(data['ids'], data['groups'].tolist()))
    pool = filtered_candidates(body['filters'])
    selected, rationale = select_diverse_designs(data['X'], pool, groups, request.budget, request.pinned_ids)
    payload = {'title': request.title, 'request_fingerprint': fingerprint, 'scope': scope(), 'scope_sha256': digest(scope()),
        'currentness_at_creation': compatible, 'filters': body['filters'], 'eligible_pool_size': len(pool),
        'requested_formulations': request.budget, 'selected_formulations': len(selected),
        'selection_method': '来源代理组分散与设计空间覆盖；不使用预测性能排序或隐藏实测标签',
        'budget_unit': 'new_formulation_hypotheses', 'selection_rationale': rationale,
        'formulations': [candidate_detail(r['id']) for r in selected],
        'external_material_tests': 0, 'actual_specimen_count': None, 'laboratory': None, 'cost': None,
        'required_before_testing': ['确认材料实物身份、料堆及批次。', '确认RAP分母、含水与旧/有效结合料核算。',
                                    '冻结工程目标条款和实际称料表。', '由实验室确认方法版本、温度、荷载、老化/冻融、压实及试件数。',
                                    '同期重新制备原配方对照，保留独立制备与确认批次。'],
        'engineering_release_allowed': False, 'laboratory_results': None,
        'note': '这是待确认的试验安排。配方数量不等于实际试件数，来源代码不等于已核实的实物料源。'}
    session.expire_all()
    if not compatibility(session)['matches']:
        raise HTTPException(409, '生成期间数据版本发生变化，请刷新并重新验证。')
    return append_record(session, 'research_test_plan', payload, dataset_id=compatible['current']['id'], record_id=record_id)


def plan_html(plan):
    esc = lambda x: html.escape(str(x))
    rows = ''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in [i+1, r['summary']['source_code'], r['summary']['gradation'],
        r['summary']['change_label'], r['summary']['oil_stone_ratio_pct'], r['summary']['rap_nominal_pct'], '待实测'])+'</tr>' for i, r in enumerate(plan['formulations']))
    requirements = ''.join('<li>'+esc(v)+'</li>' for v in plan['required_before_testing'])
    components = ''
    for i, f in enumerate(plan['formulations'], 1):
        component_rows = ''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in ['级配!第'+str(c['row'])+'行', c['type'],
            f"{100*c['before']:.4f}".rstrip('0').rstrip('.')+'%', f"{100*c['after']:.4f}".rstrip('0').rstrip('.')+'%'])+'</tr>'
            for c in f['components'] if c['before'] > 0 or c['after'] > 0)
        components += '<h2>配方'+str(i)+'的名义组分</h2><p>'+esc(f['summary']['id'])+'</p><table><tr><th>原表位置</th><th>组分</th><th>父配方名义份额%</th><th>待测名义份额%</th></tr>'+component_rows+'</table>'
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{esc(plan['title'])}</title>
<style>body{{font:14px/1.7 'Microsoft YaHei',sans-serif;color:#183b54;max-width:1000px;margin:32px auto;padding:0 24px}}h1{{font-size:26px}}h2{{font-size:18px;margin-top:28px}}table{{border-collapse:collapse;width:100%;font-size:12px}}td,th{{border:1px solid #dce5e9;text-align:left;padding:8px}}th{{background:#edf4f6}}.note{{padding:12px;background:#fff4d9}}small{{overflow-wrap:anywhere}}@media print{{body{{margin:0}}tr{{break-inside:avoid}}h2{{break-after:avoid}}}}</style>
<h1>{esc(plan['title'])}</h1><p class="note">待确认试验计划。新增实测为0，不构成材料放行。名义份额须在质量基准核对后转为实际称料单。</p>
<p>生成时间：{esc(plan['created_at'])}；生成时数据版本已匹配。当前文件为该时点的保存快照。</p>
<p>安排{plan['selected_formulations']}种待测配方；实际试件数、实验室、费用及工期均待确认。</p>
<table><tr><th>顺序</th><th>来源代码</th><th>级配</th><th>改动</th><th>油石比%</th><th>名义RAP%</th><th>状态</th></tr>{rows}</table>
<h2>选择依据</h2><p>{esc(plan['selection_method'])}</p><h2>试验前确认</h2><ol>{requirements}</ol>{components}
<p>{esc(plan['note'])}</p><small>计划编号：{esc(plan['id'])}<br>保存内容SHA256：{esc(plan['sha256'])}<br>研究范围SHA256：{esc(plan['scope_sha256'])}</small></html>'''
