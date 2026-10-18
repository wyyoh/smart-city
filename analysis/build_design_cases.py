"""Build a small, auditable historical screening demonstration, without model predictions."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
evidence = json.loads((ROOT/'analysis/derived_evidence.json').read_text(encoding='utf-8'))
OUT = ROOT/'design'
OUT.mkdir(exist_ok=True)

metric_sources = {
    'DS':('高温车辙','DS'), 'strain':('低温弯曲','strain'),
    'TSR':('冻融劈裂','TSR_raw'), 'residual':('浸水马歇尔','residual_ratio_raw'),
}
candidates = []
for i, record in enumerate(evidence['case_evidence'], 1):
    item = {'id':f'R{i}', 'source':record['source'], 'gradation':record['grade'], 'product':record['product'],
            'rap_nominal_pct':record['RAP_recorded_fraction'][0]*100,
            'metrics':{}, 'metric_ranges':{}, 'references':{}, 'evidence_kind':'historical_record_aggregate',
            'release_status':'research_screening_only'}
    for metric,(sheet,target) in metric_sources.items():
        cell = record['evidence'].get(sheet,{}).get('targets',{}).get(target)
        item['metrics'][metric] = cell['mean_recorded'] if cell else None
        if cell:
            item['metric_ranges'][metric] = [cell['min'],cell['max']]
            item['references'][metric] = {'sheet':sheet,'rows':cell['rows'],'n_recorded':cell['n_recorded']}
    oil_values = [record['evidence'].get(sheet,{}).get('oil_pct') for sheet in ['高温车辙','低温弯曲','冻融劈裂','浸水马歇尔']]
    item['oil_stone_ratio_pct'] = next((v for v in oil_values if v is not None),None)
    item['notes'] = ['合成级配与原料关联仍需按字段复核；名义RAP比例沿用原表口径。']
    if record['source'] in ['1B','1L','1N']:
        item['notes'].append('车辙第三条记录等于前两条均值，暂不据此增加独立试件数。')
    if record['source']=='M-1':
        item['notes'].append('体积表配方记为90#-3，其他性能表记为90#，本样例未自动关联体积指标。')
    candidates.append(item)

cases = [
    {'id':'C1','title':'高温重载车辙处治','family':'高温车辙','candidate_ids':['R1','R2','R3'],
     'targets':{'DS':8000,'strain':2000,'TSR':75,'residual':85}, 'rap_min_pct':0,'priority':'DS',
     'baseline_priority':'DS','provenance':'构造场景。DS>8000为团队演示目标，其余性能阈值来自工作簿设计流程。'},
    {'id':'C2','title':'寒冷地区温缩裂缝处治','family':'低温开裂','candidate_ids':['R1','R4'],
     'targets':{'DS':800,'strain':2500,'TSR':75,'residual':85}, 'rap_min_pct':0,'priority':'strain',
     'baseline_priority':'DS','provenance':'构造场景。应变>2500为团队演示目标，不代表某气候区统一验收值。'},
    {'id':'C3','title':'水损害路段修复','family':'水损害','candidate_ids':['R6','R7','R8','R9'],
     'targets':{'DS':800,'strain':2000,'TSR':85,'residual':90}, 'rap_min_pct':0,'priority':'TSR',
     'baseline_priority':'residual','provenance':'构造场景。TSR>85、残留稳定度>90为团队演示目标。'},
    {'id':'C4','title':'高RAP再生材料选型','family':'高温车辙','candidate_ids':['R1','R5','R7'],
     'targets':{'DS':6000,'strain':2200,'TSR':85,'residual':85}, 'rap_min_pct':70,'priority':'DS',
     'baseline_priority':'DS','provenance':'构造场景。名义RAP比例至少70%，其余为团队演示目标或设计流程参考值。'},
    {'id':'C5','title':'高低温与水稳定复合约束','family':'复合需求','candidate_ids':['R1','R4','R5','R7'],
     'targets':{'DS':8000,'strain':2500,'TSR':90,'residual':90}, 'rap_min_pct':0,'priority':'DS',
     'baseline_priority':'DS','provenance':'构造场景。所有高要求为团队演示目标，用于展示候选为空的处理。'},
]


def evaluate(candidate, case):
    failed, missing = [], []
    for metric, target in case['targets'].items():
        value = candidate['metrics'].get(metric)
        if value is None:
            missing.append(metric)
        elif value <= target:  # Preserve the strict > operator used by the workbook.
            failed.append(metric)
    if candidate['rap_nominal_pct'] < case['rap_min_pct']:
        failed.append('RAP')
    status = 'outside_demo_targets' if failed else 'needs_test' if missing else 'historical_screen'
    return {'candidate_id':candidate['id'],'status':status,'failed_metrics':failed,'missing_metrics':missing}


results = []
index = {c['id']:c for c in candidates}
for case in cases:
    pool = [index[cid] for cid in case['candidate_ids']]
    evaluated = [evaluate(c,case) for c in pool]
    feasible = [c for c in pool if evaluate(c,case)['status']=='historical_screen']
    feasible.sort(key=lambda c:c['metrics'][case['priority']],reverse=True)
    baseline = max(pool,key=lambda c:c['metrics'][case['baseline_priority']])
    results.append({'case_id':case['id'],'title':case['title'],'recommended_for_review':[c['id'] for c in feasible],
                    'simple_baseline':baseline['id'],'baseline_evaluation':evaluate(baseline,case),'details':evaluated})

# Boundary checks concern the rule semantics, not fitted-model performance.
assert [r['recommended_for_review'] for r in results] == [['R1'],['R4'],['R7'],['R5'],[]]
assert evaluate({'id':'edge','metrics':{'DS':8000},'rap_nominal_pct':70},
                {'targets':{'DS':8000},'rap_min_pct':70})['status']=='outside_demo_targets'
assert evaluate({'id':'missing','metrics':{},'rap_nominal_pct':70},
                {'targets':{'fatigue':1},'rap_min_pct':70})['status']=='needs_test'
assert abs(index['R1']['metrics']['TSR'] - 89.786) < 0.001

payload = {'scope':'9个历史候选子集与5个合理构造场景；按四项历史记录聚合值进行规则初筛。',
           'not_measured_outcomes':['模型泛化精度','预测区间覆盖率','工程验收','碳排放节约','路面寿命提升'],
           'candidates':candidates,'cases':cases,'results':results}
(OUT/'demo_cases.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False,indent=2))
