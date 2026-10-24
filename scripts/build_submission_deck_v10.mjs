/** Create an editable, evidence-based competition deck using the bundled Artifact Tool. */
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { execFileSync } from 'node:child_process';

const options = Object.fromEntries(process.argv.slice(2).reduce((pairs, value, i, args) => {
  if (value.startsWith('--')) pairs.push([value.slice(2), args[i+1]]);
  return pairs;
}, []));
for (const key of ['runtime-modules', 'skill-dir', 'python']) {
  if (!options[key]) throw new Error(`Missing --${key}`);
}
const ROOT = process.cwd();
const BUILD = path.join(ROOT, 'tmp/submission-v10/deck-build');
const OUT = path.join(ROOT, 'output/submission-v10/05_演示PPT');
const SKILL = options['skill-dir'];
// The finalizer spawns a fresh Node process for its first-party import check.
process.env.RUNTIME_NODE_MODULES = options['runtime-modules'];
const { Presentation, PresentationFile } = await import(pathToFileURL(
  path.join(options['runtime-modules'], '@oai/artifact-tool/dist/artifact_tool.mjs')).href);
const { finalizePresentation } = await import(pathToFileURL(
  path.join(SKILL, 'container_tools/artifact_tool_utils.mjs')).href);
await fs.mkdir(BUILD, {recursive: true});
await fs.mkdir(OUT, {recursive: true});

const C = {paper:'#F5F6F1', ink:'#143F3B', body:'#233431', muted:'#52645F', teal:'#177F76', line:'#CCD7D1'};
const FONT = 'Microsoft YaHei';
const pres = Presentation.create({slideSize:{width:1280, height:720}});
const guide = 'https://cpipc.acge.org.cn/cw/contestNews/detail/1/2c9080189ef4ecee019f038802d55c4b?page=0';
const topic = 'https://cpipc.acge.org.cn/cw/contestNews/detail/1/2c9080189fb0808c019fc63d2f083049?page=0';
const references = [];

function text(slide, value, left, top, width, height, size=28, bold=false, color=C.body) {
  const shape = slide.shapes.add({geometry:'textbox', position:{left, top, width, height},
    fill:'none', line:{fill:'none',width:0}});
  shape.text = value;
  shape.text.style = {typeface:FONT, fontSize:size, bold, color, wrap:'square',
    autoFit:'none', insets:0, verticalAlignment:'top'};
  return shape;
}
function slide(title, note, source) {
  const s = pres.slides.add();
  s.background.fill = C.paper;
  text(s, title, 64, 45, 1152, 64, 44, true, C.ink);
  s.speakerNotes.text = `${note}\n\n来源\n${source}`;
  references.push({slide:pres.slides.items.length, title, source});
  return s;
}
function foot(s, value) { text(s, value, 64, 650, 1100, 48, 18, false, C.muted); }
async function screenshot(s, filename, left=64, top=142, width=795, height=497) {
  const bytes = await fs.readFile(path.join(ROOT, 'artifacts/submission-v8/demo', filename));
  s.images.add({blob:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),
    contentType:'image/png', alt:`概念原型实际界面 ${filename}`, fit:'contain',
    position:{left,top,width,height}});
}
function table(s, values, widths, top=160, height=398, size=26) {
  const t = s.tables.add({rows:values.length,columns:values[0].length,left:64,top,
    width:1152,height,columnWidths:widths,values});
  t.borders.assign({fill:C.line,width:0.7,style:'solid'});
  for(let r=0;r<values.length;r++) for(let c=0;c<values[r].length;c++) {
    const cell=t.getCell(r,c);
    cell.fill=r===0?C.ink:(r%2?'#FFFFFF':'#EDF1EB');
    cell.text.style={typeface:FONT,fontSize:size,color:r===0?'#FFFFFF':C.body,
      bold:r===0,wrap:'square',autoFit:'none',verticalAlignment:'middle',insets:12};
  }
  return t;
}

