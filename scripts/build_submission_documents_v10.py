"""Populate current official forms; retain original template package parts."""
from copy import deepcopy
import json
from pathlib import Path
import re
from zipfile import ZipFile
from lxml import etree as E
from build_submission_documents_v8 import NS, W, replace_paragraph, fill_cell, write_package, paragraph_text

ROOT=Path(__file__).resolve().parents[1]
OFFICIAL=ROOT/'artifacts/submission-v8/official'
OUT=ROOT/'output/submission-v10/01_必交文档'


def description():
    template=OFFICIAL/'project-description.docx'
    with ZipFile(template) as z: document=E.fromstring(z.read('word/document.xml'))
    body=document.find('w:body',NS)
    original=body.findall('w:p',NS)
    section=deepcopy(body.find('w:sectPr',NS))
    for node in list(body):body.remove(node)
    for p in original[:3]:body.append(deepcopy(p))
    p=deepcopy(original[3]);replace_paragraph(p,'数智选材 道路养护材料推荐与协同设计',bold=True);body.append(p)
    content=(ROOT/'docs/submission-final-v10.md').read_text(encoding='utf-8')
    sections=re.split(r'^## ',content,flags=re.M)[1:]
    assert len(sections)==4
    counts=[]
    for i,text in enumerate(sections):
        _,payload=text.split('\n',1)
        count=len(re.sub(r'\s','',text));limit=[2000,3000,3000,500][i]
        assert count<=limit,(i,count,limit)
        counts.append({'section':i+1,'count_including_headings_and_punctuation':count,'limit':limit})
        p=deepcopy(original[[5,7,11,13][i]])
        E.SubElement(p.find('w:pPr',NS),W+'keepNext');body.append(p)
        for block in payload.strip().split('\n\n'):
            is_sub=block.startswith('### ')
            p=deepcopy(original[8 if is_sub else 6])
            replace_paragraph(p,block[4:] if is_sub else block,bold=is_sub)
            if is_sub:E.SubElement(p.find('w:pPr',NS),W+'keepNext')
            body.append(p)
    body.append(section)
    return write_package(template,OUT/'项目说明书.docx',document),counts


def summary():
    source=json.loads((ROOT/'docs/project-summary-v10.json').read_text(encoding='utf-8'))
    template=OFFICIAL/'project-summary.docx'
    with ZipFile(template) as z:document=E.fromstring(z.read('word/document.xml'))
    body=document.find('w:body',NS);ps=body.findall('w:p',NS)
    replace_paragraph(ps[3],'数智选材',bold=True)
    for p in ps[4:]:
        if not paragraph_text(p).strip():body.remove(p)
    rows=body.find('w:tbl',NS).findall('w:tr',NS)
    cell=lambda r,c:rows[r].findall('w:tc',NS)[c]
    for index in [5,7,9,11]:
        for p in rows[index].findall('.//w:tc/w:p',NS):
            prop=p.find('w:pPr',NS)
            if prop is None:prop=E.SubElement(p,W+'pPr')
            E.SubElement(prop,W+'keepNext')
    fill_cell(cell(0,1),source['title'])
    for p in cell(2,1).findall('w:p',NS):
        if '13.企业揭榜赛道' in paragraph_text(p):replace_paragraph(p,'13.企业揭榜赛道（已选择，HY-01课题一）')
    counts=[]
    for index,text in source['sections'].items():
        index=int(index);limit=600 if index==10 else 300
        assert len(text)<=limit,(index,len(text),limit)
        fill_cell(cell(index,1),text);counts.append({'row':index,'characters':len(text),'limit':limit})
    for index,text in {
        13:'创意设计类（含可运行概念原型）',
        14:'无法判断。以应用机制设计和五案对照说明创新。',
        15:'软件、方法。',16:'第3级（概念验证，自评）。',
        17:'国际技术参照：FHWA平衡配合比设计（2022）。\n功能基准：同候选、同要求的全约束查表B1。\n五案数值可行集合一致，新增要求解释、性能取舍与设计交接。',
        19:'新功能实现：要求来源、偏好比较、带原需求的设计草案和范围内冲突诊断。\n关键指标采用软件过程检查，提升率栏以“／”标记。'
    }.items():fill_cell(cell(index,2),text)
    nested=cell(18,2).find('w:tbl',NS)
    for row,values in zip(nested.findall('w:tr',NS)[1:],source['measures']):
        for target,value in zip(row.findall('w:tc',NS),values):fill_cell(target,value)
    return write_package(template,OUT/'项目简表.docx',document),counts


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    described,dc=description();summarized,sc=summary()
    result={'created_on':'2026-10-24','status':'authored_awaiting_render_review',
            'documents':[summarized,described],'description_word_limits':dc,
            'summary_word_limits':sc,'retained_template_geometry':True,
            'identity_fields':'blank_for_anonymous_review','application_version':'0.4.0'}
    art=ROOT/'artifacts/editorial-v10';art.mkdir(parents=True,exist_ok=True)
    (art/'document-build.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
