"""Printable views read the same immutable records as JSON exports."""
import html


def e(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return format(value, ',.4f').rstrip('0').rstrip('.')
    return html.escape(str(value if value is not None else '未知'))


def table(headers, rows):
    return '<table><thead><tr>'+''.join('<th>'+e(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join(
        '<tr>'+''.join('<td>'+e(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'


def record_html(record):
    kind = record['kind']; content = ''
    if kind == 'creative_case_run':
        decision = record['decision']; demand = decision['demand']
        title = record['case_id']+' '+record['title']
        content += '<p>'+e(record['identity'])+'</p><h2>工程问题</h2><p>'+e(record['question'])+'</p>'
        content += '<h2>场景与要求</h2><p>'+e('；'.join(r['rationale'] for r in demand['rules']['matches']))+'</p>'
        content += table(['指标', '要求', '单位', '来源'], [[t['metric'], t['operator']+str(t['value']), t['unit'], t['source']['reference']] for t in demand['targets']])
        rap = demand['request']['constraints']['rap_min_pct']
        if rap is not None:
            content += '<p>名义RAP最低要求：'+e(rap)+'%；质量基准待确认。</p>'
        feasible = [r for r in decision['results'] if r['passes_known_requirements']]
        content += '<h2>候选及同池基准</h2><p>当前范围 '+str(len(decision['results']))+' 条；作品数值可行 '+str(len(feasible))+' 条；B1数值可行 '+str(len(record['baseline']['feasible_ids']))+' 条。</p>'
        content += '<p>'+e(record['baseline']['method'])+'。可行集合'+('一致' if record['baseline']['same_feasible_set'] else '存在差异，需复核')+'。</p>'
        content += table(['材料', '来源代码', 'DS', '应变', 'TSR', '残留稳定度'], [[r['display_id'], r['scheme']['fields']['source_code']['value']]+[r['metrics'].get(m) for m in ['DS', 'strain', 'TSR', 'residual']] for r in feasible])
        content += '<h2>推荐理由与适用性判断</h2><p>'+e(decision['comparison']['rule'])+'</p><p>'+e(decision['diagnosis']['message'])+'</p><p>'+e(decision['scope']['evidence_view_note'])+'</p>'
        for certificate in decision['diagnosis']['certificates']:
            content += '<p>范围内冲突：'+e('、'.join(r['metric'] for r in certificate['requirements']))+'。删除见证只说明证书剩余子集。</p>'
        content += '<h2>工程师调整</h2><p>'+e(record['adjustment_reason'] or '当前为原案例要求；可在工作区比较偏好、资源目标或进入配方探索。')+'</p>'
        content += '<p>决策指纹：'+e(decision['sha256'])+'</p>'
    elif kind == 'preference_comparison':
        title = '材料方案偏好比较'
        content += '<p>'+e(record['reason'])+'</p><p>优先顺序：'+e('、'.join(record['priority_order']))+'</p>'
        content += table(['顺位', '材料', '来源代码', 'DS', '应变', 'TSR', '残留稳定度'], [[r['preference_rank'], r['display_id'], r['scheme']['fields']['source_code']['value']]+[r['metrics'].get(m) for m in ['DS', 'strain', 'TSR', 'residual']] for r in record['candidates']])
        content += '<p>'+e(record['note'])+'</p><p>原决策指纹：'+e(record['source_decision_sha256'])+'</p>'
    else:
        title = record['title']; chosen = record['hypothesis']
        content += '<h2>设计意图</h2><p>'+e(record['design_intent'])+'</p><p>父方案：'+e(record['parent_recipe_id'])+'；假设：'+e(record['hypothesis_id'])+'</p>'
        content += '<h2>原场景要求</h2>'+table(['指标', '要求', '单位'], [[t['metric'], t['operator']+str(t['value']), t['unit']] for t in record['demand_context']['targets']])
        oil = record['actual_changes']['oil_stone_ratio_pct']
        content += '<h2>组成改动</h2><p>油石比：'+e(oil['before'])+'% → '+e(oil['after'])+'%。</p>'
        content += table(['组分', '原名义份额%', '设计名义份额%', '变化/百分点'], [[c['type'], 100*c['before'], 100*c['after'], c['delta_percentage_points']] for c in chosen['components'] if c['before'] or c['after']])
        content += '<h2>父方案历史记录与新方案状态</h2>'+table(['指标', '父方案历史值', '新设计实测'], [[m, r['value'], '未知'] for m, r in chosen['parent']['metrics'].items()])
        content += '<p>'+e(record['note'])+'</p><p>原决策指纹：'+e(record['source_decision_sha256'])+'</p>'
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>'+e(title)+'</title><style>body{font:14px/1.7 "Microsoft YaHei",sans-serif;color:#183b54;max-width:1000px;margin:32px auto;padding:0 24px}h1{font-size:25px}h2{font-size:17px;margin-top:24px}table{width:100%;border-collapse:collapse;font-size:12px}th,td{border:1px solid #dce5e9;text-align:left;padding:8px}th{background:#edf4f6}p,small{overflow-wrap:anywhere}@media print{body{margin:0}tr{break-inside:avoid}h2{break-after:avoid}}</style><h1>'+e(title)+'</h1><p>保存时间：'+e(record['created_at'])+'</p>'+content+'<p>本页为保存时点的创意方案记录，历史数值比较不等于工程适用确认。</p><small>记录编号：'+e(record['id'])+'<br>保存内容SHA256：'+e(record['sha256'])+'</small></html>'