// Cover: the work name and scope are the only headline content.
{
  const s=pres.slides.add(); s.background.fill=C.ink;
  text(s,'数智选材',72,156,1136,116,76,true,'#FFFFFF');
  text(s,'道路养护材料推荐与协同设计',76,294,1100,80,40,false,'#E9F3EB');
  text(s,'企业揭榜赛道 HY-01 课题一\n创意方案与可运行概念原型',76,493,1100,96,27,false,'#B5D5CD');
  s.speakerNotes.text=`作品帮助养护工程师把场景要求落实到材料选择，再沿着准确父配方继续设计。选材理由、性能取舍和实际改动保存在同一案例中，便于复核与交接。研发使用AI辅助，内容复核由参赛者负责。\n\n来源\n${topic}\ndocs/submission-final-v10.md`;
  references.push({slide:1,title:'数智选材',source:topic});
}
{
  const s=slide('赛题成果与本作品交付',
    '课题一以创意方案和核心原型为基本成果，允许合理构造案例。作品用三类演示规则覆盖高温重载、寒冷裂缝和水损害，再增加资源变更和复合要求，形成五案。作品论文展开数据口径、决策方法、案例结果与计算研究。',
    `${guide}\n${topic}\ndocs/submission-final-v10.md\nartifacts/submission-v8/verification.json`);
  table(s,[['赛题基本成果','当前交付'],
    ['完整方案与核心原型','本地浏览器原型及推荐依据'],
    ['至少三类典型场景','三类明确登记的演示场景规则'],
    ['不少于五个典型案例','五个构造案例及同池B1对照'],
    ['数据与技术交接','源码 结构化数据 OpenAPI与操作记录'],
    ['应用价值分析','选型 比较 调整与交接的使用过程']], [365,787],145,414,26);
  text(s,'历史性能值来自企业工作簿，场景要求和案例为演示构造。',64,585,1152,48,27,false,C.teal);
  foot(s,'作品论文、五案记录和计算结果提供逐项查阅依据。');
}
{
  const s=slide('三种操作对应三种决策机制',
    '三个操作改变不同的对象。修改要求会重算候选，切换偏好会重排原集合，调整配方会建立独立草案。分开处理后，工程师能够解释哪些结论随操作更新，并沿着原记录继续工作。',
    'docs/innovation-brief-v8.md\ndocs/submission-final-v10.md\nartifacts/polish-v7/completion.json');
  table(s,[['工程师操作','系统处理','可检查的结果'],
    ['修改硬要求','重新筛选并保留旧决策','要求出处与变更理由'],
    ['切换优先性能','同一可行集合内重排','并列 取舍与比较理由'],
    ['调整父配方','保存带原需求的独立草案','组成变化与设计意图']], [275,430,447],157,328,27);
  text(s,'五案与全约束查表B1的数值可行数均为 2、2、5、1、0。',64,529,1152,63,29,true,C.teal);
  foot(s,'同池对照核对筛选结果，新增记录解释选择与后续设计。');
}
{
  const s=slide('C1 高温重载场景的要求与出处',
    '工程师先确认四项要求，再比较H与R1。H的动稳定度9565次每毫米，R1的应变和TSR更高。要求卡说明阈值依据，材料卡定位原始单元格，两条查证路径共同支持本次选择。',
    'docs/submission-final-v10.md\nartifacts/submission-v8/demo/C1-sources.png\nartifacts/submission-v8/demo/recording.json');
  await screenshot(s,'C1-sources.png');
  text(s,'84条目录\n2项数值可行',893,162,319,120,34,true,C.teal);
  text(s,'确认场景要求\n查看原始数值\n追溯源单元格',893,336,319,170,29);
  foot(s,'要求卡记录阈值依据，材料卡关联原始数据和适用条件。');
}
{
  const s=slide('C2 保留原需求的配方协同设计',
    '寒冷场景的两个候选应变均为2525微应变，比较继续进入TSR，R4进入优先查看位置。工程师从准确父配方的10个假设中筛出7个范围内假设，保持名义组分份额，将油石比4.9%至5.0%的变化保存为草案。',
    'docs/submission-final-v10.md\nartifacts/submission-v8/demo/C2-draft.png\nartifacts/submission-v8/demo/recording.json');
  await screenshot(s,'C2-draft.png');
  text(s,'油石比\n4.9% 至 5.0%',893,162,319,120,34,true,C.teal);
  text(s,'保留原需求与父配方\n锁定名义组分份额\n记录改动和设计意图',893,336,319,230,29);
  foot(s,'两项候选应变均为2525με；新草案性能以待验证状态登记。');
}
{
  const s=slide('C3 多个合理方案之间的性能取舍',
    '水损害案例有5项数值可行，5项均非支配。TSR优先查看H，残留稳定度优先查看K，工程师可按项目偏好比较余量。切换优先性能不改变可行集合。图中的历史数值和目标线帮助说明选择依据。',
    'docs/submission-final-v10.md\nartifacts/submission-v8/demo/C3-chart.png\nartifacts/submission-v8/demo/recording.json');
  await screenshot(s,'C3-chart.png');
  text(s,'5项数值可行\n5项均非支配',893,162,319,120,34,true,C.teal);
  text(s,'TSR优先查看H\n残留稳定度优先查看K\n\n偏好只改变顺序。',893,336,319,227,28);
  foot(s,'图中展示可比较候选的历史值。偏好切换保留全部五项数值可行方案。');
}
{
  const s=slide('C4 资源要求变更的结果预览',
    '四项性能要求下R5是唯一已知数值可行候选，其名义RAP为70%。将资源门槛提高至75%后，预览显示已知可行数由1变0。工程师查看变动和资料状态，确认理由后保存新需求，原记录保留供比较。',
    'docs/submission-final-v10.md\nartifacts/submission-v8/demo/C4-preview.png\nartifacts/submission-v8/demo/recording.json');
  await screenshot(s,'C4-preview.png');
  text(s,'名义RAP\n70% 提高至 75%',893,162,319,120,34,true,C.teal);
  text(s,'已知可行数\n1 变为 0\n\n确认理由后另存。',893,336,319,215,29);
  foot(s,'资源条件与性能要求一起保存，原70%需求下的记录可继续回看。');
}
{
  const s=slide('C5 无结果时的证据与范围解释',
    '84条目录中44条已知失败、40条待补证据，工程师先核查缺测。明确选定35条完整数值子池后，可以查看4组最小冲突。每份证书保存冲突要求、范围和删除见证，帮助讨论补资料或调整指标。',
    'docs/submission-final-v10.md\nartifacts/submission-v8/demo/C5-conflict.png\nartifacts/submission-v8/demo/recording.json');
  await screenshot(s,'C5-conflict.png');
  text(s,'84条完整目录\n证据不足',893,162,319,120,34,true,C.teal);
  text(s,'35条完整数值子池\n可查看4组最小冲突。\n\n下一步可补资料\n或调整要求。',893,329,319,254,28);
  foot(s,'每份冲突证书同时列出候选范围、指标子集与删除见证。');
}
{
  const s=slide('首期服务与后续产品化路径',
    '首期服务面向拥有历史资料且需要重复选材的养护和材料研发团队。从一个经授权的目录和项目要求起步，交付软件、数据字段、规则和案例回放。试用围绕真实选材、比较与交接任务验收，再按需求增加接口和维护。',
    'docs/business-plan-v10.md\ndocs/submission-final-v10.md');
  text(s,'首期交付',64,167,365,55,33,true,C.teal);
  text(s,'本地软件与数据整理\n项目规则配置\n案例回放与接口文档',64,251,500,180,30);
  text(s,'推广步骤',688,167,460,55,33,true,C.teal);
  text(s,'确认授权与真实需求\n小范围试用并按任务验收\n再扩展接口与维护服务',688,251,500,180,30);
  text(s,'拟按部署配置与额外接口工作量计费，另约维护服务。',64,503,1152,60,29,true,C.ink);
  foot(s,'报价依据资料整理、部署适配、接口范围和持续支持工作量。');
}
{
  const s=slide('成果交付与下一步应用',
    '当前交付可运行原型、源码、数据、五案和计算研究。既有记录包括106项Python测试、12项机制检查及14步AI浏览器自测。后续先核实项目规则和材料身份，再组织真实任务试用，依据新增资料扩展性能模型和候选生成。',
    'docs/submission-final-v10.md\nartifacts/submission-v8/verification.json\nartifacts/submission-v8/anonymous-checkout.json');
  text(s,'已交付',64,167,480,58,34,true,C.teal);
  text(s,'可运行原型与匿名源码包\n三类规则与五案回放\n接口 操作视频和软件证据',64,258,530,205,30);
  text(s,'后续应用',688,167,480,58,34,true,C.muted);
  text(s,'接入项目要求与材料资料\n开展真实选材和交接试用\n扩展性能模型与候选生成',688,258,530,205,30);
  text(s,'核心价值是让选材理由、性能取舍和设计改动能够连续交接。',64,528,1152,76,31,true,C.ink);
  foot(s,'数据范围、方法、案例原值与计算记录见作品论文及证据索引。');
}

