"""Fill copies of official DOCX templates without rebuilding opaque package parts."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zipfile

from lxml import etree as E

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT/'artifacts/submission-v8/official'
OUTPUT = ROOT/'output/submission'
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W = '{'+NS['w']+'}'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def paragraph_text(paragraph):
    return ''.join(paragraph.xpath('.//w:t/text()', namespaces=NS))


def replace_paragraph(paragraph, text, bold=None):
    sample = paragraph.find('w:r', NS)
    properties = deepcopy(sample.find('w:rPr', NS)) if sample is not None else None
    for child in list(paragraph):
        if child.tag != W+'pPr':
            paragraph.remove(child)
    run = E.SubElement(paragraph, W+'r')
    if properties is not None:
        run.append(properties)
    if properties is None:
        properties = E.SubElement(run, W+'rPr')
    for color in properties.findall('w:color', NS):
        properties.remove(color)
    E.SubElement(properties, W+'color', {W+'val': '000000'})
    if bold is not None:
        properties = run.find('w:rPr', NS)
        if properties is None:
            properties = E.SubElement(run, W+'rPr')
        for old in properties.findall('w:b', NS):
            properties.remove(old)
        if bold:
            E.SubElement(properties, W+'b')
    value = E.SubElement(run, W+'t')
    value.text = text
    value.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')


def fill_cell(cell, text):
    paragraphs = cell.findall('w:p', NS)
    if not paragraphs:
        paragraphs = [E.SubElement(cell, W+'p')]
    sample = deepcopy(paragraphs[0])
    for paragraph in paragraphs:
        cell.remove(paragraph)
    for line in text.split('\n'):
        new = deepcopy(sample)
        replace_paragraph(new, line)
        cell.append(new)


def write_package(template, output, document):
    before = {}
    edited = {'word/document.xml', 'docProps/core.xml'}
    with zipfile.ZipFile(template) as source, zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            before[info.filename] = sha(data)
            if info.filename == 'word/document.xml':
                data = E.tostring(document, encoding='UTF-8', xml_declaration=True, standalone=True)
            elif info.filename == 'docProps/core.xml':
                core = E.fromstring(data)
                for node in core:
                    if E.QName(node).localname in {'creator', 'lastModifiedBy', 'description', 'keywords', 'title'}:
                        node.text = ''
                data = E.tostring(core, encoding='UTF-8', xml_declaration=True, standalone=True)
            target.writestr(info, data)
    with zipfile.ZipFile(output) as saved:
        after = {name: sha(saved.read(name)) for name in saved.namelist()}
    assert before.keys() == after.keys()
    assert all(after[n] == digest for n, digest in before.items() if n not in edited)
    return {'template': template.relative_to(ROOT).as_posix(), 'template_sha256': sha(template.read_bytes()),
            'output': output.relative_to(ROOT).as_posix(), 'output_sha256': sha(output.read_bytes()),
            'preserved_package_parts': len(before)-len(edited), 'edited_parts': sorted(edited)}


def description():
    template = OFFICIAL/'project-description.docx'
    with zipfile.ZipFile(template) as package:
        document = E.fromstring(package.read('word/document.xml'))
    body = document.find('w:body', NS)
    paragraphs = body.findall('w:p', NS)
    section = body.find('w:sectPr', NS)
    heading_sources = [paragraphs[i] for i in [5, 7, 11, 13]]
    body_source = paragraphs[6]
    sub_source = paragraphs[8]
    for element in list(body):
        body.remove(element)
    for paragraph in paragraphs[:3]:
        body.append(deepcopy(paragraph))
    title = deepcopy(paragraphs[3])
    replace_paragraph(title, '数智选材 道路养护材料推荐与协同设计', bold=True)
    body.append(title)
    content = (ROOT/'docs/submission-final-v8.md').read_text(encoding='utf-8')
    sections = re.split(r'^## ', content, flags=re.M)[1:]
    counts = []
    for index, text in enumerate(sections):
        _, payload = text.split('\n', 1)
        count = len(re.sub(r'\s', '', text))
        limit = [2000, 3000, 3000, 500][index]
        assert count <= limit
        counts.append({'section': index+1, 'count_including_headings_and_punctuation': count, 'limit': limit})
        heading = deepcopy(heading_sources[index])
        props = heading.find('w:pPr', NS)
        E.SubElement(props, W+'keepNext')
        body.append(heading)
        for block in payload.strip().split('\n\n'):
            is_sub = block.startswith('### ')
            paragraph = deepcopy(sub_source if is_sub else body_source)
            replace_paragraph(paragraph, block[4:] if is_sub else block, bold=is_sub)
            props = paragraph.find('w:pPr', NS)
            if is_sub:
                E.SubElement(props, W+'keepNext')
            body.append(paragraph)
    body.append(section)
    output = OUTPUT/'项目说明书.docx'
    return write_package(template, output, document), counts


def summary():
    template = OFFICIAL/'project-summary.docx'
    with zipfile.ZipFile(template) as package:
        document = E.fromstring(package.read('word/document.xml'))
    body = document.find('w:body', NS)
    paragraphs = body.findall('w:p', NS)
    replace_paragraph(paragraphs[3], '数智选材', bold=True)
    # Remove the empty trailing paragraph responsible for a blank template page.
    for paragraph in body.findall('w:p', NS)[4:]:
        if not paragraph_text(paragraph).strip():
            body.remove(paragraph)
    rows = body.find('w:tbl', NS).findall('w:tr', NS)
    for row_number in [5, 7, 9, 11]:
        for paragraph in rows[row_number].findall('.//w:tc/w:p', NS):
            props = paragraph.find('w:pPr', NS)
            if props is None:
                props = E.SubElement(paragraph, W+'pPr')
            E.SubElement(props, W+'keepNext')
    cell = lambda r, i: rows[r].findall('w:tc', NS)[i]
    fill_cell(cell(0, 1), '数智选材 道路养护材料推荐与协同设计')
    # Team and contact fields intentionally remain blank for anonymous review.
    for paragraph in cell(2, 1).findall('w:p', NS):
        if '13.企业揭榜赛道' in paragraph_text(paragraph):
            replace_paragraph(paragraph, '13.企业揭榜赛道（已选择，HY-01课题一）')
    values = {
        6: '道路养护选材需要同时满足高温、低温与水稳定等要求。现有试验资料分散，缺测和条件差异使查表结果难以直接用于项目；多种候选同时合理时，工程师还需解释取舍并继续调整。数智选材面向养护工程师和材料研发人员，将场景要求、历史材料证据、多方案比较与配方探索连接为可追溯的决策过程。',
        8: '项目基于企业再生沥青混合料工作簿及可运行软件，围绕场景需求解释、硬要求与偏好分离、保持原需求的协同设计展开。无结果时区分资料不足和有限候选范围内的要求冲突。采用三类演示规则和五个构造案例，与同一目录的全约束基准比较，以过程记录展示新增能力。',
        10: '导入原始表格，保留单元格、单位与版本；由场景规则生成带出处的要求卡，工程师确认后检索同一历史候选目录。全部硬要求共同筛选，未知条件单列；在数值可行集合中展示非支配关系并按指标优先顺序比较，切换偏好不改变可行集合。工程师从准确父配方继续探索，锁定组成并保存需求、改动和设计意图，新草案实测保持未知。C3用五个合理方案展示取舍，C2演示油石比4.9%到5.0%的草案，C5区分84条含缺测目录与35条完整数值诊断子池。原型采用React、FastAPI与SQLite，提供JSON导出和标准接口。已有106项Python测试、12项机制检查和14步AI浏览器自测通过。当前可靠自动逆向配方生成和稳定优于基准的多任务预测属于深化路线。',
        12: '面向道路养护单位、材料研发团队和检测机构，以本地软件部署、数据整理及项目规则配置作为成果转化起点，再提供接口对接和维护服务。预期价值在于集中需求与出处、解释候选取舍、保留调整记录和减少交接遗漏。当前用构造软件案例说明潜在价值，不申报降本、减碳、寿命或真人节时百分比。',
    }
    counts = []
    for row, text in values.items():
        fill_cell(cell(row, 1), text)
        limit = 600 if row == 10 else 300
        assert len(text) <= limit
        counts.append({'row': row, 'characters': len(text), 'limit': limit})
    fill_cell(cell(13, 2), '创意设计类（含软件概念验证原型）')
    fill_cell(cell(14, 2), '无法判断。创新定位为应用机制与协同决策设计，未作领先性认证。')
    fill_cell(cell(15, 2), '软件、方法。')
    fill_cell(cell(16, 2), '第3级（概念验证，自评）。')
    fill_cell(cell(17, 2), '国际技术参照：FHWA平衡配合比设计（2022）。\n功能基准：同候选、同要求的全约束查表B1。\n五案数值可行集合一致，新增解释、取舍与协同设计功能。')
    metric_cell = cell(18, 2)
    nested = metric_cell.find('w:tbl', NS)
    assert nested is not None
    measures = [
        ['材料性能', '待验证', '同池B1', '不适用', '软件案例'],
        ['成本减碳', '未测算', '数据待补', '不适用', '后续评价'],
        ['真人节时', '待验证', '尚无计时', '不适用', '后续评价'],
    ]
    for row, vals in zip(nested.findall('w:tr', NS)[1:], measures):
        for target, value in zip(row.findall('w:tc', NS), vals):
            fill_cell(target, value)
    fill_cell(cell(19, 2), '新功能实现：要求来源、偏好取舍、上下文配方草案和范围内冲突诊断。\n质量、成本、效率及周期的实际提升留待后续项目验证。')
    output = OUTPUT/'项目简表.docx'
    return write_package(template, output, document), counts


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    described, description_counts = description()
    summarized, summary_counts = summary()
    result = {'created_on': '2026-10-23', 'status': 'authored_awaiting_render_review',
              'documents': [summarized, described], 'description_word_limits': description_counts,
              'summary_word_limits': summary_counts, 'identity_fields': 'intentionally_blank_for_anonymous_review',
              'retained_template_geometry': True, 'application_version': '0.4.0'}
    path = ROOT/'artifacts/submission-v8/document-build.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
