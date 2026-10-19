"""Read-only diagnostic of competition scope and existing case pools."""
import argparse
import hashlib
import json
from pathlib import Path

from sqlmodel import Session

from app.domain.contracts import CORE_METRICS, Scenario
from app.services import assess, case_cards, catalog, latest_dataset
from app.settings import ROOT
from app.storage import engine


def analyze(code_revision=None):
    definitions=json.loads((ROOT/'configs/cases.json').read_text(encoding='utf-8'))['cases']
    with Session(engine) as session:
        ds=latest_dataset(session)
        all_recipes=[r for r in catalog(session) if r['kind']=='historical']
        index={r['display_id']:r for r in all_recipes}
        complete=[r for r in all_recipes if all(m in r['metrics'] for m in CORE_METRICS)]
        # Diagnostic scope only: AC-13 name plus all four labels, not engineering eligibility.
        ac13=[r for r in complete if 'AC-13' in r['gradation']]
        cases=[]
        for definition,card in zip(definitions,case_cards()):
            scenario=Scenario.model_validate(card['scenario'])
            pool=[index[i] for i in definition['candidate_ids']]
            baseline=max(pool,key=lambda r:r['metrics'].get(definition['baseline_priority'],float('-inf')))
            baseline_assessment=assess(baseline,scenario)
            screened=[assess(r,scenario) for r in pool]
            broad=[assess(r,scenario) for r in ac13]
            passing=[r for r in screened if r['passes_targets']]
            passing.sort(key=lambda r:(-r['metrics'][scenario.priority],r['id']))
            broad_pass=[r for r in broad if r['passes_targets']]
            broad_pass.sort(key=lambda r:(-r['metrics'][scenario.priority],r['id']))
            cases.append({'case_id':definition['id'],'title':definition['title'],
                'context':'constructed_demo','targets':card['scenario']['targets'],
                'fixed_pool':definition['candidate_ids'],
                'baseline_single_metric':{'metric':definition['baseline_priority'],
                    'selected':baseline['display_id'],'passes_targets':baseline_assessment['passes_targets'],
                    'failed_metrics':baseline_assessment['failed_metrics'],'missing_metrics':baseline_assessment['missing_metrics']},
                'baseline_full_constraints':{'selected':[r['display_id'] for r in passing],
                    'note':'当前v0.1规则筛选本身；也是下一版必须保留的强基线'},
                'expanded_numeric_ac13_pool':{'size':len(ac13),'passing':[r['display_id'] for r in broad_pass],
                    'passing_count':len(broad_pass),'top_by_current_priority':broad_pass[0]['display_id'] if broad_pass else None,
                    'priority_optimum_ties':[r['display_id'] for r in broad_pass if abs(r['metrics'][scenario.priority]-broad_pass[0]['metrics'][scenario.priority])<1e-9] if broad_pass else [],
                    'note':'只扩大数值诊断池，未核实层位、批次、试验条件、施工或库存；不得称为工程推荐'},
                'baseline_metrics':baseline['metrics']})
        payload={'review_date':'2026-10-19','code_revision':code_revision,'dataset_id':ds.id,'dataset_revision':ds.revision,
            'importer_version':ds.importer_version,'workbook_sha256':ds.sha256,
            'official_pdf':next(ROOT.glob('*.pdf')).name,
            'official_pdf_sha256':hashlib.sha256(next(ROOT.glob('*.pdf')).read_bytes()).hexdigest(),
            'coverage':{'historical_operational_keys':len(all_recipes),'four_metric_present':len(complete),
                'four_metric_present_ac13':len(ac13),'per_metric':{m:sum(m in r['metrics'] for r in all_recipes) for m in CORE_METRICS}},
            'diagnostic_pool':[{'id':r['id'],'display_id':r['display_id'],'source':r['source'],'gradation':r['gradation'],
                'product':r['product'],'oil_stone_ratio_pct':r['oil_stone_ratio_pct'],'rap_nominal_pct':r['rap_nominal_pct'],
                'metrics':{m:r['metrics'][m] for m in CORE_METRICS},'quality_flags':r['payload']['flags'],
                'references':{m:[{'sheet':l['sheet'],'cell':l['cell']} for l in r['evidence'][m].get('raw_labels',[])] for m in CORE_METRICS}}
                for r in ac13],
            'cases':cases,'limitations':['固定案例经过构造和挑选，基准对照仅解释当前逻辑，不是独立工程验证。',
                '基准与系统使用相同已知标签，不能把规则正确执行记作预测准确率。',
                '完整四标签只表示数值存在，不表示试验条件一致、独立配方或工程适用。']}
        payload['diagnostic_pool_sha256']=hashlib.sha256(json.dumps(payload['diagnostic_pool'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    output=ROOT/'design/competition_alignment_evidence_v2.json'
    output.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'coverage':payload['coverage'],'cases':[{'id':c['case_id'],
        'single_metric':c['baseline_single_metric'],'fixed_pool_pass':c['baseline_full_constraints']['selected'],
        'expanded_pass_count':c['expanded_numeric_ac13_pool']['passing_count'],
        'expanded_top':c['expanded_numeric_ac13_pool']['top_by_current_priority']} for c in cases]},ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--code-revision');a=p.parse_args();analyze(a.code_revision)
