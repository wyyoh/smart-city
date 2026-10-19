from __future__ import annotations

from collections import defaultdict
import hashlib
from html import escape
import json
from uuid import uuid4
from sqlalchemy.exc import IntegrityError

from fastapi import HTTPException
from sqlmodel import Session, select

from .domain.calculations import binder_content_pct
from .domain.contracts import CORE_METRICS, METRICS, ObservationInput, ReviewInput, Scenario, VariantInput, satisfies
from .importer import norm
from .settings import ROOT, VERSION
from .storage import Dataset, Measurement, Observation, Recipe, Recommendation, SourceRow, now

RULE_VERSION = 'thresholds-1.0.0'


def latest_dataset(session):
    dataset = session.exec(select(Dataset).order_by(Dataset.imported_at.desc())).first()
    if dataset is None:
        raise HTTPException(503, '尚未导入数据，请运行工作簿导入命令')
    return dataset


def require_recipe(session, recipe_id):
    recipe = session.get(Recipe, recipe_id)
    if not recipe:
        ds = latest_dataset(session)
        recipe = next((r for r in session.exec(select(Recipe).where(Recipe.dataset_id == ds.id)).all()
                       if r.payload.get('fixture_id') == recipe_id), None)
    if recipe is None:
        raise HTTPException(404, '方案不存在')
    return recipe


def recipe_dict(recipe, measurements, observations=(), *, context_kind='project'):
    metrics, evidence = {}, {}
    for m in measurements:
        metrics[m.metric] = m.value
        evidence[m.metric] = dict(m.payload, value=m.value, unit=m.unit, id=m.id)
    eligible_observations = [o for o in observations if o.state == 'approved' and o.use_for_recommendation
                            and (o.data_scope == 'official' or context_kind == 'constructed_demo')]
    superseded = {o.payload.get('supersedes_id') for o in eligible_observations}
    for o in sorted(eligible_observations, key=lambda o: o.payload['review']['reviewed_at']):
        if o.id in superseded:
            continue
        metrics[o.metric] = o.value
        evidence[o.metric] = {'value': o.value, 'unit': o.unit, 'observation_id': o.id,
            'range': [o.value, o.value], 'n_recorded': 1, 'n_independent_assumed': None,
            'sample_count_declared': o.payload['sample_count'], 'conditions_status': 'user_confirmed',
            'source_kind': f'{o.data_scope}_reviewed_observation', 'review': o.payload['review'],
            'test_group': o.payload['test_group'], 'method': o.payload['method'], 'conditions': o.payload['conditions'],
            'source_reference':o.payload.get('source_reference'),
            **({'structured_conditions':o.payload['structured_conditions']} if 'structured_conditions' in o.payload else {})}
    d = recipe.model_dump()
    d['metrics'], d['evidence'] = metrics, evidence
    d['display_id'] = recipe.payload.get('fixture_id') or recipe.id[-8:]
    d['binder_content_pct'] = binder_content_pct(recipe.oil_stone_ratio_pct) if recipe.oil_stone_ratio_pct is not None else None
    d['release_status'] = 'awaiting_engineer_review_and_testing'
    return d


def catalog(session, *, context_kind='project'):
    ds = latest_dataset(session)
    recipes = session.exec(select(Recipe).where(Recipe.dataset_id == ds.id)).all()
    measurements = defaultdict(list)
    for m in session.exec(select(Measurement).where(Measurement.dataset_id == ds.id)).all():
        measurements[m.recipe_id].append(m)
    observations = defaultdict(list)
    for o in session.exec(select(Observation).join(Recipe, Observation.recipe_id == Recipe.id).where(Recipe.dataset_id == ds.id)).all():
        observations[o.recipe_id].append(o)
    return [recipe_dict(r, measurements[r.id], observations[r.id], context_kind=context_kind) for r in recipes]


def recipe_detail(session, recipe_id, context_kind='project'):
    recipe = require_recipe(session, recipe_id)
    d = recipe_dict(recipe,
        session.exec(select(Measurement).where(Measurement.recipe_id == recipe.id)).all(),
        session.exec(select(Observation).where(Observation.recipe_id == recipe.id)).all(), context_kind=context_kind)
    d['observations'] = [o.model_dump() for o in session.exec(select(Observation).where(Observation.recipe_id == recipe.id)).all()]
    return d


