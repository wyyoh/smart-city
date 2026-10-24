"""Assemble the rewritten submission and retain frozen runtime evidence bytes."""
from html import escape
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED
from pypdf import PdfReader
from assemble_submission_materials_v9 import Links

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/submission-v10'
ART=ROOT/'artifacts/editorial-v10'
GUIDE='https://cpipc.acge.org.cn/cw/contestNews/detail/1/2c9080189ef4ecee019f038802d55c4b?page=0'
TOPIC='https://cpipc.acge.org.cn/cw/contestNews/detail/1/2c9080189fb0808c019fc63d2f083049?page=0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_json(p,value):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def copy(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(a,b);assert sha(a)==sha(b)


def field_text():
    source=json.loads((ROOT/'docs/project-summary-v10.json').read_text(encoding='utf-8'))
    text=['数智选材 系统填报文案','按系统实际字段与字数选取。四项核心段落与正式简表一致。','',
          '作品名称',source['title'],'','赛道与课题','企业揭榜赛道 HY-01课题一','',
          '关键词','道路养护 材料推荐 多目标取舍 人机协同 数据溯源','',
          '短版简介','数智选材帮助工程师确认有出处的要求，比较历史材料，并从准确父配方继续设计。系统分别记录要求变更、偏好取舍和组成改动，交付可运行原型、三类场景规则、五案、源码、接口及操作视频。作品论文展开方法、案例和计算研究。']
    counts=[]
    for label,index,limit in [('项目背景','6',300),('立项思路','8',300),('解决方案','10',600),('商业模式与预期效益','12',300)]:
        value=source['sections'][index];assert len(value)<=limit
        text+=['',f'{label}（模板上限{limit}字，当前{len(value)}字）',value]
        counts.append({'field':label,'characters':len(value),'limit':limit})
    text+=['','创新机制','要求确认后逐项检查历史候选，多项合理方案按原值和指标优先顺序比较。配方探索保留原需求、准确父配方、锁定项和设计意图。空结果依据资料状态和明确的候选范围提供核查方向。',
           '','成果组织','三类演示规则、五个构造案例和同池B1对照用于检查软件机制。50页作品论文提供数据范围、具体数值、方法与证据索引，商业计划书说明首期交付和经济核算安排。',
           '','上传核对','作品名称与报名记录统一；身份资料按系统指定位置填写；核对附件格式与容量，上传后检查预览及最终状态，保存回执。']
    (OUT/'系统填报文案.txt').write_text('\n'.join(text)+'\n',encoding='utf-8-sig')
    return counts


