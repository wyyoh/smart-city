"""Create a separate anonymous derivative, keeping original repository evidence intact.

Only account/workstation metadata and file-reference digests are transformed.
Original material databases and current application source are preserved. Old
v0.2/v0.3 ZIP releases are omitted from the derivative runtime archive; current
runtime assets and historical evidence documents are retained. The extracted
final package must pass the creative workflow smoke check before publication.
"""
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

from verify_submission_checkout_v8 import check

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'output/submission/匿名提交包.zip'
META=ROOT/'artifacts/submission-v8'
TEXT={'.json','.xml','.md','.txt','.py','.ps1','.html','.yml','.yaml','.ts','.tsx','.css','.srt','.ass','.toml'}
HEX=re.compile(rb'(?<![a-f0-9])[a-f0-9]{64}(?![a-f0-9])')
MARKERS={b'wyyoh':b'ANONYMOUS_ACCOUNT',b'Lenovo':b'LOCAL_USER',b'LAPTOP-IORJGR2A':b'LOCAL_MACHINE'}


def sha(data):return hashlib.sha256(data).hexdigest()


def json_bytes(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')


def redact(data):
    # Both ordinary and JSON-escaped Windows separators are accepted.
    data=re.sub(rb'[A-Za-z]:[/\\]+Users[/\\]+[^/\\\r\n"<>]+',b'/local',data,flags=re.I)
    for old,new in MARKERS.items():data=re.sub(re.escape(old),new,data,flags=re.I)
    return data


def included(name):
    excluded=['output/','artifacts/github-publish/','artifacts/demo/','artifacts/submission-v8/official/']
    if any(name.startswith(p) for p in excluded):return False
    if name in {'README.md','docs/github-handoff.md','scripts/build_anonymous_submission_v8.py'}:return False
    if name in {'planning/submission_finish_v8.json','artifacts/submission-v8/demo/continuous-browser.webm'}:return False
    if name.startswith('scripts/') and any(x in name for x in ['submission_documents','render_submission_docx','record_submission_demo','encode_submission_demo']):return False
    if name in {'artifacts/submission-v8/anonymous-package.json','artifacts/submission-v8/anonymous-checkout.json','artifacts/submission-v8/completion.json'}:return False
    return True


def scan(data,name,findings):
    for marker in list(MARKERS)+[b'C:\\Users\\',b'C:/Users/']:
        if marker.lower() in data.lower():findings.append({'path':name,'kind':'workstation_or_account_marker'})
    suffix=Path(name).suffix.lower()
    if suffix in {'.zip','.docx','.xlsx'}:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in archive.namelist():
                if not member.endswith('/'):scan(archive.read(member),name+'!'+member,findings)
    elif suffix=='.gz':scan(gzip.decompress(data),name[:-3],findings)


def rebase(nodes,original):
    # Dependencies form file-reference chains. Preserve every previous digest
    # alias until all references converge; data snapshots themselves are intact.
    history={n:{sha(original[n])} for n in nodes if n in original}
    for iteration in range(30):
        mapping={}
        for name,values in history.items():
            current=sha(nodes[name]).encode()
            for value in values:mapping[value.encode()]=current
        changed=False
        for name,data in list(nodes.items()):
            if Path(name).suffix.lower() not in TEXT:continue
            updated=HEX.sub(lambda m:mapping.get(m.group(),m.group()),data)
            if name.endswith('.json'):
                value=json.loads(updated)
                size_changed=False
                def sizes(obj):
                    nonlocal size_changed
                    if isinstance(obj,dict):
                        path=obj.get('path')
                        if isinstance(path,str) and path in nodes and 'bytes' in obj:
                            expected=len(nodes[path])
                            if obj['bytes']!=expected:obj['bytes']=expected;size_changed=True
                        for child in obj.values():sizes(child)
                    elif isinstance(obj,list):
                        for child in obj:sizes(child)
                sizes(value)
                if size_changed:updated=json_bytes(value)
            if updated!=data:
                history.setdefault(name,set()).add(sha(data))
                nodes[name]=updated
                changed=True
        if not changed:return iteration
    raise RuntimeError('Anonymous evidence reference digests did not converge')


def write_archive(nodes):
    manifest={'schema_version':1,'scope':'anonymous derivative, source data retained',
              'files':[{'path':n,'bytes':len(v),'sha256':sha(v)} for n,v in sorted(nodes.items())]}
    payload=dict(nodes);payload['FILE-MANIFEST.json']=json_bytes(manifest)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(OUTPUT,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name,data in sorted(payload.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,10,23,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,data)
    with zipfile.ZipFile(OUTPUT) as archive:
        assert set(archive.namelist())==set(payload)
        assert all(sha(archive.read(e['path']))==e['sha256'] and len(archive.read(e['path']))==e['bytes'] for e in manifest['files'])
    return manifest


def main():
    paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode('utf-8').split('\0')
    names=sorted({n for n in paths if n and included(n) and (ROOT/n).is_file()})
    original={n:(ROOT/n).read_bytes() for n in names}
    nodes={n:redact(v) if Path(n).suffix.lower() in TEXT else v for n,v in original.items()}
    assert not any(n.startswith('.git/') or n.endswith('.env') for n in nodes)
    # The supplied workbook contains an inherited absolute Excel save path.
    # Provide a viewing derivative with only that metadata removed. Retain the
    # frozen imported database and its original source identity; do not silently
    # import a metadata-only derivative as a new experimental dataset.
    workbook='再生沥青混合料实验数据表.xlsx'
    view='data/材料数据查看.xlsx'
    raw_workbook=nodes.pop(workbook)
    viewed=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw_workbook)) as old,zipfile.ZipFile(viewed,'w',zipfile.ZIP_DEFLATED) as new:
        for info in old.infolist():
            data=old.read(info.filename)
            if info.filename=='xl/workbook.xml':data=re.sub(rb'<x15ac:absPath\b[^>]*/>',b'',data)
            new.writestr(info,data)
    nodes[view]=viewed.getvalue()
    with zipfile.ZipFile(io.BytesIO(raw_workbook)) as old,zipfile.ZipFile(io.BytesIO(nodes[view])) as new:
        assert old.namelist()==new.namelist()
        assert all(old.read(n)==new.read(n) for n in old.namelist() if n!='xl/workbook.xml')
    baseline_name='artifacts/review-phase/baseline.json'
    baseline=json.loads(nodes[baseline_name]);baseline['files'].pop(workbook,None);baseline['files'][view]=sha(nodes[view])
    nodes[baseline_name]=json_bytes(baseline)
    registry_name='configs/review_evidence_v3.json'
    registry=json.loads(nodes[registry_name])
    for entry in registry['evidence'].values():
        if entry.get('path')==workbook:entry.update(path=view,sha256=sha(nodes[view]))
    nodes[registry_name]=json_bytes(registry)
    for launcher in ['scripts/setup.ps1','scripts/start-local.ps1']:
        text=nodes[launcher].decode('utf-8')
        text=re.sub(r'^& .* -m app\.importer .*\r?\nif\(\$LASTEXITCODE -ne 0\)\{throw \'Workbook import failed\.\'\}',
                    "if(-not(Test-Path -LiteralPath (Join-Path $ProjectRoot 'data/workbench.sqlite'))){throw 'Restore the published database first.'}\nWrite-Host 'Anonymous demo uses the frozen imported database; viewing workbook is metadata-cleaned.'",
                    text,flags=re.M)
        assert '-m app.importer' not in text
        nodes[launcher]=text.encode('utf-8')
    # Remove duplicated historical release ZIPs, whose metadata belongs to the
    # original development handoff. Current source, evidence and runtime remain.
    runtime='artifacts/distribution/runtime-assets.zip'
    reduced=io.BytesIO();omitted=[]
    with zipfile.ZipFile(io.BytesIO(nodes[runtime])) as old,zipfile.ZipFile(reduced,'w',zipfile.ZIP_DEFLATED) as new:
        for info in old.infolist():
            if info.filename.startswith('artifacts/release/'):
                omitted.append(info.filename)
            else:new.writestr(info,old.read(info.filename))
    nodes[runtime]=reduced.getvalue()
    manifest_name='artifacts/distribution/runtime-assets.json'
    runtime_manifest=json.loads(nodes[manifest_name])
    runtime_manifest['files']=[v for v in runtime_manifest['files'] if v['path'] not in omitted]
    runtime_manifest['archive'].update(bytes=len(nodes[runtime]),sha256=sha(nodes[runtime]))
    runtime_manifest['scope']='Current runtime, frozen research input, research-only models and current frontend; historical ZIP releases omitted for anonymous submission.'
    nodes[manifest_name]=json_bytes(runtime_manifest)
    for name in ['项目说明书.pdf','项目说明书.docx','项目简表.pdf','项目简表.docx']:
        nodes['output/submission/'+name]=(ROOT/'output/submission'/name).read_bytes()
    readme='''# 数智选材匿名提交版

本包提供项目简表与说明书、原型源代码、运行资源、五案证据和实际操作视频。
首先查看 output/submission/ 下两份PDF或DOCX。三类场景、五个构造案例，核心数值来自企业工作簿。

## 启动

准备 Python 3.12以上、Node.js 24、pnpm 11，在本目录的PowerShell运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1 -Python python
powershell -ExecutionPolicy Bypass -File scripts/start-creative-demo.ps1
```

打开 http://127.0.0.1:8766/?view=design 。已有依赖时也可先运行恢复脚本再启动。
安装依赖需要网络，核心操作在安装后本地运行。默认根路径保留历史成果入口。
按C1、C3、C2、C4、C5演示；细节见 docs/creative-demo-v7.md 。
视频位于 artifacts/submission-v8/demo/ ，为当前应用自动化操作的连续录屏，有字幕、无配音。
本包附MP4、字幕及操作记录；录屏原始WebM另存完整研发交接资料。

## 数据与匿名副本

材料数据库、当前前端和核心算法保持原样。工作簿查看副本为 data/材料数据查看.xlsx ，只移除Excel继承的绝对保存路径，所有工作表、数值、公式及其他包部件逐字节保持。软件使用冻结导入库及其原始数据身份；匿名版启动脚本不再次导入查看副本。
文本只替换账号、本机用户名、路径和主机名等元数据，并重算对应文件摘要；变化清单见 ANONYMIZATION.json 。
旧v0.2和v0.3发布ZIP不重复附带；当前源码、运行资源及历史证据文档均保留。原始研发证据另行完整保存。
模型预测为研究参考，新配方是未试验假设，当前不申报材料性能或实际行业收益提升。重新开展原始研究训练需使用完整研发资料，本包验证当前选材、比较、草案及已有研究资料查看。
第三方依赖与企业资料保留原来源；研发使用AI辅助，最终内容由参赛者复核。
简表身份栏按匿名评审要求留空。报名系统登记信息及实际上传要求由参赛者核对。
'''
    nodes['README.md']=readme.encode('utf-8')
    index_name='artifacts/submission-v8/index.html'
    if index_name in nodes:
        index=nodes[index_name].decode('utf-8').replace('../../output/submission/匿名提交包.zip','../../FILE-MANIFEST.json')
        index=index.replace('下载匿名提交包','查看包内清单').replace('href="anonymous-package.json"','href="../../ANONYMIZATION.json"')
        nodes[index_name]=index.encode('utf-8')
    registry=json.loads(nodes[registry_name])
    for entry in registry['evidence'].values():
        if entry.get('path')=='README.md':entry['sha256']=sha(nodes['README.md'])
    nodes[registry_name]=json_bytes(registry)
    iterations=rebase(nodes,original)
    findings=[]
    for name,data in nodes.items():scan(data,name,findings)
    if findings:raise RuntimeError('Identity markers remain: '+json.dumps(findings,ensure_ascii=False))
    transformations=[{'path':n,'original_sha256':sha(original[n]),'anonymous_sha256':sha(v)}
                     for n,v in sorted(nodes.items()) if n in original and v!=original[n]]
    nodes['ANONYMIZATION.json']=json_bytes({'scope':'Account and workstation metadata substitutions and reference digest updates only; original repository files remain intact.',
        'changes':transformations,'omitted_duplicate_historical_archives':omitted,'reference_rebase_iterations':iterations,
        'material_database_changed':False,'application_version':'0.4.0','identity_marker_scan':'passed',
        'workbook_view':{'path':view,'original_sha256':sha(raw_workbook),'view_sha256':sha(nodes[view]),
                         'only_changed_package_part':'xl/workbook.xml absolute-save-path element',
                         'worksheets_formulas_and_other_parts_byte_identical':True},
        'launcher_policy':'Use frozen imported database; do not import metadata-cleaned viewing workbook.'})
    manifest=write_archive(nodes)
    work=ROOT/'tmp/submission-v8'
    work.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='anonymous-check-',dir=work) as temporary:
        directory=Path(temporary).resolve()
        assert directory.is_relative_to(work.resolve())
        with zipfile.ZipFile(OUTPUT) as archive:
            for name in archive.namelist():
                target=(directory/name).resolve()
                assert target.is_relative_to(directory)
            archive.extractall(directory)
        result=check(directory)
    result.update(status='passed',created_on='2026-10-23',scope='Extracted anonymous package, prepared Python dependencies on current host; current workflows and reference integrity checked.')
    receipt=json_bytes(result)
    (META/'anonymous-checkout.json').write_bytes(receipt)
    nodes['artifacts/submission-v8/anonymous-checkout.json']=receipt
    manifest=write_archive(nodes)
    result={'status':'passed','created_on':'2026-10-23','archive':{'path':OUTPUT.relative_to(ROOT).as_posix(),
        'bytes':OUTPUT.stat().st_size,'sha256':sha(OUTPUT.read_bytes())},'files':len(manifest['files']),
        'identity_scan':'known account, user-path and hostname markers, including nested zip/docx/xlsx/gzip payloads; no matches',
        'transformed_files':len(transformations),'reference_rebase_iterations':iterations,
        'application_source_unchanged':all(nodes[n]==original[n] for n in original if n.startswith(('backend/','frontend/src/'))),
        'current_core_application':result['core_application'],'portal_submission_performed':False}
    (META/'anonymous-package.json').write_bytes(json_bytes(result))
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