const candidate=path.join(BUILD,'candidate.pptx');
await (await PresentationFile.exportPptx(pres)).save(candidate);
await fs.writeFile(path.join(BUILD,'slide-sources.json'),JSON.stringify(references,null,2));
for(let i=0;i<pres.slides.items.length;i++) {
  const blob=await pres.export({slide:pres.slides.items[i],format:'png',scale:1.5});
  await fs.writeFile(path.join(BUILD,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await blob.arrayBuffer()));
}
const finalPath=path.join(OUT,options['filename']||'作品演示.pptx');
const result=await finalizePresentation({workspaceDir:ROOT,candidatePath:candidate,finalPath,
  pythonExecutable:options.python,
  integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',
    '--require-native-table-slide','2','--require-native-table-slide','3'],
  requiredNativeTableOwnerSlides:[2,3],fontPolicy:{basis:'design',families:[FONT]},
  verifyArtifactToolImport:true,receiptPath:path.join(BUILD,path.basename(finalPath)+'.validation.json')});
const pdfPath=path.join(OUT,'作品演示.pdf');
try {
  const pdf=await pres.export({format:'pdf'});
  await fs.writeFile(pdfPath,new Uint8Array(await pdf.arrayBuffer()));
} catch(error) {
  if(process.platform!=='win32'||!String(error).includes('#standard-fonts/')) throw error;
  // This bundle lacks the standard-font PDF resource. Use installed Office,
  // retaining the fully validated editable PPTX and the managed runtime.
  execFileSync('powershell.exe',['-NoProfile','-File',path.join(ROOT,'scripts/export_submission_deck_v9.ps1'),
    '-PptxPath',finalPath,'-PdfPath',pdfPath],{windowsHide:true,stdio:'pipe'});
}
console.log(JSON.stringify({pptx:finalPath,pdf:path.join(OUT,'作品演示.pdf'),slides:pres.slides.items.length,
  validation:result,visual_review:'pending'},null,2));
