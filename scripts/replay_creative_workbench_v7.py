"""Replay five creative cases in an isolated database; retain actual snapshots and case cards."""
from contextlib import closing
from datetime import datetime, timezone
import gzip
import hashlib
import html
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))

from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import create_app
from app.storage import make_engine
from app.decision.records import DecisionRecord, digest
from app.decision.diagnosis import verify_certificate
from app.services import latest_dataset

BASE = '/v5/design'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def checked(client, method, path, expected=200, **kwargs):
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == expected, (path, response.status_code, response.text[:500])
    return response


def execute(client, case, **changes):
    return checked(client, 'post', f'{BASE}/cases/{case}/runs', 201,
                   json={'request_id': uuid4().hex, **changes}).json()


def store_record(client, output, name, record):
    exported = checked(client, 'get', f"{BASE}/records/{record['id']}/export.json").json()
    assert exported == record
    assert digest({k: v for k, v in record.items() if k != 'sha256'}) == record['sha256']
    printed = checked(client, 'get', f"{BASE}/records/{record['id']}/print.html").text
    assert record['sha256'] in printed
    (output/(name+'.html')).write_text(printed, encoding='utf-8', newline='\n')
    (output/(name+'.json.gz')).write_bytes(gzip.compress(json.dumps(record, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode(), mtime=0))


def main():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = ROOT/'artifacts/polish-v7/runs'/stamp
    output.mkdir(parents=True, exist_ok=False)
    source = ROOT/'data/workbench.sqlite'; source_sha = sha(source)
    source_files = [p for p in (ROOT/'backend/app/creative').glob('*.py')] + [ROOT/'backend/app/main.py',
        ROOT/'frontend/src/components/CreativeWorkbench.tsx', ROOT/'frontend/src/creative-types.ts', ROOT/'frontend/src/creative.css',
        ROOT/'frontend/src/main.tsx', Path(__file__), ROOT/'tests/test_creative_workbench_v7.py']
    source_hashes = {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in source_files}
    baseline = json.loads((ROOT/'artifacts/review-phase/baseline.json').read_text(encoding='utf-8'))
    assert all(sha(ROOT/p) == h for p, h in baseline['files'].items())
    checks = {}; runs = {}; cards = []
    with tempfile.TemporaryDirectory(prefix='creative-v7-replay-') as temporary:
        database = Path(temporary)/'replay.sqlite'
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro', uri=True)) as old, closing(sqlite3.connect(database)) as new:
            old.backup(new)
        engine = make_engine(database)
        try:
            with TestClient(create_app(engine)) as client:
                for case, count in zip(['C1', 'C2', 'C3', 'C4', 'C5'], [2, 2, 5, 1, 0]):
                    result = execute(client, case); runs[case] = result; decision = result['decision']
                    assert len(decision['results']) == 84 and len(decision['comparison']['feasible_ids']) == count
                    assert result['baseline']['same_feasible_set']
                    store_record(client, output, case, result)
                    cards.append({'case_id': case, 'title': result['title'], 'question': result['question'],
                        'pool': len(decision['results']), 'feasible': count, 'baseline_feasible': len(result['baseline']['feasible_ids']),
                        'diagnosis': decision['diagnosis']['status'], 'record_id': result['id'], 'sha256': result['sha256'],
                        'html': case+'.html', 'snapshot': case+'.json.gz'})
                profiles = checked(client, 'get', BASE+'/cases').json()['cases']
                unsupported = json.loads(json.dumps(profiles[0]['example_request']))
                unsupported['scene']['climate']['class'] = 'unmapped_climate'
                resolved = checked(client, 'post', '/v2/demand-resolutions', 201, json=unsupported).json()
                assert not resolved['rules']['matches'] and not resolved['ready_for_candidate_retrieval']
                checks['A01'] = 'C1至C3每条目标均有来源；未知场景不借用规则。'
                assert all(t['source']['reference'] for case in ['C1', 'C2', 'C3'] for t in runs[case]['decision']['demand']['targets'])
                assert all(runs[c]['decision']['demand']['case_application']['id'] == c for c in ['C4', 'C5'])
                checks['A02'] = 'C4/C5附加要求保留明确构造模板身份。'
                difference = checked(client, 'get', '/v2/decision-diff', params={
                    'before_id': runs['C1']['decision']['id'], 'after_id': runs['C2']['decision']['id']}).json()
                assert difference['input_changes'] and difference['target_changes']
                write_json(output/'C1-to-C2-difference.json', difference)
                c3 = runs['C3']['decision']; preferences = {}
                for metric, first in [('TSR', 'mix_07e9acab4f8d5c4c21d0'), ('residual', 'mix_59cb42163ce4719d7809'), ('strain', 'mix_7a55a307568e18697636')]:
                    request = {'decision_id': c3['id'], 'expected_decision_sha256': c3['sha256'], 'priority_order': [metric]}
                    value = checked(client, 'post', BASE+'/preferences', json=request).json()
                    assert value['comparison']['review_first_ids'] == [first]
                    assert set(value['comparison']['feasible_ids']) == set(c3['comparison']['feasible_ids'])
                    preferences[metric] = value
                write_json(output/'C3-preference-views.json', preferences)
                saved_pref = checked(client, 'post', BASE+'/preferences', json={
                    'decision_id': c3['id'], 'expected_decision_sha256': c3['sha256'], 'priority_order': ['residual'],
                    'persist': True, 'request_id': uuid4().hex, 'reason': 'AI软件回放：水稳定门槛满足后，比较残留稳定度余量。'}).json()
                store_record(client, output, 'C3-saved-preference', saved_pref)
                checks['A03'] = '三种偏好下可行ID集合不变，首位分别为H、K和R7；五者均非支配。'
                c2 = runs['C2']['decision']; parent = 'mix_ec30ff644f3111c570bc'
                feasible = [r for r in c2['results'] if r['passes_known_requirements']]
                assert {r['metrics']['strain'] for r in feasible} == {2525.0}
                checks['A05'] = 'C2应变2525με并列，默认顺序由TSR等后续指标区分。'
                context_path = f"{BASE}/explorations/{c2['id']}/{parent}"
                context = checked(client, 'get', context_path).json()
                empty = checked(client, 'get', context_path, params=[('locked_fields', 'oil_stone_ratio_pct'), ('locked_fields', 'nominal_component_weights')]).json()
                assert context['total_parent_hypotheses'] == 10 and context['total'] == 7 and empty['total'] == 0
                assert all(r['parent_id'] == parent for r in context['items'])
                checks['A08'] = '准确R4父方案下10个假设、7个在范围内；双锁定为空，不换父方案。'
                draft_request = {'request_id': uuid4().hex, 'origin_decision_id': c2['id'], 'expected_decision_sha256': c2['sha256'],
                    'parent_recipe_id': parent, 'hypothesis_id': 'hyp_6e18d41dcaefa559', 'locked_fields': ['nominal_component_weights'],
                    'design_intent': 'AI软件回放：保持组分名义份额，探索油石比4.9%到5.0%的设计方向；不预设性能改善。',
                    'research_scope_sha256': context['scope_sha256']}
                draft = checked(client, 'post', BASE+'/drafts', 201, json=draft_request).json()
                assert draft['measured_performance'] is None and draft['hypothesis']['candidate']['measured_performance'] is None
                assert not draft['inherits_parent_measurements'] and draft['demand_context'] == c2['demand']
                assert draft['parent'] == next(r for r in c2['results'] if r['id'] == parent)
                assert checked(client, 'post', BASE+'/drafts', 201, json=draft_request).json() == draft
                store_record(client, output, 'C2-design-draft', draft)
                checks['A09'] = '草案不继承父方案实测，原需求、父方案及设计意图随记录保存。'
                c4 = runs['C4']['decision']
                with Session(engine) as session:
                    record_count = len(session.exec(select(DecisionRecord)).all())
                preview = checked(client, 'post', f"{BASE}/decisions/{c4['id']}/adjustment-preview", json={
                    'expected_decision_sha256': c4['sha256'], 'rap_min_pct': 75}).json()
                with Session(engine) as session:
                    assert len(session.exec(select(DecisionRecord)).all()) == record_count
                assert len(preview['before_feasible_ids']) == 1 and not preview['after_feasible_ids']
                write_json(output/'C4-requirement-preview.json', preview)
                changed = execute(client, 'C4', rap_min_pct=75, adjustment_reason='AI软件回放：比较更高名义RAP要求',
                    based_on_decision_id=c4['id'], expected_decision_sha256=c4['sha256'])
                assert changed['baseline']['same_feasible_set'] and not changed['decision']['comparison']['feasible_ids']
                store_record(client, output, 'C4-adjusted', changed)
                write_json(output/'C4-difference.json', checked(client, 'get', '/v2/decision-diff', params={
                    'before_id': c4['id'], 'after_id': changed['decision']['id']}).json())
                boundary = checked(client, 'post', f"{BASE}/decisions/{c4['id']}/adjustment-preview", json={
                    'expected_decision_sha256': c4['sha256'], 'target_overrides': {'DS': 6260}}).json()
                assert not boundary['after_feasible_ids']
                checks['A04'] = '偏好不补偿硬要求失败；R5动稳定度等于6260时不通过严格大于6260。'
                complete = execute(client, 'C5', evidence_view='complete_numeric_demo'); d = complete['decision']
                assert runs['C5']['decision']['diagnosis']['status'] == 'evidence_insufficient'
                assert len(d['results']) == 35 and d['diagnosis']['status'] == 'known_conflict' and len(d['diagnosis']['certificates']) == 4
                cert_checks = [verify_certificate(c, d['results'], d['pool_sha256'], d['confirmation_sha256'], d['demand']) for c in d['diagnosis']['certificates']]
                assert all(c['valid'] for c in cert_checks)
                store_record(client, output, 'C5-complete-numeric', complete)
                write_json(output/'C5-certificate-checks.json', cert_checks)
                checks['A06'] = '84条目录为证据不足；35条完整数值子池有四组范围内冲突。'
                checks['A07'] = '四组证书及删除见证校验通过；界面明确见证仅适用于剩余子集。'
                write_json(output/'C5-scope-difference.json', checked(client, 'get', '/v2/decision-diff', params={
                    'before_id': runs['C5']['decision']['id'], 'after_id': d['id']}).json())
                with Session(engine) as session:
                    dataset = latest_dataset(session); dataset.revision += 1; session.add(dataset); session.commit()
                stale = checked(client, 'post', BASE+'/drafts', 409, json={**draft_request, 'request_id': uuid4().hex})
                assert '版本' in stale.json()['detail'] or '变化' in stale.json()['detail']
                assert checked(client, 'get', f"{BASE}/records/{draft['id']}").json() == draft
                checks['A10'] = '历史草案可重读；在隔离副本上推进数据修订后拒绝新建草案。'
                checks['A11'] = '五案均有同池B1对照，数值可行集合一致；保留构造案例身份。'
                checks['A12_software'] = '案例卡、取舍与草案JSON导出等于保存记录，打印显示同一保存内容指纹；键盘与布局另见UI记录。'
        finally:
            engine.dispose()
    assert sha(source) == source_sha
    assert all(sha(ROOT/p) == h for p, h in baseline['files'].items())
    assert all(sha(ROOT/p) == h for p, h in source_hashes.items())
    write_json(output/'case-index.json', cards)
    verification = {'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'passed', 'actor': 'AI software replay',
        'source_database_unchanged': source_sha, 'protected_legacy_files_unchanged': len(baseline['files']),
        'source_files': source_hashes, 'checks': checks, 'case_cards': cards,
        'scope': 'Five constructed software cases on an isolated database, not new material measurements or human timing.'}
    write_json(output/'verification.json', verification)
    links = ''.join('<li><a href="'+c['html']+'">'+html.escape(c['case_id']+' '+c['title'])+'</a>：'+str(c['feasible'])+'项数值可行；同池B1为'+str(c['baseline_feasible'])+'项。</li>' for c in cards)
    (output/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>五案卡与软件回放</title><style>body{font:15px/1.8 "Microsoft YaHei",sans-serif;max-width:900px;margin:40px auto;padding:0 24px;color:#183b54}a{color:#007f82}li{margin:16px 0}</style><h1>五案卡与软件回放</h1><p>五个合理构造案例，同一84条AC-13目录，保留缺测。点击查看由实际保存记录生成的案例卡。</p><ol>'+links+'</ol><p><a href="C2-design-draft.html">C2设计草案</a> · <a href="C3-saved-preference.html">C3保存的取舍</a> · <a href="C4-adjusted.html">C4调整后</a> · <a href="C5-complete-numeric.html">C5完整数值子池诊断</a></p><p>计算与操作结果不表示新增材料实测或真人收益。</p></html>', encoding='utf-8')
    relative = str(output.relative_to(ROOT)).replace('\\', '/')
    write_json(ROOT/'artifacts/polish-v7/latest-replay.json', {'path': relative, 'status': 'passed', 'verification_sha256': sha(output/'verification.json')})
    print(json.dumps({'status': 'passed', 'output': relative, 'checks': len(checks), 'five_case_counts': [c['feasible'] for c in cards]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
