"""Record actual automated browser operations in one continuous video.

Optional authoring tool: Playwright 1.56.0 and its ffmpeg recording binary.
Use --browser to select an installed Chromium executable. Application runtime
does not depend on this authoring tool. The original database stays read-only.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/'artifacts/submission-v8/demo'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def srt_time(seconds):
    ms = int(seconds*1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'


def record(browser_path, port, pace=1.0):
    from playwright.sync_api import sync_playwright

    OUTPUT.mkdir(parents=True, exist_ok=True)
    work = ROOT/'tmp/submission-v8'
    work.mkdir(parents=True, exist_ok=True)
    source = ROOT/'data/workbench.sqlite'
    original_hash = digest(source)
    events, subtitles, screenshots, errors, runs = [], [], [], [], {}
    with tempfile.TemporaryDirectory(prefix='video-', dir=work, ignore_cleanup_errors=True) as temporary:
        stage = Path(temporary).resolve()
        assert stage.is_relative_to(work.resolve())
        database = stage/'demo.sqlite'
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro', uri=True)) as old, closing(sqlite3.connect(database)) as new:
            old.backup(new)
        env = dict(os.environ)
        env['PYTHONPATH'] = str(ROOT/'backend')
        env['ASPHALT_DATABASE'] = str(database)
        log = (stage/'server.log').open('w', encoding='utf-8')
        server = subprocess.Popen([sys.executable, '-X', 'utf8', '-m', 'uvicorn', 'app.main:app',
                                   '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT, env=env,
                                  stdout=log, stderr=subprocess.STDOUT,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            base = f'http://127.0.0.1:{port}'
            for _ in range(60):
                try:
                    with urllib.request.urlopen(base+'/health', timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    if server.poll() is not None:
                        raise RuntimeError('Recording server exited')
                    time.sleep(.25)
            else:
                raise RuntimeError('Recording server did not start')
            with sync_playwright() as driver:
                browser = driver.chromium.launch(executable_path=browser_path, headless=True, slow_mo=160)
                context = browser.new_context(viewport={'width':1600, 'height':1000},
                                              record_video_dir=str(stage/'recordings'),
                                              record_video_size={'width':1600, 'height':1000},
                                              locale='zh-CN', reduced_motion='reduce')
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                start = time.monotonic()

                def note(caption, seconds=7, name=None, anchor=None):
                    if anchor is not None:
                        anchor.scroll_into_view_if_needed()
                    time.sleep(.4)
                    begin = time.monotonic()-start
                    print(json.dumps({'second':round(begin,1), 'action':caption}, ensure_ascii=False), flush=True)
                    if name:
                        target = OUTPUT/(name+'.png')
                        page.screenshot(path=str(target))
                        screenshots.append({'path':target.relative_to(ROOT).as_posix(), 'sha256':digest(target),
                                            'at_seconds':round(begin,2)})
                    page.wait_for_timeout(seconds*1000*pace)
                    end = time.monotonic()-start
                    subtitles.append({'start':begin, 'end':end, 'text':caption})

                def execute(case, expected):
                    page.get_by_role('navigation', name='五个典型案例').get_by_role('button').filter(has_text=case).click()
                    with page.expect_response(lambda r: r.url.endswith(f'/cases/{case}/runs') and r.request.method == 'POST') as pending:
                        page.get_by_role('button', name='确认案例要求并选材', exact=True).click()
                    response = pending.value
                    assert response.status == 201
                    result = response.json()
                    assert len(result['decision']['results']) == 84
                    assert len(result['decision']['comparison']['feasible_ids']) == expected
                    assert result['baseline']['same_feasible_set']
                    runs[case] = {'id':result['id'], 'record_sha256':result['sha256'],
                                  'feasible':expected, 'same_feasible_set':True}
                    events.append({'case':case, 'action':'actual_browser_case_run', 'result':runs[case]})
                    return result

                page.goto(base+'/?view=design')
                page.get_by_role('heading', name='把养护需求变成可比较的材料方案').wait_for()
                note('数智选材：从养护需求出发，比较材料，再继续设计。', 8, 'overview')
                execute('C1',2)
                note('C1 高温重载：同一84条目录中，有2项数值满足构造要求。', 8, 'C1-scene',
                     page.get_by_role('heading', name='这个场景，需要什么性能'))
                page.get_by_text('为什么采用这些要求？查看出处与适用条件', exact=True).click()
                note('展开要求出处：规则、单位与适用条件随本次决策保留。', 8, 'C1-sources',
                     page.get_by_text('为什么采用这些要求？查看出处与适用条件', exact=True))

                c3=execute('C3',5)
                note('C3 水损害：五种候选均数值可行，而且全部非支配。', 8, 'C3-TSR',
                     page.get_by_role('heading',name='满足要求之后，怎样取舍'))
                with page.expect_response(lambda r: r.url.endswith('/preferences') and r.request.method=='POST'
                                          and r.request.post_data_json['priority_order'][0]=='residual') as pending:
                    page.get_by_role('button',name=re.compile('残留稳定度.*优先')).click()
                preference=pending.value.json()
                assert preference['comparison']['review_first_ids']==['mix_59cb42163ce4719d7809']
                assert set(preference['comparison']['feasible_ids'])==set(c3['decision']['comparison']['feasible_ids'])
                note('改为残留稳定度优先，首位H变K；五项可行候选保持不变。', 10, 'C3-residual',
                     page.get_by_role('heading',name='满足要求之后，怎样取舍'))
                chart=page.get_by_role('img',name=re.compile('比较，5个数值可行方案'))
                note('原始数值与要求线说明取舍，不用一个综合分数掩盖性能差异。', 8, 'C3-chart',chart)
                page.get_by_label('选择这个优先顺序的理由').fill('已满足水稳定门槛，本次优先保留残留稳定度余量。')
                page.get_by_role('button',name='保存当前取舍',exact=True).click()
                page.get_by_role('link',name='导出取舍记录').wait_for()
                note('保存工程师的取舍理由，后续交接可以回看依据。', 8, 'C3-saved',
                     page.get_by_label('选择这个优先顺序的理由'))

                execute('C2',2)
                note('C2 寒冷抗裂：两项候选应变同为2525με，继续比较其他指标。', 8, 'C2-tie',
                     page.get_by_role('heading',name='满足要求之后，怎样取舍'))
                parent=page.locator('.cw-schemes > article').filter(has_text='R4')
                parent.get_by_role('button',name='从此方案继续设计',exact=True).click()
                page.get_by_label('选择设计假设').wait_for()
                note('从准确的R4父配方继续设计，保留原寒冷场景的要求。', 8, 'C2-explorer',
                     page.get_by_role('heading',name=re.compile('从 .*R4 继续设计')))
                page.get_by_label('各组分名义份额',exact=True).check()
                page.get_by_label('选择设计假设').select_option('hyp_6e18d41dcaefa559')
                note('保持组分名义份额，比较油石比4.9%到5.0%的设计假设。', 9, 'C2-change',
                     page.get_by_label('选择设计假设'))
                page.get_by_label('这次调整想解决什么问题？').fill('保持组分名义份额，探索油石比增加0.1个百分点的设计方向；性能尚待判断。')
                with page.expect_response(lambda r:r.url.endswith('/drafts') and r.request.method=='POST') as pending:
                    page.get_by_role('button',name='保存设计草案',exact=True).click()
                draft=pending.value.json()
                assert draft['parent_recipe_id']=='mix_ec30ff644f3111c570bc'
                assert draft['measured_performance'] is None and not draft['inherits_parent_measurements']
                events.append({'action':'save_design_draft','id':draft['id'],'sha256':draft['sha256'],
                               'measured_performance':None,'parent_recipe_id':draft['parent_recipe_id']})
                note('草案保存需求、改动与意图；新配方实测保持未知。', 9, 'C2-draft',
                     page.get_by_role('heading',name='设计草案已保存'))

                execute('C4',1)
                page.get_by_text('调整场景要求，先预览再确认',exact=True).click()
                page.get_by_label('名义RAP最低比例/%').fill('75')
                page.get_by_role('button',name='预览要求变化',exact=True).click()
                page.locator('.cw-adjustment-preview').wait_for()
                note('C4 将名义RAP要求从70%提高到75%，预览数值可行1变0。', 9, 'C4-preview',
                     page.locator('.cw-adjustment-preview'))
                page.get_by_label('确认调整的理由').fill('比较更高名义RAP资源要求对历史候选的影响。')
                page.get_by_role('button',name='确认新要求并重新选材',exact=True).click()
                page.get_by_role('button',name='重新运行原案例',exact=True).wait_for()
                note('确认后另存新需求与决策，旧记录保留。名义比例不等于减碳收益。', 8, 'C4-adjusted',
                     page.get_by_role('heading',name='这个场景，需要什么性能'))

                execute('C5',0)
                diagnosis=page.get_by_role('region',name='决策诊断')
                note('C5 完整84条目录含缺测：证据不足，尚不能判定无解。', 9, 'C5-unknown',diagnosis)
                with page.expect_response(lambda r:r.url.endswith('/cases/C5/runs') and r.request.method=='POST') as pending:
                    page.get_by_role('button',name='明确切换完整数值诊断视图',exact=True).click()
                complete=pending.value.json()
                assert len(complete['decision']['results'])==35
                assert len(complete['decision']['diagnosis']['certificates'])==4
                note('明确切换35条完整数值子池，得到四组范围内冲突。', 9, 'C5-conflict',diagnosis)
                page.locator('.conflict-certificate summary').first.click()
                note('删除见证只对剩余子集成立；据此选择补资料、改要求或探索配方。', 10, 'C5-witness',
                     page.locator('.conflict-certificate').first)
                note('五案同池对照；交付包含源码、接口、保存记录与可重放证据。', 8)
                assert not errors, errors
                duration=time.monotonic()-start
                raw=page.video
                context.close()
                raw_path=raw.path()
                destination=OUTPUT/'continuous-browser.webm'
                shutil.copyfile(raw_path,destination)
                browser.close()
        finally:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(server.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill();server.wait(timeout=10)
            log.close()
    assert digest(source)==original_hash
    (OUTPUT/'operation.srt').write_text('\n\n'.join(
        f"{i}\n{srt_time(v['start'])} --> {srt_time(v['end'])}\n{v['text']}" for i,v in enumerate(subtitles,1))+'\n',encoding='utf-8')
    result={'recorded_on':'2026-10-23','created_at':datetime.now(timezone.utc).isoformat(),
            'status':'recorded','recording_pace':pace,'format':'continuous actual browser recording with automated operations, no narration',
            'viewport':{'width':1600,'height':1000},'duration_seconds_observed':round(duration,2),
            'source_database_unchanged_sha256':original_hash,'events':events,'case_runs':runs,
            'subtitles':subtitles,'screenshots':screenshots,'page_errors':errors,
            'raw_video':{'path':'artifacts/submission-v8/demo/continuous-browser.webm','sha256':digest(destination)}}
    (OUTPUT/'recording.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'status':'recorded','duration':round(duration,2)},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser',required=True)
    parser.add_argument('--port',type=int,default=8767)
    parser.add_argument('--pace',type=float,default=1.0,help='1 for final recording; smaller values only for action preflight')
    args=parser.parse_args()
    record(args.browser,args.port,args.pace)
