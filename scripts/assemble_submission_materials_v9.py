"""Assemble existing verified assets and new supplementary documents by upload purpose."""
from html import escape
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree as E
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'output/submission-v9'
EVIDENCE = ROOT/'artifacts/submission-v9'
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
GUIDE = 'https://cpipc.acge.org.cn/cw/contestNews/detail/1/2c9080189ef4ecee019f038802d55c4b?page=0'
TOPIC = 'https://cpipc.acge.org.cn/cw/contestNews/detail/1/2c9080189fb0808c019fc63d2f083049?page=0'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    assert sha(source) == sha(destination)


def form_text():
    with ZipFile(ROOT/'output/submission/项目简表.docx') as package:
        doc = E.fromstring(package.read('word/document.xml'))
    rows = doc.find('w:body/w:tbl', NS).findall('w:tr', NS)
    fields = []
    for label, row, limit in [('项目背景', 6, 300), ('立项思路', 8, 300), ('解决方案', 10, 600),
                              ('商业模式与预期效益', 12, 300)]:
        cell = rows[row].findall('w:tc', NS)[1]
        value = ''.join(cell.xpath('.//w:t/text()', namespaces=NS))
        assert len(value) <= limit
        fields.append((label, value, limit))
    lines = [
        '数智选材系统填报文案',
        '这份文案供按实际系统字段选取。字段名称和字数限制仍以报名系统为准，未填写任何个人身份信息。',
        '',
        '作品名称',
        '数智选材 道路养护材料推荐与协同设计',
        '',
        '参赛赛道与赛题',
        '企业揭榜赛道 HY-01 课题一',
        '数智选材——AI驱动的道路养护决策与沥青材料方案智能推荐系统创意方案征集',
        '',
        '关键词',
        '道路养护 场景驱动选材 多目标取舍 人机协同 可追溯决策',
        '',
        '短版简介 供较短的简介字段选择',
        '数智选材面向养护工程师，将场景要求、历史材料证据、多目标比较和配方草案连接起来。'
        '工程师可确认要求来源、比较合理候选并保留调整理由。已完成本地概念原型、三类演示规则'
        '和五个构造案例，提供源码、接口及实际操作视频。新配方实测和工程收益保持待验证。',
    ]
    for label, value, limit in fields:
        lines.extend(['', f'{label} 与正式简表一致 模板上限{limit}字 当前{len(value)}字', value])
    lines.extend([
        '', '创新机制',
        '场景规则生成有来源的要求，工程师确认后检索历史材料。硬要求先共同筛选，'
        '优先性能只重排数值可行集合。配方改动建立独立草案并保存原需求、父配方和改动理由。'
        '无结果时区分资料不足与限定完整数值子池中的要求冲突。',
        '', '当前成果与边界',
        '已完成原型、结构化数据和规则、五案对照、接口、源码及软件证据。'
        '五案使用企业历史数值及构造的场景要求。预测模型尚未形成稳定优于基准的结论，'
        '可靠自动逆向生成属于深化路线。AI操作自测不代表真人效率收益。',
        '', '提交前核对',
        '作品名称必须与报名记录一致。队伍、成员、导师、培养单位和联系方式在系统身份栏核对。'
        '简表中的身份栏暂留空；如系统明确要求实名模板，按其匿名与实名安排另行处理，'
        '不要将个人资料加入公开仓库。',
        '上传后检查预览和最终提交状态，保存回执。材料打包完成不代表比赛已提交。',
        ''
    ])
    (OUT/'系统填报文案.txt').write_text('\n'.join(lines), encoding='utf-8-sig')
    return [{'field': label, 'characters': len(value), 'template_limit': limit} for label, value, limit in fields]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {'href', 'src', 'poster'}:
                self.targets.append(value)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frozen = json.loads((ROOT/'artifacts/submission-v8/verification.json').read_text(encoding='utf-8'))
    pinned = {row['path']: row['sha256'] for row in frozen['deliverables']}
    copies = []
    for name in ['项目简表.pdf', '项目简表.docx', '项目说明书.pdf', '项目说明书.docx']:
        source = ROOT/'output/submission'/name
        assert sha(source) == pinned[source.relative_to(ROOT).as_posix()]
        dest = OUT/'01_必交文档'/name
        copy(source, dest)
        copies.append({'from': source.relative_to(ROOT).as_posix(),
                       'to': dest.relative_to(OUT).as_posix(), 'sha256': sha(dest)})
    source = ROOT/'output/submission/匿名提交包.zip'
    assert sha(source) == pinned[source.relative_to(ROOT).as_posix()]
    source_zip = OUT/'02_原型源码与证据/原型源码与证据.zip'
    copy(source, source_zip)
    copies.append({'from': source.relative_to(ROOT).as_posix(),
                   'to': source_zip.relative_to(OUT).as_posix(), 'sha256': sha(source_zip)})
    with ZipFile(source_zip) as package:
        assert package.testzip() is None
        source_entries = len(package.namelist())
    video = ROOT/'artifacts/submission-v8/demo/数智选材_五案实际操作.mp4'
    assert sha(video) == '1f4930d869fd194248cfc4f5a5f3cf36eef7a6900f46de11a33e994073628eed'
    copy(video, OUT/'03_演示视频/五案实际操作.mp4')
    copies.append({'from': video.relative_to(ROOT).as_posix(), 'to': '03_演示视频/五案实际操作.mp4', 'sha256': sha(video)})
    cases = [
        ('C1-sources.png', 'C1_场景要求与出处.png', 'C1 场景要求与原始出处'),
        ('C2-draft.png', 'C2_协同配方草案.png', 'C2 保留原需求的配方草案'),
        ('C3-chart.png', 'C3_多目标取舍.png', 'C3 五个合理候选的性能取舍'),
        ('C4-preview.png', 'C4_要求调整预览.png', 'C4 名义RAP要求变更预览'),
        ('C5-conflict.png', 'C5_范围内冲突.png', 'C5 完整数值子池内的冲突诊断'),
    ]
    for source_name, dest_name, label in cases:
        copy(ROOT/'artifacts/submission-v8/demo'/source_name, OUT/'06_案例图片'/dest_name)
    copy(ROOT/'tmp/submission-v9/business-plan-render-approved/商业计划书.pdf',
         OUT/'04_商业计划书/商业计划书.pdf')
    copy(ROOT/'docs/submission-materials-v9.md', OUT/'00_材料清单与上传说明.txt')
    counts = form_text()
    rows = [
        ('必交', '项目简表', [('PDF', '01_必交文档/项目简表.pdf'), ('DOCX', '01_必交文档/项目简表.docx')],
         '官方表格副本，身份栏留空待按系统安排核对。'),
        ('必交', '项目说明书', [('PDF', '01_必交文档/项目说明书.pdf'), ('DOCX', '01_必交文档/项目说明书.docx')],
         '7页，包含完整技术方案、机制与五案。'),
        ('软件作品必附', '原型源码与证明材料', [('ZIP', '02_原型源码与证据/原型源码与证据.zip')],
         '32.12 MB，冻结匿名版源码、运行资源、接口与证据。'),
        ('可选', '实际操作视频', [('MP4', '03_演示视频/五案实际操作.mp4')],
         '约2分48秒，实际原型连续操作，附中文字幕。'),
        ('可选', '商业计划书', [('PDF', '04_商业计划书/商业计划书.pdf'), ('DOCX', '04_商业计划书/商业计划书.docx')],
         '官方六部分模板，拟交付、收费与风险安排。'),
        ('可选', '作品演示稿', [('PPTX', '05_演示PPT/作品演示.pptx'), ('PDF', '05_演示PPT/作品演示.pdf')],
         '10页，含机制、五案界面与产品化路径。'),
    ]
    table_rows = []
    for requirement, label, files, explanation in rows:
        links = ' '.join(f'<a href="{escape(file)}">{escape(fmt)}</a>' for fmt, file in files)
        table_rows.append(f'<tr><td>{requirement}</td><th scope="row">{label}</th><td>{links}</td><td>{explanation}</td></tr>')
    images = ''.join(f'<figure><img loading="lazy" src="06_案例图片/{escape(name)}" alt="{escape(label)}">'
                     f'<figcaption>{escape(label)} · 概念原型实际界面，案例为构造</figcaption></figure>'
                     for _, name, label in cases)
    html = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>数智选材 参赛材料与上传说明</title><style>