def source_package():
    source=ROOT/'output/submission/匿名提交包.zip'
    assert sha(source)=='8dc932e9452e4df4ccba13aba85e12573d0b362af776f62fad6c2e49ddec2eec'
    dest=OUT/'02_原型源码与证据/原型源码与证据.zip';dest.parent.mkdir(parents=True,exist_ok=True)
    entries={}
    with ZipFile(source) as old:
        original={x.filename:old.read(x.filename) for x in old.infolist() if not x.is_dir()}
    assert len(original)==656
    for name,data in original.items():entries['runtime/'+name]=data
    for relative in ['artifacts/editorial-v10/evidence.json','artifacts/submission-v8/verification.json']:
        assert 'runtime/'+relative not in entries
        entries['runtime/'+relative]=(ROOT/relative).read_bytes()
    for group in ['01_必交文档','04_商业计划书','07_作品论文']:
        for p in sorted((OUT/group).iterdir()):
            if p.suffix in ['.docx','.pdf']:entries['作品说明/'+p.name]=p.read_bytes()
    for p in sorted((ROOT/'docs/paper-v10').iterdir()):
        if p.is_file():entries['论文源稿/'+p.name]=p.read_bytes()
    readme='''数智选材 原型源码与证据

阅读顺序
作品说明：本次项目简表、说明书、商业计划书及50页作品论文。
runtime：可运行原型、企业数据、接口及冻结的计算和软件记录。
论文源稿：本次论文章节和文献表，便于文字复核与继续编辑。

启动原型
1. 进入runtime目录，阅读README.md中的环境与依赖说明。
2. 准备Python与Node.js环境，恢复冻结资源并安装依赖。
3. 在runtime目录执行：
powershell -ExecutionPolicy Bypass -File scripts/start-creative-demo.ps1
4. 按启动输出打开本地地址，进入“案例与设计”工作区。

资料定位
论文证据索引中的artifacts和docs路径，均从runtime目录查找。
五案采用企业工作簿的历史数值和构造要求，当前应用版本0.4.0。
原型与研究目录保留研发时的记录；本次申报文字以“作品说明”为阅读入口。
运行数据、案例与计算结果沿用冻结文件，顶层FILE-MANIFEST.json列出所有内容指纹。
'''
    entries['README.txt']=readme.encode('utf-8-sig')
    manifest={'created_on':'2026-10-24','application_version':'0.4.0',
              'frozen_parent_archive_sha256':sha(source),'frozen_runtime_file_count':656,
              'files':[{'path':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(entries.items())]}
    entries['FILE-MANIFEST.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    with ZipFile(dest,'w',ZIP_DEFLATED,compresslevel=6) as z:
        for n,b in sorted(entries.items()):z.writestr(n,b)
    with ZipFile(dest) as z:
        assert z.testzip() is None
        assert all(z.read('runtime/'+n)==b for n,b in original.items())
        for row in manifest['files']:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
    result={'path':dest.relative_to(ROOT).as_posix(),'sha256':sha(dest),'file_count':len(entries),
            'frozen_runtime_files_byte_identical':656,'parent_archive_sha256':sha(source)}
    write_json(ART/'source-package.json',result)
    return result


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for relative,folder in [('01_必交文档/项目简表.pdf','render-summary'),('01_必交文档/项目说明书.pdf','render-description'),
                            ('04_商业计划书/商业计划书.pdf','render-business'),('07_作品论文/作品论文.pdf','render-paper-accepted')]:
        copy(ROOT/'tmp/editorial-v10'/folder/Path(relative).name,OUT/relative)
    copy(ART/'demo/五案实际操作.mp4',OUT/'03_演示视频/五案实际操作.mp4')
    cases=[('C1-sources.png','C1_场景要求与出处.png','C1 场景要求与原始出处'),
           ('C2-draft.png','C2_协同配方草案.png','C2 保留原需求的配方草案'),
           ('C3-chart.png','C3_多目标取舍.png','C3 五个合理候选的性能取舍'),
           ('C4-preview.png','C4_要求调整预览.png','C4 名义RAP要求变更预览'),
           ('C5-conflict.png','C5_范围内冲突.png','C5 完整数值子池的冲突诊断')]
    for a,b,_ in cases:copy(ROOT/'artifacts/submission-v8/demo'/a,OUT/'06_案例图片'/b)
    copy(ROOT/'docs/submission-materials-v10.txt',OUT/'00_材料清单与上传说明.txt')
    counts=field_text();src=source_package()
    specifications=[
        ('必交','项目简表','01_必交文档/项目简表','官方模板，集中说明任务、方案和软件过程指标。',['PDF','DOCX']),
        ('必交','项目说明书','01_必交文档/项目说明书','依次说明问题、机制、实施与应用。',['PDF','DOCX']),
        ('软件作品必附','原型源码与证据','02_原型源码与证据/原型源码与证据','解压后先读README.txt，再进入runtime启动。',['ZIP']),
        ('可选','五案实际操作','03_演示视频/五案实际操作','约2分48秒，连续原型操作与中文字幕。',['MP4']),
        ('可选','商业计划书','04_商业计划书/商业计划书','按官方六部分模板说明服务与经济核算。',['PDF','DOCX']),
        ('可选','作品演示稿','05_演示PPT/作品演示','10页，介绍机制、五案和产品化步骤。',['PPTX','PDF']),
        ('技术补充','作品论文','07_作品论文/作品论文','50页，展开数据、方法、五案及计算研究。',['PDF','DOCX'])]
    rows=[]
    for need,label,stem,note,formats in specifications:
        links=' '.join(f'<a href="{escape(stem)}.{fmt.lower()}">{fmt}</a>' for fmt in formats)
        rows.append(f'<tr><td>{need}</td><th scope="row">{label}</th><td>{links}</td><td>{note}</td></tr>')
    images=''.join(f'<figure><img loading="lazy" src="06_案例图片/{name}" alt="{label}"><figcaption>{label}</figcaption></figure>' for _,name,label in cases)
    html='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>数智选材 参赛材料</title><style>
body{margin:0;background:#f5f6f1;color:#233431;font:17px/1.75 "Microsoft YaHei",sans-serif}main{max-width:1120px;margin:auto;padding:42px 26px 70px}h1,h2{color:#143f3b;line-height:1.4}h1{font-size:34px}h2{font-size:24px;margin-top:38px}a{color:#087169;text-underline-offset:4px}a:focus-visible{outline:3px solid #cf7b2b;outline-offset:4px}.lead{font-size:20px}.note{border-left:4px solid #177f76;padding:12px 20px;background:#e7efe7}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;background:white;min-width:740px}td,th{border-bottom:1px solid #cbd7cf;text-align:left;padding:15px 13px;vertical-align:top}thead{background:#143f3b;color:white}td a{display:inline-block;margin-right:12px}video{width:100%;max-height:650px;background:#143f3b}figure{margin:25px 0;background:white;padding:14px}img{max-width:100%;height:auto;display:block;margin:auto}figcaption,.small{font-size:15px;color:#52645f}li{margin:10px 0}@media(max-width:600px){main{padding:24px 16px}h1{font-size:28px}}
</style></head><body><main><p class="small">企业揭榜赛道 HY-01 课题一 · 2026年10月24日整理</p>
<h1>数智选材参赛材料</h1><p class="lead">先用简表和五案演示了解作品，再按需要查阅完整论文与可运行原型。</p>
<p class="note"><strong>作品论文已整理为50页。</strong>本次重写按工程师的选材、比较和调整过程展开，数据与方法在相应章节说明。<br>官方作品截止时间：2026年10月25日中午12:00。报名与资格审核已完成，系统上传及回执由参赛者办理。</p>
<h2>按用途选择材料</h2><p>正式文档提供可编辑版和预览版；按系统实际字段选择格式与附件。</p><div class="scroll"><table><thead><tr><th>要求</th><th>材料</th><th>文件</th><th>用途</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div>
<p><a href="系统填报文案.txt">系统填报文案</a>　<a href="00_材料清单与上传说明.txt">完整上传说明</a>　<a href="材料指纹.json">文件清单与SHA256</a></p>
<h2>阅读与上传顺序</h2><ol><li>简表、演示稿和操作视频用于快速了解；说明书与论文用于技术阅读。</li><li>论文第4至9章解释核心机制和五案，第3章与第10章说明数据及计算研究；附录列出接口与证据位置。</li><li>作品名称与报名记录统一，身份资料填写在系统指定位置，匿名文档的身份栏留空。</li><li>登录后核对格式、容量与附件数量，先上传简表、说明书和软件证明，再安排演示与技术附件。</li><li>逐项预览或下载检查，确认最终提交状态并保存回执。</li></ol>
<h2>五案连续操作</h2><video controls preload="metadata" src="03_演示视频/五案实际操作.mp4"></video>
<p class="small">五案采用企业工作簿的历史性能值和构造要求，记录需求确认、候选取舍、配方探索与范围诊断。</p>
<h2>案例界面</h2>'''+images+f'''<h2>官方依据</h2><p><a href="{GUIDE}">参赛指南与官方模板</a>　<a href="{TOPIC}">企业课题一要求</a></p></main></body></html>'''
    index=OUT/'00_材料清单与上传说明.html';index.write_text(html,encoding='utf-8')
    parser=Links();parser.feed(html)
    local=[u for u in parser.targets if not u.startswith(('http:','https:')) and u!='材料指纹.json']
    assert all((OUT/u).is_file() for u in local)
    pages={}
    for p in sorted(OUT.rglob('*.pdf')):pages[p.relative_to(OUT).as_posix()]=len(PdfReader(p).pages)
    assert pages['07_作品论文/作品论文.pdf']==50 and pages['05_演示PPT/作品演示.pdf']==10
    markers=['lenovo','wyyoh','11374','c:\\users\\','c:/users/']
    for p in sorted(OUT.rglob('*')):
        if p.suffix in ['.docx','.pptx']:
            with ZipFile(p) as z:
                assert z.testzip() is None
                value='\n'.join(z.read(n).decode('utf-8',errors='replace') for n in z.namelist() if n.endswith(('.xml','.rels')))
        elif p.suffix=='.pdf':
            r=PdfReader(p);value=str(r.metadata)+'\n'+'\n'.join(x.extract_text() or '' for x in r.pages)
        else:continue
        assert not any(s in value.casefold() for s in markers),p
    files=[{'path':p.relative_to(OUT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='材料指纹.json']
    manifest={'prepared_on':'2026-10-24','edition':'v10_editorial','application_version':'0.4.0','files':files,
              'pdf_page_counts':pages,'summary_word_limits':counts,'source_package':src,
              'portal_submission_performed':False,'official_deadline':'2026-10-25T12:00:00+08:00',
              'official_sources':[GUIDE,TOPIC],'identity_marker_checks':'passed'}
    review=ART/'visual-review.json'
    if review.exists():
        d=json.loads(review.read_text(encoding='utf-8'));assert d['status']=='passed'
        for row in d['deliverables']:assert sha(ROOT/row['path'])==row['sha256']
        manifest['visual_review']='passed'
    write_json(OUT/'材料指纹.json',manifest)
    archive=ROOT/'output/数智选材_参赛材料_v10.zip'
    with ZipFile(archive,'w',ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file():z.write(p,'数智选材_参赛材料/'+p.relative_to(OUT).as_posix())
    with ZipFile(archive) as z:
        assert z.testzip() is None
        for row in files:assert hashlib.sha256(z.read('数智选材_参赛材料/'+row['path'])).hexdigest()==row['sha256']
    result={'status':'passed','file_count':len(files)+1,'archive':archive.relative_to(ROOT).as_posix(),
            'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive),'pdf_page_counts':pages,
            'frozen_runtime_files_byte_identical':656,'local_links_checked':len(local)+1,
            'known_identity_marker_checks':'passed','portal_submission_performed':False,
            'visual_review':manifest.get('visual_review','pending')}
    write_json(ART/'materials-verification.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