def case_cards():
    cases = json.loads((ROOT/'configs/cases.json').read_text(encoding='utf-8'))['cases']
    refs = {'DS':(800,'设计流程!E11'),'strain':(2000,'设计流程!E12'),'TSR':(75,'设计流程!E10'),'residual':(85,'设计流程!E10')}
    return [dict(case, scenario={
        'name': case['title'], 'maintenance_method': '既定养护方案下的再生混合料选材', 'layer': '沥青面层（演示设定）',
        'distress_type': case['family'], 'climate_zone': None, 'traffic_level': None,
        'targets': [{'metric': m, 'operator': '>', 'value': v,
            'source_kind': 'enterprise_reference' if v == refs[m][0] else 'demo_assumption',
            'reference':refs[m][1] if v == refs[m][0] else f'构造案例{case["id"]}团队演示目标',
            'test_method':None,'conditions':None} for m,v in case['targets'].items()],
        'candidate_ids': case['candidate_ids'], 'rap_min_pct': case['rap_min_pct'], 'priority': case['priority'],
        'case_id': case['id'], 'context_kind': 'constructed_demo'}) for case in cases]


def scene_rules():
    reference = [{'metric': 'DS', 'value': 800, 'operator': '>', 'reference': '设计流程!E11'},
                 {'metric': 'strain', 'value': 2000, 'operator': '>', 'reference': '设计流程!E12'},
                 {'metric': 'TSR', 'value': 75, 'operator': '>', 'reference': '设计流程!E10'},
                 {'metric': 'residual', 'value': 85, 'operator': '>', 'reference': '设计流程!E10'}]
    return {'version': RULE_VERSION, 'metrics': METRICS,
        'families': [{'id':'rutting','name':'高温车辙','priority':'DS'}, {'id':'cracking','name':'低温开裂','priority':'strain'},
                     {'id':'water','name':'水损害','priority':'TSR'}],
        'references': reference, 'scope': '工作簿企业参考要求；项目目标须由工程师确认。构造案例不代表区域规范。'}


def assess(recipe, scenario):
    failed, missing, checks = [], [], []
    for target in scenario.targets:
        value = recipe['metrics'].get(target.metric)
        ok = None if value is None else satisfies(value, target)
        if ok is False:
            failed.append(target.metric)
        elif ok is None:
            missing.append(target.metric)
        checks.append(dict(target.model_dump(), actual=value, unit=METRICS[target.metric]['unit'], passes=ok))
    if scenario.rap_min_pct > 0:
        rap = recipe['rap_nominal_pct']
        if rap is None:
            missing.append('RAP')
        elif rap < scenario.rap_min_pct:
            failed.append('RAP')
    if scenario.budget is not None:
        missing.append('unit_cost')
    return dict(recipe, status='excluded' if failed else 'needs_test' if missing else 'needs_review',
                passes_targets=not failed and not missing, failed_metrics=failed, missing_metrics=missing, checks=checks,
                evidence_state='variant_requires_testing' if recipe['kind'] != 'historical' else 'historical_screening',
                applicability_notes=['试验条件与工程场景适用性待复核', '名义RAP比例的计量基准待确认'])


def recommend(session, scenario: Scenario):
    ds = latest_dataset(session)
    pool = catalog(session, context_kind=scenario.context_kind)
    if scenario.candidate_ids is not None:
        ids = set(scenario.candidate_ids)
        resolved = {r['id'] for r in pool if r['id'] in ids or r['payload'].get('fixture_id') in ids}
        known = {r['id'] for r in pool} | {r['payload'].get('fixture_id') for r in pool}
        if ids - known:
            raise HTTPException(422, f'候选ID不存在：{sorted(ids-known)}')
        pool = [r for r in pool if r['id'] in resolved]
    else:
        pool = [r for r in pool if r['kind'] == 'historical']
    if scenario.available_sources is not None:
        pool = [r for r in pool if r['source'] in scenario.available_sources]
    results = [assess(r, scenario) for r in pool]
    priority_target = next((t for t in scenario.targets if t.metric == scenario.priority), None)
    ascending = priority_target and priority_target.operator in ['<', '<=']
    def sort_key(r):
        val = r['metrics'].get(scenario.priority)
        return (not r['passes_targets'], len(r['failed_metrics']), len(r['missing_metrics']),
                (val if ascending else -val) if val is not None else float('inf'), r['id'])
    results.sort(key=sort_key)
    passed = [r['id'] for r in results if r['passes_targets']]
    payload = {'scenario': scenario.model_dump(), 'results': results, 'recommended_for_review': passed,
        'summary': {'total': len(results), 'needs_review': len(passed),
                    'needs_test': sum(r['status'] == 'needs_test' for r in results),
                    'excluded': sum(r['status'] == 'excluded' for r in results)},
        'empty_reason': None if passed else '当前候选没有同时满足全部目标的历史依据；请补充试验或显式调整目标后重新计算。',
        'next_tests': next_tests(results, scenario), 'versions': {'app': VERSION, 'rule': RULE_VERSION,
            'dataset_id': ds.id, 'dataset_sha256': ds.sha256, 'dataset_revision': ds.revision, 'importer': ds.importer_version},
        'limitations': ['历史记录初筛结果需要工程师审核与场景试验；不代表工程验收。',
                       '无价格、碳因子与路面寿命实测数据，不能据此计算成本、减碳量或寿命。']}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    payload['snapshot_sha256'] = hashlib.sha256(canonical.encode()).hexdigest()
    record = Recommendation(id='rec_'+uuid4().hex, dataset_id=ds.id, payload=payload)
    session.add(record)
    session.commit()
    return dict(record.payload, id=record.id, created_at=record.created_at)