body{margin:0;background:#f5f6f1;color:#233431;font:17px/1.75 "Microsoft YaHei",sans-serif}
main{max-width:1120px;margin:auto;padding:42px 26px 70px}h1,h2{color:#143f3b;line-height:1.4}
h1{font-size:34px;margin:8px 0 12px}h2{font-size:24px;margin-top:38px}
a{color:#087169;text-underline-offset:4px}a:focus-visible{outline:3px solid #cf7b2b;outline-offset:4px}
.lead{font-size:20px}.note{border-left:4px solid #177f76;padding:12px 20px;background:#e7efe7}
.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;background:white;min-width:750px}
td,th{border-bottom:1px solid #cbd7cf;text-align:left;padding:15px 13px;vertical-align:top}
thead{background:#143f3b;color:white}td a{display:inline-block;margin-right:12px}
video{width:100%;max-height:650px;background:#143f3b}figure{margin:25px 0;background:white;padding:14px}
img{max-width:100%;height:auto;display:block;margin:auto}figcaption{font-size:15px;color:#52645f;margin-top:8px}
.small{font-size:15px;color:#52645f}li{margin:10px 0}@media(max-width:600px){main{padding:24px 16px}h1{font-size:28px}}
</style></head><body><main>
<p class="small">企业揭榜赛道 HY-01 课题一 · 2026年10月24日整理</p>
<h1>数智选材参赛材料</h1>
<p class="lead">必交文档、软件证明和演示补充材料已按用途分类。先核对报名名称与系统字段，再逐项上传。</p>
<p class="note"><strong>官方作品截止时间为2026年10月25日中午12:00。</strong><br>
报名和培养单位资格审核已确认完成。当前尚未登录提交系统，也未取得系统提交回执。</p>
<h2 id="files">上传材料</h2><p>每份正式文档同时提供可编辑版和预览版，按上传字段支持的格式选取。公开指南未给出单文件容量和视频时长限制。</p>
<div class="table-scroll"><table><thead><tr><th>官方要求</th><th>材料</th><th>文件</th><th>用途</th></tr></thead><tbody>'''
    html += ''.join(table_rows)+'''</tbody></table></div>
<p><a href="系统填报文案.txt">打开系统填报文案</a>　<a href="00_材料清单与上传说明.txt">查看完整提交说明</a>　
<a href="材料指纹.json">查看材料清单与SHA256</a></p>
<h2>登录系统后的核对顺序</h2><ol>
<li>作品名称统一为报名记录中的名称。当前文档全名是“数智选材 道路养护材料推荐与协同设计”。</li>
<li>核对匿名安排。简表中的队伍、成员及联系方式暂留空；身份资料在系统规定位置核对，实名资料另行私下处理。</li>
<li>检查允许的格式、容量和附件数量。先满足简表、说明书和软件证明，再选择视频、商业计划书、PPT和图片。</li>
<li>源码包解压后按README启动。首次安装依赖需具备相应环境及网络或缓存，源码包含冻结运行资源和已有证据。</li>
<li>上传后逐项预览或下载复核，确认提交状态，保存回执。</li></ol>
<h2>五案实际操作视频</h2><video controls preload="metadata" src="03_演示视频/五案实际操作.mp4"></video>
<p class="small">历史性能值来自企业工作簿，场景要求和五案为构造。新配方实测、真人效率和工程收益保持待验证。</p>
<h2>五案界面图片</h2>'''+images+f'''
<h2>官方依据</h2><p><a href="{GUIDE}">大赛参赛指南及三个官方模板</a>　
<a href="{TOPIC}">企业课题一要求</a></p>
<p class="small">指南第6页规定必交材料、软件证明和匿名要求，第7页规定截止时间。企业课题一允许合理构造案例，实验室验证属于加分成果。</p>
</main></body></html>'''
    index = OUT/'00_材料清单与上传说明.html'
    index.write_text(html, encoding='utf-8')
    parser = Links()
    parser.feed(html)
    local_links = [unquote(urlsplit(u).path) for u in parser.targets if not urlsplit(u).scheme and u != '材料指纹.json']
    assert all((OUT/u).is_file() for u in local_links)
    pdf_counts = {}
    for relative, expected in [('01_必交文档/项目简表.pdf', 3), ('01_必交文档/项目说明书.pdf', 7),
                               ('04_商业计划书/商业计划书.pdf', 5), ('05_演示PPT/作品演示.pdf', 10)]:
        reader = PdfReader(OUT/relative)
        assert len(reader.pages) == expected
        pdf_counts[relative] = len(reader.pages)
    identity_markers = ['lenovo', 'wyyoh', '11374', 'c:\\users\\', 'c:/users/']
    checked_packages = []
    for relative in ['04_商业计划书/商业计划书.docx', '05_演示PPT/作品演示.pptx']:
        with ZipFile(OUT/relative) as package:
            assert package.testzip() is None
            xml = '\n'.join(package.read(n).decode('utf-8', errors='replace') for n in package.namelist()
                            if n.endswith(('.xml', '.rels'))).casefold()
            assert not any(marker in xml for marker in identity_markers)
            checked_packages.append(relative)
    for relative in ['04_商业计划书/商业计划书.pdf', '05_演示PPT/作品演示.pdf']:
        reader = PdfReader(OUT/relative)
        content = str(reader.metadata)+'\n'+'\n'.join(page.extract_text() or '' for page in reader.pages)
        assert not any(marker in content.casefold() for marker in identity_markers)
    files = [{'path': p.relative_to(OUT).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}
             for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != '材料指纹.json']
    manifest = {
        'prepared_on': '2026-10-24', 'application_version': '0.4.0',
        'status': 'materials_prepared_pending_portal_checks',
        'official_deadline': '2026-10-25T12:00:00+08:00',
        'portal_submission_performed': False, 'files': files, 'copied_frozen_assets': copies,
        'source_package_file_count': source_entries, 'summary_word_limits': counts,
        'pdf_page_counts': pdf_counts,
        'known_identity_marker_checks': {'passed': True, 'new_office_packages': checked_packages},
        'remaining_user_checks': ['registered_work_name', 'identity_fields_per_system',
                                  'accepted_formats_sizes_and_counts', 'upload_preview_and_submission_receipt'],
        'official_sources': [GUIDE, TOPIC]
    }
    reviewed = EVIDENCE/'visual-review.json'
    visual_status = 'pending'
    if reviewed.exists():
        review = json.loads(reviewed.read_text(encoding='utf-8'))
        for row in review['deliverables']:
            assert sha(ROOT/row['path']) == row['sha256']
        assert review['status'] == 'passed'
        visual_status = 'passed'
        manifest['new_document_visual_review'] = 'passed'
    write_json(OUT/'材料指纹.json', manifest)
    archive = ROOT/'output/数智选材_参赛材料.zip'
    with ZipFile(archive, 'w', ZIP_DEFLATED, compresslevel=6) as packed:
        for file in sorted(OUT.rglob('*')):
            if file.is_file():
                packed.write(file, '数智选材_参赛材料/'+file.relative_to(OUT).as_posix())
    with ZipFile(archive) as packed:
        assert packed.testzip() is None
        for row in files:
            data = packed.read('数智选材_参赛材料/'+row['path'])
            assert hashlib.sha256(data).hexdigest() == row['sha256']
        assert json.loads(packed.read('数智选材_参赛材料/材料指纹.json')) == manifest
    report = {'prepared_on': '2026-10-24', 'status': 'passed',
              'directory': OUT.relative_to(ROOT).as_posix(), 'file_count': len(files)+1,
              'archive': archive.relative_to(ROOT).as_posix(), 'archive_bytes': archive.stat().st_size,
              'archive_sha256': sha(archive), 'copied_frozen_assets_unchanged': True,
              'source_package_crc_passed': True, 'source_package_file_count': source_entries,
              'local_link_count': len(local_links)+1, 'local_links_missing': 0,
              'pdf_page_counts': pdf_counts, 'portal_submission_performed': False,
              'new_document_visual_review': visual_status,
              'software_evidence': 'Reused frozen v8; no new material test or human-efficiency claim.'}
    write_json(EVIDENCE/'materials-verification.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
