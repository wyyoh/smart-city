"""Fill the retained official business-plan template, preserving opaque parts."""
from copy import deepcopy
import json
from pathlib import Path
import re
from zipfile import ZipFile

from lxml import etree as E
from build_submission_documents_v8 import NS, W, replace_paragraph, sha

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT/'artifacts/submission-v8/official/business-plan.docx'
DESTINATION = ROOT/'output/submission-v9/04_商业计划书/商业计划书.docx'


def write_package(template, output, document):
    edited = {'word/document.xml', 'docProps/core.xml', 'word/styles.xml'}
    before = {}
    with ZipFile(template) as source, ZipFile(output, 'w') as target:
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
            elif info.filename == 'word/styles.xml':
                # The official template omits Word's Title style. Append a
                # semantic style only; keep every existing style byte intact.
                assert b'w:styleId="Title"' not in data
                addition = ('<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
                            '<w:basedOn w:val="1"/><w:next w:val="1"/><w:qFormat/>'
                            '<w:pPr><w:jc w:val="center"/></w:pPr><w:rPr>'
                            '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="仿宋"/>'
                            '<w:b/><w:color w:val="000000"/><w:sz w:val="28"/></w:rPr></w:style>').encode('utf-8')
                data = data.replace(b'</w:styles>', addition+b'</w:styles>')
                assert data.replace(addition, b'') == source.read(info.filename)
            target.writestr(info, data)
    with ZipFile(output) as final:
        assert set(before) == set(final.namelist())
        assert all(sha(final.read(n)) == value for n, value in before.items() if n not in edited)
    return {'template': template.relative_to(ROOT).as_posix(), 'template_sha256': sha(template.read_bytes()),
            'output': output.relative_to(ROOT).as_posix(), 'output_sha256': sha(output.read_bytes()),
            'preserved_package_parts': len(before)-len(edited), 'edited_parts': sorted(edited),
            'style_addition': 'Title only; all original style bytes preserved'}


def main():
    assert sha(TEMPLATE.read_bytes()) == '777f66a29204f6a9470da43f0b23d1e3c76f08a4891c08718c81c27dfd91e01b'
    with ZipFile(TEMPLATE) as source:
        document = E.fromstring(source.read('word/document.xml'))
    body = document.find('w:body', NS)
    original = body.findall('w:p', NS)
    section = deepcopy(body.find('w:sectPr', NS))
    sources = [original[i] for i in [5, 6, 7, 10, 14, 19]]
    sub_sources = [[8, 9], [11, 12, 13], [15, 16, 17, 18]]
    content = (ROOT/'docs/business-plan-v9.md').read_text(encoding='utf-8')
    sections = re.split(r'^## ', content, flags=re.M)[1:]
    assert len(sections) == 6
    for element in list(body):
        body.remove(element)
    for element in original[:3]:
        body.append(deepcopy(element))
    title = deepcopy(original[3])
    replace_paragraph(title, '数智选材 道路养护材料推荐与协同设计', bold=True)
    # The reference controls fonts and spacing. Title style adds semantics only.
    title_pr = title.find('w:pPr', NS)
    title_pr.insert(0, E.Element(W+'pStyle', {W+'val': 'Title'}))
    body.append(title)
    body.append(deepcopy(original[4]))
    counts = []
    for index, text in enumerate(sections):
        _, payload = text.split('\n', 1)
        count = len(re.sub(r'\s', '', text))
        limit = [200, 200, 2000, 2000, 2000, 500][index]
        assert count <= limit, (index, count, limit)
        counts.append({'section': index+1, 'including_subheadings_and_punctuation': count, 'limit': limit})
        heading = deepcopy(sources[index])
        props = heading.find('w:pPr', NS)
        E.SubElement(props, W+'keepNext')
        body.append(heading)
        sub_index = 0
        for block in payload.strip().split('\n\n'):
            is_sub = block.startswith('### ')
            source_paragraph = original[8]
            if is_sub:
                source_paragraph = original[sub_sources[index-2][sub_index]]
                sub_index += 1
            paragraph = deepcopy(source_paragraph)
            text_value = ''.join(source_paragraph.xpath('.//w:t/text()', namespaces=NS)) if is_sub else block
            replace_paragraph(paragraph, text_value, bold=False)
            if is_sub:
                E.SubElement(paragraph.find('w:pPr', NS), W+'keepNext')
            body.append(paragraph)
    body.append(section)
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    result = write_package(TEMPLATE, DESTINATION, document)
    result.update({'created_on': '2026-10-24', 'status': 'authored_awaiting_visual_review',
                   'word_limits': counts, 'reference_page_count': 1,
                   'source_docx_unchanged': True, 'template_section_geometry_unchanged': True})
    evidence = ROOT/'artifacts/submission-v9'
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence/'business-plan-build.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'output': result['output'], 'counts': counts}, ensure_ascii=False))


if __name__ == '__main__':
    main()
