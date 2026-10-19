"""Build a source-linked research report and an unexecuted laboratory handoff."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import html
import json
from pathlib import Path
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from app.research.data import METRICS, dump, freeze_inputs, load_data, sha
from app.research.advanced import advanced_configs
from app.research.estimators import configurations
from app.storage import now

OUT = ROOT/'artifacts/research-v04'


def read(name):
    return json.loads((OUT/name).read_text(encoding='utf-8'))


def verify():
    freeze_inputs(OUT)
    checks = deepcopy(read('validation.json')['checks'])
    a, b = np.load(OUT/'advanced-oof.npz'), np.load(OUT/'reproduction/advanced-oof.npz')
    checks['advanced_all_oof_values_exactly_reproduced'] = set(a.files) == set(b.files) and all(np.array_equal(a[k], b[k]) for k in a.files)
    assert checks['advanced_all_oof_values_exactly_reproduced']
    D = load_data(ROOT/'artifacts/next-phase/baseline/workbench-v01.sqlite')
    advanced = read('advanced.json')
    for i, c in enumerate(advanced_configs()):
        for t, m in enumerate(METRICS):
            keep = np.isfinite(D['Y'][:, t])
            actual = np.tile(D['Y'][keep, t], 5)
            value = np.mean(abs(actual-a[f'pred_{i}'][:, keep, t].ravel()))
            assert np.isclose(value, advanced['summaries'][c['id']][m]['mae'], rtol=1e-12)
    checks['all_33_advanced_configuration_mae_recomputed'] = True
    for name in ['cost-replay.json', 'baseline-sensitivity.json']:
        for campaign in read(name)['runs']:
            seen = set(campaign['initial_groups']); cost = 0
            for step in campaign['history']:
                assert set(step['visible_groups_before_query']) == seen
                assert step['queried_group'] not in seen
                seen.add(step['queried_group']); cost += step['panel_cost']
                assert cost == step['panels_spent'] and cost <= campaign['budget']
            assert cost == campaign['panels_spent']
    checks['all_1080_cost_matched_campaigns_budget_and_group_audit'] = True
    # Recheck historical integrity without overwriting any previous receipt.
    baseline = json.loads((ROOT/'artifacts/review-phase/baseline.json').read_text(encoding='utf-8'))
    file_results = {name: sha(ROOT/name) == digest for name, digest in baseline['files'].items()}
    assert all(file_results.values())
    tables = {}
    with sqlite3.connect((ROOT/'data/workbench.sqlite').as_uri()+'?mode=ro', uri=True) as conn:
        for name, before in baseline['original_database'].items():
            rows = conn.execute('SELECT * FROM "'+name+'" ORDER BY id').fetchall()
            after = {'rows': len(rows), 'sha256': hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()}
            assert after == before; tables[name] = after
    assert sha(ROOT/baseline['v02_release']['path']) == baseline['v02_release']['sha256']
    release = json.loads((ROOT/'artifacts/review-phase/final-bundle.json').read_text(encoding='utf-8'))
    assert sha(ROOT/release['zip']) == release['zip_sha256']
    checks['all_84_historical_files_and_6_original_tables_unchanged'] = True
    checks['v02_and_v03_archives_unchanged'] = True
    tests = ET.parse(OUT/'pytest.xml').getroot()
    suite = tests.find('testsuite') if tests.tag != 'testsuite' else tests
    assert suite is not None and int(suite.attrib['failures']) == 0 and int(suite.attrib['errors']) == 0
    checks['python_regression_checks_passed'] = int(suite.attrib['tests'])
    cards = read('candidate-model-cards.json')
    for name, digest in cards['artifact_sha256'].items(): assert sha(OUT/'models'/name) == digest
    checks['all_four_saved_research_model_artifact_hashes'] = True
    result = {'created_at': now(), 'status': 'passed', 'checks': checks,
              'protected_file_count': len(file_results), 'original_tables': tables,
              'interpretation': 'Internal computation, replay separation and preserved history; no new material test or engineering validity is certified.'}
    dump(OUT/'final-verification.json', result)
    return result


def laboratory_handoff():
    D = load_data(ROOT/'artifacts/next-phase/baseline/workbench-v01.sqlite')
    search, plan = read('formulation-search.json'), read('laboratory-plan.json')
    family = plan['pilot']['material_families'][0]
    parent = next(r for r in D['recipes'] if r['id'] == family['parent_id'])
    hypotheses = {h['id']: h for h in search['hypotheses']}
    base_weights = [c['nominal_weight'] for c in parent['payload']['gradation']['components']]
    formulations = [{'planned_id': 'F0', 'kind': 'fresh_control', 'source_parent_id': parent['id'],
                     'oil_stone_ratio_pct': parent['oil_stone_ratio_pct'], 'rap_nominal_pct': parent['rap_nominal_pct'],
                     'nominal_component_weights': base_weights, 'measured_performance': None}]
    siblings = [h for h in search['hypotheses'] if h['parent_id'] == family['parent_id']]
    oil_ids = [key for key in family['proposed_hypothesis_ids'] if hypotheses[key]['kind'] == 'oil_ratio']
    blend = next(h for h in siblings if h['kind'] == 'nominal_blend')
    reverse = next(h for h in siblings if h['kind'] == 'nominal_blend'
                   and h['change']['from_component'] == blend['change']['to_component']
                   and h['change']['to_component'] == blend['change']['from_component'])
    selected_ids = oil_ids+[blend['id'], reverse['id']]
    for i, key in enumerate(selected_ids, 1):
        h = hypotheses[key]
        formulations.append({'planned_id': f'F{i}', 'hypothesis_id': key, 'kind': h['kind'],
            'source_parent_id': h['parent_id'], 'oil_stone_ratio_pct': h['oil_stone_ratio_pct'],
            'rap_nominal_pct': h['rap_nominal_pct'], 'nominal_component_weights': h['nominal_component_weights'],
            'change': h['change'], 'measured_performance': None})
    rng = np.random.default_rng(20261019)
    orders = [{'planned_preparation_block': f'P{i}', 'randomized_formulation_order': rng.permutation([f['planned_id'] for f in formulations]).tolist(),
               'actual_material_batch': None, 'actual_preparation_date': None} for i in range(1, 4)]
    units = {'DS': '次/mm', 'strain': 'με', 'TSR': '%', 'residual': '%'}
    template = [{'planned_preparation_block': order['planned_preparation_block'], 'planned_formulation_id': f['planned_id'],
        'metric': metric, 'unit': units[metric], 'actual_value': None, 'method_and_version': None,
        'defining_conditions': None, 'actual_specimen_count': None, 'actual_material_batch': None,
        'raw_data_reference': None, 'operator': None, 'observed_at': None}
        for order in orders for f in formulations for metric in METRICS]
    packet = {'created_at': now(), 'status': 'proposal_ready_not_executed',
        'user_constraint': '暂时没有实验室，先完成计算实验与送检方案', 'sent_to_laboratory': False,
        'laboratory': None, 'quote_or_budget': None, 'independent_material_tests_executed': 0,
        'source_code': parent['source'], 'source_code_is_confirmed_physical_supplier': False,
        'parent_gradation': parent['gradation'], 'parent_product': parent['product'],
        'formulations': formulations,
        'selection_refinement': 'The final pilot uses a symmetric reverse aggregate transfer around the same control. The earlier generic laboratory-plan.json is retained as an unexecuted first proposal.',
        'ingredient_rows': [{'sheet': '级配', 'row': c['row'], 'type': c['type'], 'size': c['size'],
                             'actual_stockpile_or_lot_id': None} for c in parent['payload']['gradation']['components']],
        'mass_basis': 'All fractions are nominal workbook fractions. Do not convert them into a batching sheet until RAP denominator, moisture, recovered binder and effective binder accounting have been confirmed.',
        'design': {'formulations': len(formulations), 'independent_preparation_blocks_proposed': 3,
                   'preparation_batches_proposed': len(formulations)*3, 'metric_results_proposed': len(template),
                   'physical_specimen_count': None, 'orders': orders,
                   'replication_note': 'Pilot proposal, not a powered confirmatory experiment or a required specimen count under a standard.'},
        'stage_0_required': plan['stage_0_required'], 'stop_rules': plan['stop_rules'],
        'primary_analysis': plan['primary_analysis'],
        'target_requirements': {m: {'value': None, 'comparison': None, 'source_clause': None, 'approved_by': None} for m in METRICS},
        'results_template': template}
    dump(OUT/'laboratory-handoff.json', packet)
    labels = {m: label for m, label in zip(METRICS, ['动稳定度', '最大弯拉应变', '冻融劈裂强度比', '残留稳定度比'])}
    header = ''.join('<th>'+html.escape(k)+'</th>' for k in ['计划编号', '类型', '油石比（%）', '名义RAP（%）', '名义组分份额'])
    kind_labels = {'fresh_control': '同期原配方对照', 'oil_ratio': '油石比微调', 'nominal_blend': '名义级配微调'}
    body = ''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in [f['planned_id'], kind_labels[f['kind']], f['oil_stone_ratio_pct'], f['rap_nominal_pct'], ', '.join(f'{w:.4f}' for w in f['nominal_component_weights'])])+'</tr>' for f in formulations)
    ingredients = ''.join('<li>'+html.escape(f"级配!第{r['row']}行：{r['type']} / "+(r['size'] if r['size'] not in ['', '\\', None] else '原表未明确规格')+'；实际料堆、批次待确认。')+'</li>' for r in packet['ingredient_rows'])
    required = ''.join('<li>'+html.escape(t)+'</li>' for t in [
        '确认原料实物身份、批次、RAP计量分母、含水率、旧结合料含量与有效结合料核算。',
        '确认工程目标条款、允许级配范围、材料和施工限制；本研究的演示阈值不直接作为送检验收值。',
        '由实验室确认各指标的方法版本、温度、荷载、老化/冻融条件及实际试件数。',
        '核对名义份额与实际称料质量；确认后重新冻结配方编号和称料表。'])
    document = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>数智选材：新配方送检方案</title>
<style>body{{font:15px/1.7 'Microsoft YaHei',sans-serif;color:#172c38;max-width:1000px;margin:36px auto;padding:0 24px}}h1{{font-size:27px}}h2{{font-size:19px;margin-top:30px}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{padding:9px;border:1px solid #c7d2d9;text-align:left;overflow-wrap:anywhere}}th{{background:#edf3f6}}.status{{padding:14px 18px;background:#fff4d9;border-left:4px solid #b27a13}}small{{color:#516572}}@media print{{body{{margin:0;font-size:11pt}}h2{{break-after:avoid}}tr{{break-inside:avoid}}}}</style>
<h1>数智选材 · 新配方送检方案</h1><p class="status">方案待条件确认。当前没有实验室；未送检，新增独立试验数为0。所有配方均待实测，表中名义份额不可直接作为实际称料单。</p>
<p>试验家族：来源代码 {html.escape(parent['source'])} / {html.escape(parent['gradation'])} / {html.escape(parent['product'])}。来源代码尚未确认对应实际供应商或材料批次。</p>
<h2>1. 拟比较的配方</h2><table><tr>{header}</tr>{body}</table>
<p>F0需要与其他方案同期重新制备。F1–F2改变油石比；F3–F4在已披露的新集料之间转移名义2%份额，保持名义RAP不变。父配方历史性能不继承给新方案。</p>
<h2>2. 组分来源</h2><ol>{ingredients}</ol><p>份额顺序对应上述原表行序。物理质量基准、含水及结合料核算确认后再换算称料质量。</p>
<h2>3. 启动前必须补齐的资料</h2><ol>{required}</ol>
<h2>4. 制备与检测安排</h2><p>{len(formulations)}种配方，每种拟独立制备3批，共{len(formulations)*3}个制备批次；每批记录四项指标，共拟{len(template)}个批次指标结果。这里不是已完成数量，也不是实际试件数量。三批仅为先导试验建议，不能视为充分统计功效。</p>
<p>按原料批次和制备日分块，块内随机排序，尽可能对检测人员隐藏配方身份。三块拟定顺序：{html.escape('；'.join(o['planned_preparation_block']+'：'+', '.join(o['randomized_formulation_order']) for o in orders))}。</p>
<p>指标：{html.escape('、'.join(labels.values()))}。方法、条件、每项试件数、目标值及批准条款均待确认。</p>
<h2>5. 判断与停试</h2><p>先核对全部必需指标和施工约束，再比较同期对照的块内差异及批次波动。出现质量核算或方法不一致时先停止并核对；差异小于试验/批次波动时保留已验证对照。用于选优的同批数据不能再次充作独立验证。</p>
<p>先导方差获得后，以事先约定的实际改进幅度安排确认试验，保留新的独立原料或制备批次。费用与周期待实验室报价。</p>
<small>结构化交接与空白结果模板：artifacts/research-v04/laboratory-handoff.json。所有实际结果字段保持为空。</small></html>'''
    (ROOT/'docs/research-v04-lab-handoff.html').write_text(document, encoding='utf-8')
    return packet


def build_report(checks, packet):
    first, advanced = read('benchmark.json'), read('advanced.json')
    audit, search, sensitivity = read('data-audit.json'), read('formulation-search.json'), read('baseline-sensitivity.json')
    source_doc = json.loads((ROOT/'docs/research-v04-sources.json').read_text(encoding='utf-8'))
    sources = {s['id']: s for s in source_doc['sources']}
    def cite(key): return f"[{sources[key]['title']}]({sources[key]['url']})"
    mean = first['summaries']['basic:mean:']; legacy = first['summaries']['legacy_nested']; improved = advanced['summaries']['fixed_half_ensemble']
    labels = dict(zip(METRICS, ['动稳定度 DS（次/mm）', '最大弯拉应变（με）', '冻融劈裂比 TSR（百分点）', '残留稳定度比（百分点）']))
    lines = ['| 指标 | 同划分均值基线 MAE | 原选模流程 MAE | 新保守集成 MAE | 相对均值变化 | 改善轮数 |', '|---|---:|---:|---:|---:|---:|']
    for m in METRICS:
        score = improved[m]; delta = score['relative_mae_improvement_vs_mean']*100
        meaning = f'下降{delta:.2f}%' if delta >= 0 else f'上升{-delta:.2f}%'
        lines.append(f"| {labels[m]} | {mean[m]['mae']:.3f} | {legacy[m]['mae']:.3f} | {score['mae']:.3f} | {meaning} | {score['repeats_better_than_mean']}/5 |")
    fixed_lines = ['| 指标 | 事后最优固定配置 | MAE | 相对均值下降 |', '|---|---|---:|---:|']
    for m in METRICS:
        pool = [(c['id'], first['summaries'][c['id']][m]) for c in configurations()]
        key, score = min(pool, key=lambda kv: kv[1]['mae'])
        fixed_lines.append(f"| {labels[m]} | `{key}` | {score['mae']:.3f} | {100*score['relative_mae_improvement_vs_mean']:.2f}% |")
    acquisition = ['| 新增历史配方记录预算 | 按来源组随机 | 按配方随机 | 空间覆盖 |', '|---:|---:|---:|---:|']
    for b in ['10', '20', '30']:
        values = [sensitivity['summaries'][p][b]['feasible_mean'] for p in ['random_uniform_group', 'random_uniform_recipe', 'space_filling']]
        acquisition.append(f'| {b} | {values[0]:.2f} | {values[1]:.2f} | {values[2]:.2f} |')
    source_lines = ['| 编号 | 来源与实际读取范围 | 对本项目的作用 |', '|---|---|---|']
    for s in source_doc['sources']:
        source_lines.append(f"| {s['id']} | [{s['title']}]({s['url']})；{s['read_scope']} | {s['project_decision']} |")
    phase_unique = len({c['id'] for c in configurations()} | {c['id'] for c in advanced_configs()})
    scope = {'created_at': now(), 'status': 'complete_offline_research_and_laboratory_proposal_scope',
        'user_constraints': {'laboratory': 'not_available', 'execution': '计算实验与送检方案', 'human_weekly_hours': '15–20'},
        'phase_1_configurations': 81, 'phase_2_configurations': 33, 'unique_configurations': phase_unique,
        'shared_outer_folds_per_round': 25, 'primary_model_fit_calls_including_inner_selection': first['fit_count']+advanced['fit_count'],
        'learning_curves': 100, 'negative_control_runs': 40, 'joint_interval_runs': 15,
        'sequential_campaigns': 60, 'cost_matched_campaigns': 180, 'baseline_sensitivity_campaigns': 900,
        'saved_research_models': 4, 'generated_untested_hypotheses': search['hypothesis_count'],
        'nominally_supported_hypotheses': search['supported_hypothesis_count'],
        'laboratory_pilot_formulations': len(packet['formulations']), 'laboratory_pilot_preparation_batches_proposed': 15,
        'independent_material_tests': 0, 'production_models_replaced': 0,
        'next_actions': [
            {'priority': 1, 'action': '补齐料源实物身份、组分与RAP/结合料计量口径、四项试验方法和关键条件；检查同输入异性能记录的来源。', 'external_dependency': 'organizer_or_material_provider'},
            {'priority': 2, 'action': '冻结先导送检的实际称料表、工程目标条款、方法及试件数量，并取得第三方报价；当前只准备交接资料。', 'external_dependency': 'laboratory'},
            {'priority': 3, 'action': '取得同期对照及新批次结果后，先盲测已冻结候选，再决定是否重训练；保留独立确认批次。', 'external_dependency': 'new_measured_data'},
            {'priority': 4, 'action': '新增数据足够后再评估ARD任务核、局部或异方差校准与带噪约束多目标优化；不能以合成性能补足验证。', 'external_dependency': 'identified_data_and_test_budget'}],
        'evidence': {'sources': 'docs/research-v04-sources.json', 'report': 'docs/research-v04-report.md',
                     'laboratory': 'docs/research-v04-lab-handoff.html', 'verification': 'artifacts/research-v04/final-verification.json'}}
    dump(ROOT/'docs/research-v04-plan.json', scope)
    report = f'''# 数智选材：性能预测与新配方设计调研及实验报告

## Material Passport

- Origin Skill：academic-research-suite；文献检索、实验执行与验证内联完成。
- Origin Mode：research / run / validate。
- Origin Date：{scope['created_at']}。
- Version Label：research_v04_report_1。
- Verification Status：VERIFIED，仅指两轮主模型计算逐值复现、数据划分与历史保护检查；材料、工程效用和新配方实测仍未验证。
- 用户约束：每周15–20小时；暂时没有实验室，先完成计算实验与送检方案。

## 1. 本轮回答了什么

本轮完成两条线的方案与实际计算：四项性能的小样本预测，以及受约束配方假设生成和下一步试验选择。81组首轮配置与33组第二轮配置共{phase_unique}个不同配置，含6组重复对照；每轮25个外层折、每折3个内层折。两轮主模型合计{scope['primary_model_fit_calls_including_inner_selection']:,}次模型/管线训练调用，包含内层选模，并非这么多个独立数据集或材料试验。

最值得保留的结果是低温应变的保守集成信号，以及在有限历史池中先覆盖设计空间的选点策略。当前证据仍不足以把四项预测作为工程判定器，也不足以宣布某个新配方性能更优。原产品版本仍为v0.3，研究模块独立存放。

## 2. 数据审计改变了研究重点

180个历史操作键中，本轮至少有一个可用目标标签且设计基础字段合格的操作键为{audit['union_labeled_rows']}个，合并成{audit['union_groups']}个来源/原料曲线族代理组；四指标完整者为{audit['complete_four_metric_rows']}条。DS、应变、TSR、残留比的可用数分别为85、72、81、79，不能把缺失指标补成实测标签。27条记录的组分曲线待复核，35条不满足本轮完整组分描述符所要求的全部核对条件。

存在15组相同已知设计输入的碰撞，其中一组DS标签跨度8402次/mm。这是当前输入表达的不可识别性证据：同一个X无法唯一解释这些结果。原料真实身份、改性/再生剂、旧结合料与试验条件等可能解释差异，但这些解释尚待原始证据，不能当成已经发现的因果因素。未因预测误差大而删掉不利记录，也未把来源代码当特征。

标签相关性也不支持无条件共享：DS与低温应变约-0.08，应变与残留比约0.52，TSR与残留比约0.37。它们只是当前选择性历史记录的描述相关，任务迁移是否有用必须由共同分组验证决定。

## 3. 调研后采用的技术路线

小样本下，模型选择带来的乐观偏差与估计方差都需要控制。因此将整条选模流程置于外层评估，所有填补、缩放、标签标准化、任务相关矩阵和集成权重只使用训练组；重复划分用于检查稳定性，不能增加独立样本量。依据：{cite('R01')}、{cite('R02')}、{cite('R04')}。

协同预测采用两种可核对实现：任务核及降秩岭回归。任务核形式为 `K((x,t),(x',t')) = k(x,x') B[t,t']`，B由训练内可观测成对标签估计、投影为半正定并收缩；对角B作为不迁移对照。缺失标签不进入核的观测向量。降秩回归只在训练内部迭代填补缺失目标并收缩共享系数。它们是本项目小样本研究实现，未声称完整复现原论文优化器。方法依据：{cite('R03')}。

首轮比较基础设计、完整可用级配及紧凑级配/交互表达；覆盖均值、中位数、岭、贝叶斯岭、弹性网、SVR、核岭、GPR、极端随机树、直方图提升、任务核与降秩模型，并对DS测试对数变换。第二轮加入12个由已披露组分份额与原料密度构造的名义描述符。未核对的组分保留缺失，不将名义密度代理误称为确认后的物理配比。

第二轮明确属于看过首轮结果后的探索：冻结33组配置，使用同一外层折作配对比较。增加固定半均值集成、保守内层筛选和非负凸权重共享。它不是新的独立测试集，不能据此宣布确认性胜出。

## 4. 预测结果：改善和退步同时保留

下表每项使用相同来源划分和对应原始标签；MAE越低越好。

{chr(10).join(lines)}

保守集成相对于旧自动选模流程四项均下降，但强均值对照仍然重要：对均值只有前三项小幅改善，残留比退步。应变5/5轮改善，均值误差差的来源组聚类描述性95%分位范围约[-26.10,-1.32]με；这只是该历史数据条件下的稳定性描述。第二轮具有适应性研究过程，不能将这个区间当独立新材料的确认性显著性。

事先登记的内部候选要求为MAE下降至少5%、至少4/5轮改善、误差差上界为负。保守集成的应变下降约4.74%，仍未达到5%门槛；不因接近门槛而事后修改规则。当前没有模型升格为正式工程判定模型。

以下是首轮在全部外层结果中事后挑出的最优固定配置，仅作为后续研究线索：

{chr(10).join(fixed_lines)}

不能把四行各自挑出的最好值拼成一个已经验证的四任务系统。嵌套自动选择总体仍未稳定战胜均值，说明小样本选模方差是实际问题。任务共享和新增密度描述符没有带来一致的四指标提升，原料信息仍需补齐。

## 5. 不确定性与负对照

完成100组学习曲线、40组训练标签向量随机化负对照，以及15次联合最大残差校准试验。负对照只随机训练标签，不改变测试真实值；未用这些诊断制造显著性p值。

联合校准按来源组划分训练、10组校准、7组测试，分数为组内各条记录各可观测任务的最大标准化残差，同时报告四指标完整测试记录的覆盖分母。覆盖大致达到研究目标时，区间往往极宽：任务核平均DS宽度约15128次/mm、TSR约32.44个百分点，工程区分度有限。未观测指标不能验证覆盖，组交换性尚未确认。

GPR标准差、统计覆盖和工程验收是不同证据。相关依据：{cite('R05')}、{cite('R09')}。本轮未对外发布多指标工程通过概率。

## 6. 新配方的反向设计已经计算到哪一步

从可核对组分的历史配方出发，完成{search['hypothesis_count']}个局部未试验假设：油石比±0.1/0.2个百分点，或在已披露且活跃的新集料料堆之间转移名义2%份额。固定基质名义牌号与名义RAP，不发明未披露的改性剂、再生剂或其用量。

生成时检查非负份额、名义和为1、原表混合曲线与分量重算一致、级配通过率0–100且随筛孔递减。731个通过当前基础设计距离与同公称粒径观测曲线包络检查。这个包络不是规范包络，距离支持不代表性能准确；所有1098个方案均无新实测、无父配方性能继承，工程放行数为0。

保存候选、预测、模型不确定性、父方案预测差、名义组分与原表行号，并用第二个保守集成对10个候选作交叉检查。预测Pareto只在代理模型下成立，不是实测最优或稳健最优配方。

长期采用“硬约束候选生成→可靠性检查→试验选点→真实回流→冻结后验证”的结构。贝叶斯多目标优化与输入噪声研究提供方法方向，但当前未声称实现qLogNEHVI或在未知噪声下找到稳健最优。依据：{cite('R06')}、{cite('R07')}。

## 7. 如何选择更值得检测的材料

先在59条四指标完整记录、32个来源代理组上隐藏目标标签，比较6种策略、10种初始划分，共60次顺序回放；一次查询揭示整个来源组，避免同组记录暗中泄漏。再补做180次按配方记录数量限制的回放，防止大来源组获得更多标签却被算成同样一次检测。

最后在同一历史池上进行100种初始化×3种预算×3种策略，共900次随机基线敏感性回放。目标固定为研究演示值DS>6000、应变>2200、TSR>85、残留比>85；不等同于真实项目要求。表中为新增找到满足四项数值目标的历史记录数均值：

{chr(10).join(acquisition)}

三种策略在上述预算下平均实际消耗均恰好达到10/20/30条记录；组内多条记录全部计费。空间覆盖在此有限池较早发现可行记录，表明预测薄弱时先覆盖设计差异值得优先研究。按组随机和按配方随机的差异同时保留，避免依靠较弱随机口径夸大效果。

这些是同一完整案例池上的初始化敏感性，不是900个独立材料数据集，不是1098个新配方已被验证，也不能换算成节省了多少实际试件、工时或经费。材料选点的比较原则参考{cite('R08')}。

## 8. 没有实验室时已经准备好的送检方案

先导选用来源代码H的AC-13-110#家族作为待确认材料体系，代码不等于实际供应商身份。拟5种配方：重新制备的原配方、油石比低/高各一档、名义集料比例双向微调各一档。每种拟独立制备3批，共15个制备批次、60个批次指标结果；不是60个试件，也不是已经执行的检测数量。

送检之前需要确认材料/批次、RAP计量分母、含水与旧/有效结合料、工程目标条款、级配包络、方法版本、温度/荷载/老化或冻融条件、实际试件数、施工适用性。未知项在交接表中保持为空。

在同原料批次与制备日内随机安排原配方和新方案，尽量盲化检测身份。原配方必须同期重新制备，不能拿历史极端结果作对照。三批仅用于先导估计波动；根据实际重要差异与先导方差另行计算确认性复验数量。选优后的同一批数据不能再次被称为独立验证。

平衡开裂、车辙和其他指标、记录压实及老化条件的工程思路参考{cite('R10')}；该来源不授权本项目的中国工程阈值。当前没有实验室，不执行或虚构新试验，不代填实验室报价，也没有向外发送资料。

## 9. 外部数据能否直接增加样本

检查到的沥青断裂研究含物理代理目标及体积/力学试后特征，其任务与我们的设计前四指标不一致，不能直接搬用其高分或把VV、稳定度、流值放进设计前预测。见{cite('R11')}。

另找到再生防水材料的公开实验仓储，记录了流变、TSRST及水敏感性等，但本轮只检查明确V1元数据，尚未证明方法、单位、材料体系和授权兼容，未下载后混入官方训练表。见{cite('R12')}。下一步先建立材料、指标、方法、条件、独立批次和授权的兼容矩阵，不能仅凭字段名字相似就合并数据。

## 10. 下一步投入顺序与完成边界

优先补料源和试验口径、核对同输入异标签记录，再将当前5配方先导交接表完善为确认后的实际称料/送检表。取得新独立批次后，先盲测已冻结的保守集成与均值对照，再决定是否重训练。真实数据足够时再做ARD任务核、局部/异方差区间和带噪约束多目标优化，不继续在同一外层结果上堆叠调参来充当新证据。

本轮计算、研究方案、可复用候选模型和送检资料已完成；新配方实测优效、真实料源泛化及工程验收仍待外部条件。新模型没有替换v0.3判定逻辑，独立材料试验数为0。

## 11. 复核入口

- [研究协议]({(OUT/'protocol.json').as_posix()})、[第二轮协议]({(OUT/'advanced-protocol.json').as_posix()})、[全部模型结果]({(OUT/'benchmark.json').as_posix()})、[集成结果]({(OUT/'advanced.json').as_posix()})。
- [候选模型卡]({(OUT/'candidate-model-cards.json').as_posix()})、[全部未试验配方]({(OUT/'formulation-search.json').as_posix()})、[100初始化回放]({(OUT/'baseline-sensitivity.json').as_posix()})。
- [可打印送检方案]({(ROOT/'docs/research-v04-lab-handoff.html').as_posix()})、[结构化交接与空白结果]({(OUT/'laboratory-handoff.json').as_posix()})。
- [最终验证]({(OUT/'final-verification.json').as_posix()})：两轮全部OOF预测逐值复现；82项Python检查通过；原84个保护文件、6张原表和v0.2/v0.3归档保持不变。11/11项统计误用扫描含选择偏差和因果边界。

复现命令在项目根目录执行，默认拒绝覆盖已有结果；重跑应指定新的输出目录。`freeze`先登记协议，`benchmark`执行首轮，随后依次执行`advanced`、`diagnostics`、`replay`、`cost-replay`、`baselines`、`search`、`fit-candidates`。完整逐值验证另见`reproduction`目录。

```powershell
.venv\\Scripts\\python.exe -X utf8 scripts/research_v04.py freeze --output artifacts/new-research-run
.venv\\Scripts\\python.exe -X utf8 scripts/research_v04.py benchmark --output artifacts/new-research-run
```

## 12. 定向调研来源登记

检索日期2026-10-19。仅列原始研究、作者材料、官方文档和原始数据仓储；本报告不是系统综述。存在性及使用范围按实际访问页面登记；未宣称全文人工阅读、全面撤稿核验或跨模型专家评审。完整字段见`docs/research-v04-sources.json`。

{chr(10).join(source_lines)}
'''
    (ROOT/'docs/research-v04-report.md').write_text(report, encoding='utf-8')
    return scope


def main():
    checks = verify()
    packet = laboratory_handoff()
    scope = build_report(checks, packet)
    # A reviewable handoff package only; it has not been sent to any laboratory.
    archive = OUT/'laboratory-handoff.zip'
    dump(OUT/'laboratory-conditions.json', {key: packet[key] for key in ['status', 'user_constraint', 'mass_basis', 'stage_0_required', 'stop_rules', 'primary_analysis', 'target_requirements', 'design']})
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
        zipped.write(ROOT/'docs/research-v04-lab-handoff.html', '送检方案.html')
        zipped.write(OUT/'laboratory-handoff.json', '配方与空白结果模板.json')
        zipped.write(OUT/'laboratory-conditions.json', '试验条件与分析方案.json')
    with zipfile.ZipFile(archive) as zipped: assert zipped.testzip() is None
    dump(OUT/'handoff-package.json', {'path': archive.relative_to(ROOT).as_posix(), 'sha256': sha(archive),
        'files': 3, 'sent_to_lab': False, 'status': 'reviewable_proposal_only'})
    files = [p for p in OUT.rglob('*') if p.is_file() and p.name != 'completion.json']
    completion = {'created_at': now(), 'status': scope['status'],
        'verification': checks['status'], 'python_checks': checks['checks']['python_regression_checks_passed'],
        'main_model_experiments_exactly_reproduced': True, 'external_material_tests': 0,
        'production_models_replaced': 0, 'user_lab_constraint': 'No laboratory now; computational experiments and submission proposal only.',
        'research_file_sha256': {p.relative_to(OUT).as_posix(): sha(p) for p in sorted(files)},
        'document_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in [ROOT/'docs/research-v04-report.md', ROOT/'docs/research-v04-plan.json', ROOT/'docs/research-v04-sources.json', ROOT/'docs/research-v04-lab-handoff.html']},
        'code_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in [*sorted((ROOT/'backend/app/research').glob('*.py')), ROOT/'scripts/research_v04.py', ROOT/'scripts/create_research_report_v04.py', ROOT/'tests/test_research_v04.py']}}
    dump(OUT/'completion.json', completion)
    print(json.dumps({'status': completion['status'], 'python_checks': completion['python_checks'], 'research_files': len(files),
                      'independent_material_tests': 0, 'report': 'docs/research-v04-report.md'}, ensure_ascii=False))


if __name__ == '__main__': main()
