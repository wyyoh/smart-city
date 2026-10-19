"""Printable HTML generated from the same review payload as the interface."""
from html import escape
import json
from .labels import label

STATE = {'satisfied': '满足', 'failed': '不满足', 'missing': '缺测', 'incomparable': '不可比'}
SOURCE = {'constructed_demo': '构造演示', 'enterprise_reference': '企业参考', 'normative': '规范声明',
          'project_target': '项目自定', 'project_approved': '项目批准声明'}
APPLICABILITY = {'unknown': '未知', 'applicable': '适用', 'inapplicable': '不相容'}


def e(value):
    return escape(str(value)) if value is not None else '待确认'


def shell(title, body):
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title>
<style>body{{font:14px/1.8 'Microsoft YaHei','DengXian',sans-serif;color:#183b54;max-width:1080px;margin:36px auto;padding:0 28px}}header{{border-bottom:3px solid #007f82;padding-bottom:22px;margin-bottom:24px}}h1{{font-size:28px;line-height:1.5;margin:8px 0}}h2{{font-size:20px;margin-top:32px}}h3{{font-size:16px}}p{{margin:8px 0}}small,.muted{{color:#5a707e}}.scope{{background:#fff7e9;border-left:4px solid #ad8a40;padding:16px 20px;margin:18px 0}}.lead{{font-size:18px}}table{{border-collapse:collapse;width:100%;font-size:12px;margin:12px 0 22px}}td,th{{border:1px solid #dce5e9;padding:9px 12px;text-align:left;vertical-align:top;overflow-wrap:anywhere}}th{{background:#eef4f5}}a{{color:#007f82}}article{{padding:14px 0;border-bottom:1px solid #dce5e9}}code,pre{{font-size:11px;white-space:pre-wrap;overflow-wrap:anywhere}}button{{border:1px solid #b3c7cd;background:white;color:#183b54;padding:9px 18px;border-radius:4px;cursor:pointer}}.fingerprints{{font-size:11px;overflow-wrap:anywhere}}.steps{{display:flex;gap:20px}}.steps>div{{flex:1}}@media(max-width:700px){{.steps{{display:block}}body{{padding:0 16px}}table{{font-size:11px}}}}@media print{{body{{max-width:none;margin:0;padding:0;font-size:11px}}h1{{font-size:23px}}h2{{font-size:17px;break-after:avoid}}button,.screen-only{{display:none}}thead{{display:table-header-group}}tr,article{{break-inside:avoid}}a{{color:inherit}}.scope{{background:#fff}}}}@page{{size:A4;margin:16mm}}</style></head><body>{body}</body></html>'''


def review_html(review):
    summary = review['numerical_summary']
    status = '生成时快照已过期' if review['status'] == 'stale' else '等待工程外部核验'
    freshness = '；'.join(review['freshness']['reasons']) or '生成时与当前输入一致'
    targets = ''.join(f"<tr><td>{e(t['label'])}</td><td>{e(t['operator'])} {e(t['value'])}{(' 至 '+e(t['upper'])) if t['upper'] is not None else ''} {e(t['unit'])}</td><td>{e(SOURCE.get(t['source']['kind'],t['source']['kind']))}<br>{e(t['source']['reference'])}</td><td>{e(t['test_method'])}<br>{e(json.dumps(t['conditions'],ensure_ascii=False))}</td><td>{'<br>'.join(e(i) for i in t['issues']) or '声明完整，仍待独立审核'}</td></tr>" for t in review['requirements'])
    candidates = ''
    for candidate in review['focus_candidates']:
        rows = ''
        for check in candidate['checks']:
            sources = '、'.join(e(x['sheet']) + '!' + e(x['cell']) for x in check['source_preview'])
            if check['source_count'] > len(check['source_preview']):
                sources += f"（展示{len(check['source_preview'])}/{check['source_count']}，全量见JSON）"
            rows += f"<tr><td>{e(label(check['metric']))}</td><td>{e(check['value'])} {e(check['unit'])}</td><td>{e(STATE[check['state']])}</td><td>{e(APPLICABILITY.get(check['engineering_applicability'],check['engineering_applicability']))}<br>{e('、'.join(label(key) for key in check['unresolved_dimensions']))}</td><td>{sources or e(check['source_reference'])}</td></tr>"
        candidates += f"<h3>{e(candidate['display_id'])} · {e(candidate['material_version'])}</h3><p>{e(candidate['identity_review'])}。组成待核验字段：{e('、'.join(label(key) for key in candidate['material_unknowns']))}。</p><table><thead><tr><th>项目</th><th>记录值</th><th>数值状态</th><th>工程适用</th><th>来源预览</th></tr></thead><tbody>{rows}</tbody></table>"
    actions = ''.join(f"<article><strong>{index+1}. {e(a['title'])}</strong><p>{e(a['reason'])}</p><small>所需：{e('；'.join(a['needed']))}　负责角色：{e(a['owner_role'])}</small></article>" for index,a in enumerate(review['actions']))
    certs = ''
    targets_by_id = {t['target_id']: t for t in review['requirements']}
    for certificate, checked in zip(review['diagnosis']['certificates'], review['certificate_checks']):
        witnesses = ''
        for witness in certificate['deletion_witnesses']:
            remaining = []
            for check in witness['remaining_checks']:
                target = targets_by_id[check['target_id']]
                remaining.append(f"{label(target['metric'])} {check.get('value')} {target['unit']}，{STATE[check['state']]}")
            removed = label(targets_by_id[witness['removed_target']]['metric'])
            witnesses += f"<tr><td>{e(removed)}</td><td>{e(witness['display_id'])}</td><td>{e('；'.join(remaining))}</td></tr>"
        minimality = '已验证包含关系下最小' if certificate['minimality_status'] == 'verified_inclusion_minimal' else '最小已知失败覆盖，见证仍有未知'
        certs += f"<article><strong>{e(' + '.join(label(t['metric']) for t in certificate['requirements']))}</strong><p>{e(minimality)}；证书校验：{'通过' if checked['valid'] else '失败'}</p><table><thead><tr><th>移除要求</th><th>见证候选</th><th>余下要求的记录值与判断</th></tr></thead><tbody>{witnesses}</tbody></table><small>{e(certificate['certificate_sha256'])}</small></article>"
    body = f'''<header><small>数智选材　选材复核单</small><h1>{e(review['name'])}</h1><p class="lead">{e(status)}</p><button onclick="window.print()">打印或保存为 PDF</button></header>
<div class="scope"><strong>{'团队构造演示' if review['context_kind']=='constructed_demo' else '项目要求核验'}</strong><p>{e(review['scope']['scope_note'])}</p><p>{e(review['source_note'])}</p></div>
<h2>本次能得出什么结论</h2><p>{e(review['diagnosis']['message'])}</p><p>候选 {summary['candidate_count']} 条，数值满足 {summary['feasible_count']} 条。{e(review['scope']['evidence_view_note'])}</p><p>工程发布批准：未执行。当前性：{e(freshness)}。</p>
<h2>要求来源及口径</h2><table><thead><tr><th>指标</th><th>目标</th><th>来源</th><th>方法与条件</th><th>待核验</th></tr></thead><tbody>{targets}</tbody></table>
<h2>优先复核候选与原始依据</h2><p>{e(review['focus_selection'])}，共{len(review['focus_candidates'])}条；本节不替代完整候选清单。</p>{candidates or '<p>当前范围没有无已知失败的候选；先复核要求、补齐证据或扩充候选。</p>'}
<h2>范围内冲突及删除见证</h2>{certs or '<p>本次没有生成可验证的冲突证书；缺测不能作为无解证明。</p>'}<p>{e(review['diagnosis']['scope_note'])}</p>
<h2>下一步核验行动</h2>{actions}
<h2>验证口径与复核指纹</h2><p>{e(review['model_note'])}</p><p>本轮价值记录执行者为AI，真人参与数0，真人用时与行业收益待验证。</p><p>{e(review['export_note'])}</p>
<div class="fingerprints">生成时间 {e(review['generated_at'])}<br>原决策 {e(review['decision_id'])}<br>原决策 SHA256 {e(review['decision_sha256'])}<br>复核单 SHA256 {e(review['review_sha256'])}<br>候选池 SHA256 {e(review['pool_sha256'])}<br>需求 SHA256 {e(review['confirmation_sha256'])}</div>'''
    return shell(review['name'] + ' · 选材复核单', body)


def handbook_html(overview):
    basic = [r for r in overview['requirements'] if r['kind'] == 'basic']
    technical = [r for r in overview['requirements'] if r['kind'] == 'technical_detail']
    bonus = [r for r in overview['requirements'] if r['kind'] == 'bonus']
    def table(items):
        return '<table><thead><tr><th>赛题要求</th><th>当前交付范围</th><th>证据文件</th></tr></thead><tbody>' + ''.join(
            f"<tr><td>{e(r['title'])}<br><small>赛题PDF第{r['source_page']}页</small></td><td><strong>{e(r['status_label'])}</strong><br>{e(r['delivered_scope'])}</td><td>" + '<br>'.join(
                f"<a href='/v2/review/evidence/{e(key)}'>{e(overview['evidence'][key]['label'])}</a> <small>{e(overview['evidence'][key]['integrity'])}</small>" for key in r['evidence_ids']) + '</td></tr>' for r in items) + '</tbody></table>'
    highlights = ''.join(f"<article><h3>{e(h['title'])}</h3><p>{e(h['question'])}</p><p>{e(h['mechanism'])}</p><ol>" + ''.join('<li>'+e(s)+'</li>' for s in h['steps']) + f"</ol><p><small>{e(h['boundary'])}</small></p></article>" for h in overview['highlights'])
    sources = ''.join(f"<article><strong>{e(s['standard'])}</strong><p>{e(s['type'])}，公告落款{e(s['notice_date'])}，页面公开{e(s['page_publication_date'])}，施行{e(s['effective_date'])}。</p><p>{e(s['verification_scope'])}</p><a href='{e(s['url'])}'>{e(s['title'])}</a></article>" for s in overview['sources'])
    qas = ''.join(f"<article><h3>{e(q['question'])}</h3><p>{e(q['answer'])}</p></article>" for q in overview['questions'])
    current = overview['current_data']
    replay_rows = overview['case_replay']['data'].get('cases', [])
    diagnosis_labels = {'numeric_feasible': '存在数值满足候选，工程适用待审', 'evidence_insufficient': '证据不足，不能证明无解', 'known_conflict': '限定池内已知冲突'}
    case_table = '<table><thead><tr><th>案例及范围</th><th>冻结候选数</th><th>B1可行数</th><th>V2可行数</th><th>范围内判断</th></tr></thead><tbody>' + ''.join(
        f"<tr><td>{e(r.get('case',r.get('case_id')))} {'完整数值演示子池' if r.get('evidence_view')=='complete_numeric_demo' else '含缺测完整目录'}</td><td>{e(r.get('pool'))}</td><td>{e(r.get('feasible_B1'))}</td><td>{e(r.get('feasible_V2'))}</td><td>{e(diagnosis_labels.get(r.get('diagnosis'),r.get('diagnosis')))}</td></tr>" for r in replay_rows) + '</tbody></table>'
    body = f'''<header><small>企业课题一　评审阅读与演示指引</small><h1>数智选材成果与证据手册</h1><p class="lead">场景要求、材料证据、冲突解释与下一步验证。</p><button onclick="window.print()">打印或保存为 PDF</button></header>
<p>作品把养护场景接到材料方案选择，展示推荐依据、未知条件和验证行动。当前为本地研究原型。</p><div class="scope">{e(overview['scope_note'])}<p>当前历史操作键{current['historical_keys']}条，AC-13目录{current['ac13_keys']}条，四指标数值完整{current['complete_four_metric_ac13_keys']}条。{e(current['identity_note'])}</p></div>
<h2>五项基本成果</h2>{table(basic)}<h2>同池案例与复核</h2><p>{e(overview['case_replay']['scope'])}。这些结果是构造软件案例回放，未据此推算真实地区推荐成功率或行业收益。数值要求正确给定时，B1与V2可行集一致。</p>{case_table}<h2>三条亮点演示</h2>{highlights}
<h2>详细技术要求的完成范围</h2>{table(technical)}<h2>加分方向及外部验证</h2>{table(bonus)}
<h2>依据版本登记</h2>{sources}<p>构造阈值保留原身份；官方公告不能单独证明项目阈值适用。</p>
<h2>答辩问答</h2>{qas}<h2>外部核验下一步</h2><ul>''' + ''.join('<li>'+e(s)+'</li>' for s in overview['external_pending']) + '''</ul><p>空白核验模板在成果入口下载；字段校验只检查格式与配对，不认证真实证据。</p>'''
    return shell('数智选材成果与证据手册', body)
