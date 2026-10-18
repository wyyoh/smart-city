"""Reveal true recorded labels in a small historical pool; no proxy-generated truth."""
import json
from pathlib import Path
from sqlmodel import Session

from app.domain.contracts import Scenario, satisfies
from app.services import case_cards, catalog, latest_dataset
from app.settings import ROOT
from app.storage import engine


def run():
    results=[]
    with Session(engine) as session:
        recipes={r['display_id']:r for r in catalog(session)}
        ds=latest_dataset(session)
        for case in case_cards():
            scenario=Scenario.model_validate(case['scenario'])
            focus=scenario.priority
            other=[t for t in scenario.targets if t.metric!=focus]
            target=next(t for t in scenario.targets if t.metric==focus)
            # Screening only uses visible, non-focus labels. The focus label stays hidden until queried.
            pool=[recipes[i] for i in case['candidate_ids'] if all(recipes[i]['metrics'].get(t.metric) is not None and satisfies(recipes[i]['metrics'][t.metric],t) for t in other)
                  and (recipes[i]['rap_nominal_pct'] or 0)>=scenario.rap_min_pct]
            def bottleneck(r):
                margins=[(r['metrics'][t.metric]-t.value)/max(abs(t.value),1) for t in other]
                return (min(margins) if margins else 0,r['display_id'])
            policies={'id_order':sorted(pool,key=lambda r:r['display_id']), 'visible_bottleneck_first':sorted(pool,key=bottleneck)}
            outcome={}
            for policy,ordered in policies.items():
                queries=[];found=None
                for r in ordered:
                    ev=r['evidence'].get(focus)
                    if not ev:
                        continue
                    truth=r['metrics'][focus]
                    queries.append({'recipe':r['display_id'],'revealed_actual':truth,'metric':focus,
                                    'references':ev.get('raw_labels',[]),'meets_focus_target':satisfies(truth,target)})
                    if satisfies(truth,target):
                        found=r['display_id'];break
                outcome[policy]={'queries':queries,'query_count':len(queries),'found':found}
            results.append({'case_id':case['id'],'hidden_metric':focus,'visible_pool':[r['display_id'] for r in pool],'policies':outcome})
    payload={'scope':'五个构造场景的固定历史池；先隐藏一个指标，按真实原表标签逐次揭示。',
             'dataset_sha256':ds.sha256, 'results':results,
             'limitations':['样例小且经选择，不能证明试验效率的总体提升。','无真实试验成本，仅比较查询次数。','选择排序只读已揭示的其他指标，隐藏指标不进入排序。']}
    path=ROOT/'artifacts/next_test_replay.json'
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{ 'case':r['case_id'], **{p:o['query_count'] for p,o in r['policies'].items()}} for r in results],ensure_ascii=False))


if __name__=='__main__':run()