def next_tests(results, scenario):
    suggestions = []
    for r in results:
        for metric in r['missing_metrics']:
            reason = '缺少目标指标的试验依据' if metric in METRICS else '需补充真实材料价格与计价边界' if metric == 'unit_cost' else '需先确认名义RAP身份及计量口径'
            suggestions.append({'recipe_id':r['id'], 'metric':metric, 'reason':reason, 'priority':0})
        if r['passes_targets']:
            suggestions.append({'recipe_id':r['id'], 'metric':scenario.priority,
                                'reason':'历史初筛满足目标，优先核验关键指标及条件适用性', 'priority':1})
        elif r['failed_metrics']:
            metric = scenario.priority if scenario.priority in r['failed_metrics'] else r['failed_metrics'][0]
            suggestions.append({'recipe_id':r['id'], 'metric':metric,
                                'reason':'历史记录与目标冲突，先核对记录及项目要求；复测不保证达标', 'priority':2})
    return sorted(suggestions, key=lambda x:(x['priority'],x['recipe_id'],x['metric']))[:12]


def create_variant(session, recipe_id, request: VariantInput):
    parent = require_recipe(session, recipe_id)
    fields = request.model_dump(exclude_none=True, exclude={'note'})
    if 'product' in fields:
        fields['product'] = norm(fields['product'])
        if not fields['product']:
            raise HTTPException(422, '沥青产品不能仅为空格')
    changes = {k:{'before':getattr(parent,k), 'after':v} for k,v in fields.items() if getattr(parent,k) != v}
    if not changes:
        raise HTTPException(422, '请至少修改一个设计输入')
    values = {k:getattr(parent,k) for k in ['source','gradation','product','oil_stone_ratio_pct','rap_nominal_pct']}
    values.update(fields)
    payload = {'note':request.note, 'changes':changes, 'evidence_kind':'untested_design_variant',
               'flags':['all_parent_performance_invalidated','rap_mass_basis_unconfirmed','requires_new_tests'],
               'gradation':None if 'rap_nominal_pct' in changes else parent.payload.get('gradation')}
    recipe = Recipe(id='var_'+uuid4().hex, dataset_id=parent.dataset_id, parent_id=parent.id,
                    kind='variant', payload=payload, **values)
    session.add(recipe)
    session.commit()
    return recipe_detail(session, recipe.id)


def create_observation(session, request: ObservationInput):
    recipe = require_recipe(session, request.recipe_id)
    payload = request.model_dump()
    payload['recipe_id'] = recipe.id
    existing = session.exec(select(Observation).where(Observation.idempotency_key == request.idempotency_key)).first()
    if existing:
        original = {k:v for k,v in existing.payload.items() if k != 'review'}
        if original != payload:
            raise HTTPException(409, '幂等键已用于不同内容，请使用新键')
        return existing.model_dump()
    if request.supersedes_id:
        old = session.get(Observation, request.supersedes_id)
        if not old or old.recipe_id != recipe.id or old.metric != request.metric or old.data_scope != request.data_scope:
            raise HTTPException(422, '修订必须引用同一方案、指标与数据范围的既有记录')
    observation = Observation(id='obs_'+uuid4().hex, recipe_id=recipe.id, idempotency_key=request.idempotency_key,
                              metric=request.metric, value=request.value, unit=request.unit,
                              data_scope=request.data_scope, payload=payload)
    session.add(observation)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.exec(select(Observation).where(Observation.idempotency_key == request.idempotency_key)).first()
        if existing is None:
            raise
        return create_observation(session, request)
    session.refresh(observation)
    return observation.model_dump()


