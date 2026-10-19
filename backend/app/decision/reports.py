"""Self-contained, escaped HTML reports from frozen evidence only."""
from html import escape
import json


def value(item):
    if item is None:
        return '未知 / 未披露'
    return f'{item:,.2f}' if isinstance(item, (int, float)) else escape(str(item))


def html_report(decision):
    e = lambda item: escape(str(item))
    demand = decision['demand']
    targets = ''.join(f"<tr><td>{e(t['metric'])}</td><td>{e(t['operator'])} {value(t['value'])} {e(t['unit'])}</td><td>{e(t['source']['kind'])}：{e(t['source']['reference'])}</td><td>{e(t['test_method'] or '待确认')} / {e(json.dumps(t['conditions'], ensure_ascii=False))}</td></tr>" for t in demand['targets'])
    states = {'satisfied':'满足','failed':'不满足','missing':'缺测','incomparable':'不可比'}
    rows = ''
    for row in decision['results']:
        fields = row['scheme']['fields']
        checks = '<br>'.join(e(c['metric']) + '：' + states[c['state']] + (' / 余量 ' + value(c['margin']) if c.get('margin') is not None else '') for c in row['checks'])
        rows += f"<tr><td>{e(row['display_id'])}</td><td>{value(fields['source_code']['value'])} / {value(fields['gradation']['value'])} / {value(fields['product']['value'])}</td><td>{value(fields['oil_stone_ratio_pct']['value'])}% / RAP {value(fields['rap_nominal_pct']['value'])}%（名义）</td><td>{checks}</td><td>{e(row['status'])}</td></tr>"
    certificates = ''
    for cert in decision['diagnosis']['certificates']:
        requirements = ' + '.join(e(t['metric']) + ' ' + e(t.get('operator','')) + ' ' + value(t.get('value')) for t in cert['requirements'])
        witnesses = ''.join(f"<li>移除 {e(w['removed_target'])} → {e(w['display_id'])}：{e(w['kind'])}</li>" for w in cert['deletion_witnesses'])
        certificates += f"<article><strong>{requirements}</strong><p>{e(cert['minimality_status'])}</p><ul>{witnesses}</ul><small>证书 {e(cert['certificate_sha256'])}</small></article>"
    schemes = ''
    focus = [r for r in decision['results'] if r['passes_known_requirements']][:3]
    if not focus:
        focus = [r for r in decision['results'] if not r['failed_targets']][:2]
    for row in focus:
        fields = ''.join(f"<div><dt>{e(key)}</dt><dd>{value(field['value'])} {e(field['unit'] or '')}<small>{e(field['status'])}</small></dd></div>" for key, field in row['scheme']['fields'].items())
        evidence = ''.join(f"<p>{e(metric)}：{value(item['value'])} {e(item['unit'])}；{item['n_recorded']}条标签；独立批次 {value(item.get('n_independent_assumed'))}；来源 " + '、'.join(e(s['sheet'])+'!'+e(s['cell']) for s in item.get('raw_labels',[])) + f"；方法 {e(item.get('method') or '未披露')}。</p>" for metric,item in row['evidence'].items() if metric in [t['metric'] for t in demand['targets']])
        schemes += f"<details open><summary>{e(row['display_id'])} · 完整材料卡</summary><dl>{fields}</dl><small>{e(row['scheme']['material_version'])}</small>{evidence}</details>"
    actions = ''.join(f"<tr><td>{e(c['display_id'])}</td><td>{e(c['metric'])}</td><td>{e(c['action'])}</td><td>{e(c['reason'])}</td><td>{e(c['stop_condition'])}</td></tr>" for c in decision.get('test_plan',{}).get('cards',[])[:12])
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(demand['request']['name'])} · 数智选材决策报告</title>
<style>body{{font:14px/1.75 'Microsoft YaHei',sans-serif;color:#183b54;max-width:1180px;margin:35px auto;padding:0 25px}}h1{{font-size:28px}}h2{{font-size:20px;border-bottom:2px solid #007f82;padding:8px 0;margin-top:28px}}small{{color:#6b7d8a;font-size:11px;overflow-wrap:anywhere}}table{{width:100%;border-collapse:collapse;font-size:12px}}td,th{{padding:10px;text-align:left;border:1px solid #dce5e9;vertical-align:top;overflow-wrap:anywhere}}th{{background:#eef4f5}}.scope{{background:#fff7e9;border-left:4px solid #ad8a40;padding:15px 20px}}article,details{{border:1px solid #dce5e9;padding:15px;margin:12px 0}}dl{{display:grid;grid-template-columns:repeat(3,1fr)}}dt{{color:#6b7d8a;font-size:11px}}dd{{margin:5px 0 12px}}dd small{{display:block}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f7f9;padding:15px;font-size:11px}}@media print{{body{{margin:0;font-size:11px}}details{{break-inside:avoid}}table{{font-size:10px}}}}</style>
<h1>数智选材 · {e(demand['request']['name'])}</h1><p>冻结决策 {e(decision['id'])} · {e(decision['created_at'])}</p><div class="scope"><strong>{'团队构造演示' if decision['scope']['context_kind']=='constructed_demo' else '项目选材证据核验'}</strong><p>{e(decision['scope']['scope_note'])}</p><p>历史数值满足不等于工程适用；价格、碳排、寿命与现场收益缺少真实证据，不能据此核算。材料发布须工程师审核和独立试验。</p></div>
<h2>场景与性能需求</h2><pre>{e(json.dumps(demand['request']['scene'],ensure_ascii=False,indent=2))}</pre><p>{e(demand.get('case_application',{}).get('source','') if demand.get('case_application') else '三类构造场景规则或有出处的项目要求')}</p><table><tr><th>指标</th><th>目标</th><th>来源</th><th>试验口径</th></tr>{targets}</table>
<h2>冻结范围与诊断</h2><p>目录 {decision['pool_summary']['catalogue_total']}，入选 {decision['pool_summary']['included']}，检索排除 {decision['pool_summary']['excluded']}。{e(decision['scope']['evidence_view_note'])}</p><p><strong>{e(decision['diagnosis']['message'])}</strong></p>{certificates}<p>{e(decision['diagnosis']['scope_note'])}</p><small>池哈希 {e(decision['pool_sha256'])}<br>需求哈希 {e(decision['confirmation_sha256'])}</small>
<h2>同池候选判断</h2><p>{e(decision['comparison']['rule'])}</p><table><tr><th>候选</th><th>材料身份</th><th>用油与RAP</th><th>逐项判断</th><th>状态</th></tr>{rows}</table>
<h2>完整方案与证据</h2>{schemes or '<p>此范围内没有可列为待补齐或待审核的材料。请先复核冲突或增加独立候选。</p>'}
<h2>下一步核验行动</h2><p>{e(decision.get('test_plan',{}).get('note','旧版报告未含验证计划'))}</p><table><tr><th>候选</th><th>项目</th><th>行动</th><th>理由</th><th>停止条件</th></tr>{actions}</table><p>仅列前12项，完整动作和所有候选原始证据保存于决策JSON快照。</p>
<h2>复核指纹</h2><small>决策 SHA-256 {e(decision['sha256'])}<br>数据 {e(json.dumps(decision['scope']['dataset'],ensure_ascii=False))}<br>规则与注册表 {e(json.dumps(demand['versions'],ensure_ascii=False))}</small><p>此报告从冻结快照生成，模型研究值不替代实测，也未参与硬约束通过判定。</p></html>'''
