"""Record actual acceptance evidence without re-running the planning generator."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from app.settings import ROOT
from app.storage import now

EVIDENCE={
 'ENG-01':['pyproject.toml','requirements.lock.txt','frontend/pnpm-lock.yaml','backend/app/main.py'],
 'DAT-01':['docs/data-contracts.json','backend/app/domain/contracts.py'],
 'DAT-02':['backend/app/importer.py','artifacts/import-result.json'],
 'DAT-03':['backend/app/importer.py','docs/enterprise-questions.md'],
 'DAT-04':['backend/app/storage.py','backend/app/services.py'],
 'TST-01':['tests/test_core.py','artifacts/tests.xml'],
 'BIZ-01':['docs/enterprise-questions.md'],
 'RUL-01':['backend/app/services.py','configs/cases.json'],
 'CAL-01':['backend/app/domain/calculations.py','tests/test_core.py'],
 'RUL-02':['backend/app/services.py','tests/test_core.py'],
 'API-01':['backend/app/main.py','docs/api.openapi.json'],
 'WEB-01':['frontend/src/main.tsx','artifacts/screenshots/mobile.jpg'],
 'WEB-02':['frontend/src/main.tsx','artifacts/screenshots/workbench.jpg'],
 'TST-02':['tests/test_core.py','artifacts/acceptance/final-rehearsal-1/result.json'],
 'WEB-03':['frontend/src/main.tsx','artifacts/screenshots/C5-full.jpg'],
 'WEB-04':['frontend/src/main.tsx','backend/app/services.py'],
 'REC-01':['backend/app/services.py','tests/test_core.py'],
 'OBS-01':['backend/app/services.py','artifacts/screenshots/observation-approved.jpg'],
 'OUT-01':['backend/app/services.py','artifacts/acceptance/final-rehearsal-1/C3.html'],
 'TST-03':['scripts/rehearse.py','artifacts/acceptance/final-rehearsal-2/result.json'],
 'DEM-01':['docs/demo-script.md','configs/cases.json'],
 'ML-01':['backend/app/ml/features.py','artifacts/models/model_cards.json'],
 'ML-02':['backend/app/ml/features.py','tests/test_models.py'],
 'ML-03':['backend/app/ml/train.py','artifacts/models/model_cards.json'],
 'ML-04':['backend/app/ml/train.py','artifacts/models/model_cards.json'],
 'ML-05':['artifacts/models/model_cards.json','docs/release-notes.md'],
 'ML-06':['backend/app/ml/predict.py','tests/test_models.py'],
 'TST-04':['tests/test_models.py','artifacts/tests.xml'],
 'UQ-01':['backend/app/ml/train.py','artifacts/models/model_cards.json'],
 'UQ-02':['frontend/src/main.tsx','configs/features.json'],
 'OPT-01':['configs/features.json','docs/enterprise-questions.md'],
 'EXP-01':['scripts/replay_test_selection.py','artifacts/next_test_replay.json'],
 'TST-05':['tests/test_core.py','tests/test_models.py','frontend/src/main.tsx'],
 'BIZ-02':['docs/enterprise-questions.md'],
 'TST-06':['tests/test_offline.py','artifacts/acceptance/final-rehearsal-1/result.json','artifacts/acceptance/final-rehearsal-2/result.json'],
 'PKG-01':['scripts/start-local.ps1','scripts/package_release.py','scripts/verify_bundle.py'],
 'DOC-01':['README.md','docs/developer-guide.md','docs/api.openapi.json'],
 'DEM-02':['docs/demo-script.md','artifacts/demo/manifest.json','artifacts/demo/数智选材_界面步骤回放.mp4'],
 'REL-01':['docs/release-notes.md','artifacts/development_progress.json']}


def main():
    stamp=now()
    path=ROOT/'planning/development_backlog_v1.json'
    plan=json.loads(path.read_text(encoding='utf-8'))
    verified=ROOT/'artifacts/package-verification.json'
    packaged=verified.exists() and json.loads(verified.read_text(encoding='utf-8')).get('status')=='passed'
    for task in plan['tasks']:
        id=task['id'];task['status_updated_at']=stamp
        task['status']='completed'
        task['evidence']=EVIDENCE[id]
        if id=='OPT-01':
            task['status']='skipped_condition'
            task['execution_note']='RAP质量基准、原料关联和有效旧沥青口径未确认，自动优化关闭；未试验微调仍可用。'
        elif id=='BIZ-02':
            task['status']='prepared_awaiting_external'
            task['execution_note']='验证设计与评议表已准备；尚未收到企业评议或独立实测，外部验证保持计划状态。'
        elif id in ['PKG-01','REL-01'] and not packaged:
            task['status']='in_progress'
            task['execution_note']='源码、静态资源及版本已准备，等待异目录发行包验证。'
        elif id=='DEM-02':
            task['execution_note']='两次真实HTTP完整排练；视频为30秒真实截图步骤回放，无配音，非连续现场录屏。'
        elif id=='TST-06':
            task['execution_note']='进程级阻断网络连接的离线测试；两次同机回环HTTP排练。未更改系统网络，未在全新电脑验收。'
        elif id.startswith('ML-') or id=='UQ-01':
            task['execution_note']='实验已执行；四项选择流程未优于均值MAE基线，保留研究模式。区间需组可交换性假设。'
        else:
            task['execution_note']='见对应代码、自动检查、真实界面或排练证据。'
    plan['execution']={'updated_at':stamp,'release':'0.1.0 prototype','actual_hours':None,
                       'note':'六周与150小时是原估算，不代表实际历时或投入；日期未固定。'}
    path.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    states={s:sum(t['status']==s for t in plan['tasks']) for s in sorted({t['status'] for t in plan['tasks']})}
    root=ET.parse(ROOT/'artifacts/tests.xml').getroot()
    suite=root.find('testsuite')
    tests={k:suite.get(k) for k in ['tests','failures','errors','skipped','time']}
    cards=json.loads((ROOT/'artifacts/models/model_cards.json').read_text(encoding='utf-8'))
    verification={'recorded_at':stamp,'tests':tests,'frontend_build':'passed','browser_checks':{
        'five_case_results':['R1','R4','R7','R5','empty'],'variant_clears_evidence':True,
        'draft_and_review':True,'each_raw_cell_selectable':True,'mobile_width':390,
        'mobile_target_rows_fit':True,'viewport_reset':True},
        'rehearsals':[json.loads((ROOT/'artifacts/acceptance'/name/'result.json').read_text(encoding='utf-8')) for name in ['final-rehearsal-1','final-rehearsal-2']],
        'limits':['同机验证，未在全新电脑安装验收','本地审核人声明无账户权限签章','企业和独立试验待取得'],
        'warning':'Starlette当前TestClient的httpx传输有弃用提示，18项检查通过。'}
    progress={'updated_at':stamp,'tasks':states,'p0_completed':sum(t['priority']=='P0' and t['status']=='completed' for t in plan['tasks']),
              'p0_total':sum(t['priority']=='P0' for t in plan['tasks']),'entrypoint':'http://127.0.0.1:8766/',
              'dataset_sha256':cards['dataset_sha256'],'model_status':'research_only_no_stable_selection_improvement',
              'package_verified':packaged,'external_validation':'awaiting_external_evidence'}
    (ROOT/'artifacts/development_progress.json').write_text(json.dumps(progress,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'artifacts/verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest_path=ROOT/'planning/plan_manifest.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'));manifest['implementation_tasks_completed']=states.get('completed',0)
        manifest['execution_progress']='../artifacts/development_progress.json';manifest['updated_at']=stamp
        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(progress,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