def review_observation(session, observation_id, request: ReviewInput):
    observation = session.get(Observation, observation_id)
    if not observation:
        raise HTTPException(404, '试验记录不存在')
    if observation.state != 'draft':
        raise HTTPException(409, '已审核记录保持不变，请新建修订记录')
    observation.state, observation.use_for_recommendation = request.state, request.use_for_recommendation
    observation.payload = dict(observation.payload, review=dict(request.model_dump(), reviewed_at=now()))
    if request.use_for_recommendation:
        recipe = session.get(Recipe, observation.recipe_id)
        ds = session.get(Dataset, recipe.dataset_id)
        ds.revision += 1
        session.add(ds)
    session.add(observation)
    session.commit()
    session.refresh(observation)
    return observation.model_dump()


def get_snapshot(session, recommendation_id):
    rec = session.get(Recommendation, recommendation_id)
    if rec is None:
        raise HTTPException(404, '报告不存在')
    return dict(rec.payload, id=rec.id, created_at=rec.created_at)


def html_report(snapshot):
    def e(v):
        return escape(str(v if v is not None else '—'), quote=True)
    rows = []
    for r in snapshot['results']:
        metrics = ''.join(f'<td>{e(round(r["metrics"][m],3) if r["metrics"].get(m) is not None else None)}</td>' for m in CORE_METRICS)
        refs = '; '.join(f'{m}: '+', '.join(f'{p["sheet"]}!{p["cell"]}' for p in ev.get('raw_labels',[]))
                         if ev.get('raw_labels') else f'{m}: {ev.get("observation_id", "待试验")}' for m,ev in r['evidence'].items())
        rows.append(f'<tr><td>{e(r["display_id"])} · {e(r["source"])}/{e(r["gradation"])}<br>{e(r["product"])}</td>{metrics}<td>{e(r["status"])}</td></tr>'
                    f'<tr><td colspan="6" class="refs">依据：{e(refs)}<br>未满足：{e(r["failed_metrics"])}；缺失：{e(r["missing_metrics"])}</td></tr>')
    targets = ', '.join(f'{METRICS[t["metric"]]["label"]} {t["operator"]} {t["value"]} {METRICS[t["metric"]]["unit"]}（{t["source_kind"]}；{t.get("reference") or "用户项目目标"}）' for t in snapshot['scenario']['targets'])
    details = e(json.dumps({'scenario': snapshot['scenario'], 'versions':snapshot['versions'],
                           'limitations':snapshot['limitations']},ensure_ascii=False,indent=2))
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>数智选材方案报告</title>
<style>body{{font:15px/1.7 "Microsoft YaHei",sans-serif;color:#183b54;max-width:1060px;margin:48px auto;padding:0 24px}}h1{{font-size:28px}}table{{width:100%;border-collapse:collapse}}td,th{{border-bottom:1px solid #dce4e8;padding:12px;text-align:left}}th{{background:#eef4f6}}.refs{{font-size:12px;color:#526775}}pre{{white-space:pre-wrap;background:#f4f7f9;padding:20px}}@media print{{body{{margin:10px}}}}</style>
<h1>{e(snapshot['scenario']['name'])}</h1><p>历史材料记录与项目目标初筛 · 等待工程师审核与适用性试验</p>
<p>{e(targets)}</p><p>推荐复核 {len(snapshot['recommended_for_review'])} 项 / 候选 {len(snapshot['results'])} 项。</p>
<table><thead><tr><th>方案</th><th>DS 次/mm</th><th>应变 με</th><th>TSR %</th><th>残留稳定度 %</th><th>筛选状态</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p>{e(snapshot.get('empty_reason') or '')}</p><h2>输入、版本与边界</h2><pre>{details}</pre>
<p class="refs">报告 {e(snapshot['id'])}<br>生成时间 {e(snapshot['created_at'])}<br>快照 SHA256 {e(snapshot['snapshot_sha256'])}</p></html>'''
