from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import unicodedata

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis'
data = json.loads((OUT / 'performance_records.json').read_text(encoding='utf-8'))
raw = json.loads((OUT / 'workbook_raw.json').read_text(encoding='utf-8'))
blocks = json.loads((OUT / 'gradation_blocks.json').read_text(encoding='utf-8'))
formulas = openpyxl.load_workbook(next(ROOT.glob('*.xlsx')), data_only=False)


def norm(x):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(x)))


def number(x):
    return isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x)


def key(record):
    product = record['product_key']
    if record['source'] == 'B' and '沥青方案' in product and record['sheet'] in ['高温车辙', '低温弯曲']:
        product = re.sub(r'-\d+$', '', norm(record['specimen']))
    return (record['source'], record['grade_key'], product, round(record['oil'], 6) if number(record['oil']) else str(record['oil']))


groups = {}
suspected_mean = []
for sheet, records in data.items():
    grouped = defaultdict(list)
    for record in records:
        grouped[key(record)].append(record)
    groups[sheet] = grouped
    if sheet == '高温车辙':
        for identity, items in grouped.items():
            values = [r['targets']['DS'] for r in items]
            if len(values) == 3 and all(map(number, values)) and abs(values[2] - (values[0] + values[1]) / 2) < 1e-7:
                suspected_mean.append({'identity': identity, 'rows': [r['row'] for r in items], 'values': values})

curves_by_raw_id = defaultdict(list)
fingerprints = defaultdict(set)
for rowno, row in enumerate(raw['集料筛分及密度']['expanded'][2:], 3):
    if row[0] is None:
        continue
    identity = tuple(map(norm, row[:3]))
    curves_by_raw_id[identity].append((rowno, row[3:15]))
    if all(map(number, row[3:15])):
        fp = tuple(round(x, 6) for x in row[3:15])
        fingerprints[fp].add(norm(row[0]))

component_disagreements = []
blend_disagreements = []
blend_sums = []
for block in blocks:
    mix = [0.] * 12
    total = 0.
    complete = True
    for component in block['components']:
        a, b = component['new_old_fraction'], component['within_fraction']
        if not number(a) or not number(b):
            complete = False
            continue
        weight = a * b
        total += weight
        curve = component['sieving']
        if weight > 1e-10:
            if all(map(number, curve)):
                mix = [p + weight * q for p, q in zip(mix, curve)]
            else:
                complete = False
            lookup = (block['source'], norm(component['type']), norm(component['size']))
            candidates = curves_by_raw_id.get(lookup, [])
            if candidates and all(map(number, curve)):
                distance = [max(abs(x-y) for x, y in zip(curve, c)) for _, c in candidates if all(map(number, c))]
                if distance and min(distance) > 0.01:
                    component_disagreements.append({'source': block['source'], 'grade': block['grade_key'],
                        'grade_row': component['row'], 'raw_rows': [r for r, _ in candidates],
                        'max_difference_pp': min(distance), 'type': component['type'], 'size': component['size']})
    blend_sums.append(total)
    recorded = raw['级配']['values'][block['row_start'] + 8][6:18]
    if complete and abs(total - 1.0) < 1e-8 and all(map(number, recorded)):
        delta = max(abs(x-y) for x,y in zip(mix, recorded))
        if delta > 0.01:
            blend_disagreements.append({'source': block['source'], 'grade': block['grade_key'], 'row': block['row_start']+9,
                                        'max_difference_pp': delta})

examples = []
requested = [('S','AC-13','70#'), ('S','AC-13','110#-1'), ('S','AC-13','110#-2'),
             ('M-1','AC-13-3','90#'), ('1B','AC-13-3','AC-13-3(130#)'),
             ('1L','AC-13-1','AC-13-1(90#)'), ('1L','AC-13-2','AC-13-2(110#)'),
             ('1N','AC-13','AC-13(90#)'), ('1N','AC-13','AC-13(70#)')]
for source, grade, product in requested:
    result = {'source': source, 'grade': grade, 'product': product, 'evidence': {}}
    block = next((b for b in blocks if b['source']==source and b['grade_key']==grade), None)
    if block:
        result['RAP_recorded_fraction'] = block['rap_fractions']
        result['gradation_rows'] = [block['row_start'],block['row_end']]
    for sheet, grouped in groups.items():
        selected = [(identity, items) for identity, items in grouped.items() if identity[:3] == (source,grade,product)]
        for identity, items in selected:
            target_summary = {}
            for target in items[0]['targets']:
                pairs = [(r['row'], r['targets'][target]) for r in items if number(r['targets'][target])]
                if not pairs:
                    continue
                factor = 100 if target == 'TSR_raw' else 1
                vals = [v * factor for _,v in pairs]
                target_summary[target] = {'rows': [row for row,_ in pairs], 'n_recorded': len(pairs),
                    'mean_recorded': statistics.mean(vals), 'min': min(vals), 'max': max(vals)}
            result['evidence'][sheet] = {'oil_pct':identity[3], 'rows': [r['row'] for r in items], 'targets':target_summary}
    examples.append(result)

evidence = {'operational_key_counts': {s:len(g) for s,g in groups.items()},
    'DS_suspected_derived_mean_groups': len(suspected_mean), 'DS_suspected_derived_mean_examples': suspected_mean[:4],
    'nonzero_component_curve_disagreement_count':len(component_disagreements), 'nonzero_component_curve_disagreements':component_disagreements,
    'recorded_blend_formula_disagreement_count':len(blend_disagreements), 'recorded_blend_formula_disagreements':blend_disagreements,
    'blend_weight_sum_min':min(blend_sums), 'blend_weight_sum_max':max(blend_sums),
    'blend_weight_sum_note':'零值代表B-2为合成曲线输入，未提供分档比例，不能据此判断原配方比例不合格。',
    'shared_raw_curve_source_pairs': sorted({tuple(sorted(s)) for s in fingerprints.values() if len(s)>1}),
    'case_evidence':examples,
    'T_oil_formulas': {f'{col}{row}': formulas['低温弯曲'][f'{col}{row}'].value for row in [143,144,145,148] for col in ['E','F']}}
(OUT/'derived_evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in evidence.items() if k not in ['case_evidence','nonzero_component_curve_disagreements','recorded_blend_formula_disagreements']},ensure_ascii=False,indent=2))
print('CURVE EXAMPLES',json.dumps(component_disagreements[:3],ensure_ascii=False))
print('CASE EVIDENCE')
for result in examples:
    print(result['source'],result['grade'],result['product'],'RAP',result.get('RAP_recorded_fraction'))
    for sheet, item in result['evidence'].items():
        print(' ',sheet,item['oil_pct'],{k:(round(v['mean_recorded'],4),v['n_recorded'],v['rows']) for k,v in item['targets'].items()})
