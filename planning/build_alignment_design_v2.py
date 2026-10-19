"""Author machine-readable design records. Does not alter v0.1 app or backlog."""
import hashlib
import json
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]


def write(path,value):
    (ROOT/path).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    # Status describes competition alignment, not a percentage or an official score.
    definitions=[
      ('B01','basic',4,'核心方案与原型','输入养护场景、识别材料性能需求、输出候选、展示依据','partial',
       '手工targets驱动，缺少实际场景需求解析','需求解析与确认贯穿主操作','三类无手工数值目标输入可生成带出处需求卡并推荐',['backend/app/services.py:87','backend/app/services.py:112']),
      ('B02','basic',4,'至少三类结构化场景','场景、组成、性能、适用条件的结构化关联','partial',
       '有标签和固定案例，关系查询及适用条件不足','规则和关系数据模型','三类规则路径及关联候选查询',['configs/cases.json','backend/app/storage.py']),
      ('B03','basic',4,'至少五个带对照案例','场景约束、候选、理由、性能预期或适用判断、基准对照','partial',
       '数值回归已过，固定池及案例报告中的对照不完整','同池B0、B1和完整案例包','五份报告均含基准与未知项；不将回归通过当工程准确率',['design/competition_alignment_evidence_v2.json']),
      ('B04','basic',4,'数据与技术交接','字段、算法或规则、模块与数据需求；鼓励代码模型接口','covered_at_software_level',
       '已有工程与交接，但缺完整上游及工程反馈契约','扩充设计契约和能力状态','企业可理解的请求响应与字段说明',['docs/developer-guide.md','docs/api.openapi.json']),
      ('B05','basic',4,'应用价值','分析设计周期、选型和匹配效率；可靠时测算成本寿命碳排','partial',
       '仅有接口耗时与潜在价值，缺业务任务对照','同信息人工与系统流程评估','时间、操作、遗漏和可追溯性记录；假设与实测分开',['docs/release-notes.md']),
      ('T01','technical_detail',2,'场景量化映射','气候、交通、结构、病害及严重程度到目标值','not_implemented',
       '气候交通没有进入需求计算，严重程度缺字段','条件规则与来源卡','命中、缺失与冲突均可解释',['backend/app/domain/contracts.py:47','backend/app/services.py:112']),
      ('T02','technical_detail',2,'多约束优先级','预算、工期、环保下的性能权重与优先序','partial',
       '一个priority字段且预算缺价标未知','硬约束、偏好、未知约束分离','权重改变不覆盖失败；未知维度不静默重分权重',['backend/app/services.py:151']),
      ('T03','technical_detail',3,'材料性能场景知识','组成、性能和适用关系可查询可推理','partial',
       '实验材料目录可用，场景适用关系不足','关系表和有证据路径','可解释场景为何关联某产品及缺项',['backend/app/storage.py']),
      ('T04','technical_detail',3,'目标到材料方案','品种、改性剂、级配、助剂及性能预期','partial',
       '历史候选及手工微调存在，组成披露和推荐生成不完整','历史方案检索与完整组成卡；条件优化另列','所有字段有值或未知状态，不猜剂量',['backend/app/services.py:192']),
      ('T05','technical_detail',3,'多维方案比较','性能、成本、碳排、寿命、施工可行性','partial',
       '四性能表和级配图已有；其他数据欠缺','同口径性能雷达与维度缺项卡','缺测不补0，未知成本碳寿命不出虚构分数',['frontend/src/main.tsx','configs/features.json']),
      ('T06','technical_detail',3,'路用效果反馈','实施后监测关联推荐引擎与更新','design_gap',
       '实验室观察有审核，现场体系未实现，新variant训练资格不足','分开实验室与工程记录并受控更新','正式新试验可进入训练视图，模拟工程反馈不冒充实测',['backend/app/ml/features.py:48','backend/app/services.py:244']),
      ('T07','technical_detail',3,'多性能和小样本路线','组成及环境输入，多性能预测、小样本策略和解释','research_evidence_only',
       '四独立模型及严格基准完成，选择流程无稳定改进；无联合学习','独立基准加多任务GP公平对照，环境输入依赖真实记录','同组划分、离折预测、每指标表现及失败原因',['artifacts/models/model_cards.json']),
      ('T08','technical_detail',3,'预测解释','材料参数到预测贡献和工程解释','partial',
       '已有规则原因，模型贡献未进入候选主视图','规则路径、特征贡献、邻例和适用性','模型关联解释不作为实验因果证据',['backend/app/services.py:112','backend/app/ml/predict.py']),
      ('T09','technical_detail',3,'养护决策接口及模块','场景与方案标准数据格式、松耦合API和操作全流程','partial',
       '通用API可用，缺带上游决策ID的适配器和样例','决策请求到需求解析再到方案返回','本地模拟端到端；真实企业联调另记',['backend/app/main.py']),
      ('T10','technical_detail',2,'材料工艺衔接','材料组成和拌和、摊铺、压实条件的适配','not_implemented',
       '场景文本与标签不执行工艺适用检查','工艺来源卡、兼容及未知状态','无资料不认定施工可行；明确不兼容可排除',['backend/app/domain/contracts.py']),
      ('X01','bonus',4,'多目标配方优化','有组成与模型依据的配方变量优化','disabled_by_conditions',
       'RAP质量基准等不明，自动优化关闭','小范围有上限枚举后比较BO','质量核算及独立评价，不用代理自评分证明改进',['configs/features.json']),
      ('X02','bonus',4,'多性能协同预测','任务间共享信息并公平验证','not_implemented',
       '四独立预测不构成协同','多任务GP与独立模型同划分比较','有共同参数或相关性机制，公开负迁移',['artifacts/models/model_cards.json']),
      ('X03','bonus',4,'置信度分析','推荐风险和校准分析','research_evidence_only',
       '12校准组、8测试组，区间较宽，物理料源尚未确认','保留覆盖、宽度、拒答与域外状态','不把单指标覆盖解释为联合或工程保证',['artifacts/models/model_cards.json']),
      ('X04','bonus',4,'生命周期成本或碳排','具有可靠数据边界的效益评价','data_unavailable',
       '缺价格、能耗、因子与寿命数据','数据结构及情景计算框架','有依据后核算，RAP比例不直接换算减碳',['configs/features.json']),
      ('X05','bonus',4,'实验室性能验证','真实材料独立试验','awaiting_external',
       '新增观察流程不等于已完成独立材料试验','同批对照及原始材料核验方案','报告真实试件与条件，非软件合成值',['docs/enterprise-questions.md']),
      ('X06','bonus',4,'实际接口联调','与养护决策系统联调','awaiting_external',
       '尚未企业系统双向验证','先本地模拟，再企业样例联调','联调对象、协议、请求响应与结果证据',['docs/api.openapi.json']),
      ('X07','bonus',4,'模型持续学习','反馈数据积累后受控改进','design_gap',
       '数据失效保护存在，无自动学习收益证据','审核、版本、候选模型比较与批准发布','固定测试和新来源验证，支持回退',['backend/app/ml/features.py'])]
    requirements=[]
    for id,kind,page,title,requirement,status,gap,design,acceptance,evidence in definitions:
        requirements.append({'id':id,'kind':kind,'source_page':page,'title':title,'requirement_paraphrase':requirement,
                             'current_status':status,'gap':gap,'v2_design':design,'acceptance':acceptance,'existing_evidence':evidence})
    diagnostic=json.loads((ROOT/'design/competition_alignment_evidence_v2.json').read_text(encoding='utf-8'))
    write('design/competition_requirements_v2.json',{'version':'2.0-design','review_date':'2026-10-19',
        'source':{'file':diagnostic['official_pdf'],'sha256':diagnostic['official_pdf_sha256'],'topic':1,'pages':[1,2,3,4,5]},
        'official_scoring_weights':None,'priority_note':'任务分类依据任务书，实施优先级由团队确定，不给官方评分或契合百分比。',
        'requirements':requirements})
    items=[
      ('A01',4,'上游场景和需求契约',['B01','B04','T01','T09'],[],'结构层、严重程度和来源字段；合法、缺失与演示输入样例'),
      ('A02',6,'三类需求规则卡',['B01','B02','T01','T02'],['A01'],'来源、条件、目标、优先级；构造与正式模式隔离'),
      ('A03',6,'需求解析与确认',['B01','T01','T02'],['A02'],'无手工targets输入可解析；冲突、覆盖和待补项可追溯'),
      ('A04',6,'场景材料知识关系',['B02','T03'],['A01'],'三类场景可查询组成、性能、适用条件和证据路径'),
      ('A05',4,'完整组成与方案卡',['B01','T04','T05'],['A04'],'产品、级配、用油、RAP、助剂与工艺字段真实或明确未知'),
      ('A06',6,'候选池自动检索与冻结',['B03','T03','T04'],['A03','A04'],'按库存和适用规则生成，显示全量排除和范围哈希'),
      ('A07',4,'组成施工及未知约束检查',['T02','T10'],['A05','A06'],'不兼容可排除，条件未知不自动通过，研究数值筛选另标'),
      ('A08',6,'多指标偏好与比较',['T02','T05','T08'],['A07'],'硬约束后排序，并列、贡献、雷达缺测和未知成本可见'),
      ('A09',4,'候选预测与验证视图',['B01','B03','T07','T08'],['A05'],'区分历史、离折与研究预测；显示模型边界与原始对照'),
      ('A10',6,'五案例同池基准报告',['B03','T09'],['A08','A09'],'B0、强B1及V2比较；正例、无解和不适用负例'),
      ('A11',4,'上游接口本地模拟',['B04','T09'],['A03','A06'],'决策ID、需求版本和候选响应端到端；不冒充企业联调'),
      ('A12',4,'实验室新方案资格与工程反馈契约',['B04','T06'],['A05','A11'],'正式新试验进入适格训练视图；现场模拟与实验室指标分开'),
      ('A13',4,'应用价值比较记录',['B05'],['A10'],'同信息流程用时、操作和遗漏记录；自测范围明确'),
      ('A14',4,'参赛报告与对齐验收',['B01','B02','B03','B04','B05'],['A10','A11','A12','A13'],'基本成果逐项挂接证据，程序、案例、答辩与能力状态一致')]
    tasks=[{'id':id,'priority':'P0_alignment','title':title,'estimate_hours':hours,'status':'planned',
            'owner':'single_developer','requirements':reqs,'dependencies':deps,'acceptance':acceptance}
            for id,hours,title,reqs,deps,acceptance in items]
    tasks.extend([
      {'id':'M01','priority':'P1_conditional','title':'小样本多任务GP对照','estimate_hours':8,'status':'planned',
       'owner':'single_developer','requirements':['T07','X02'],'dependencies':['A09'],'acceptance':'统一来源分组和缺测掩码，同划分独立基线对照；公开负结果'},
      {'id':'M02','priority':'P1_conditional','title':'局部配方探索','estimate_hours':8,'status':'blocked_by_data_condition',
       'owner':'single_developer','requirements':['X01'],'dependencies':['A07','A09'],
       'optional_inputs':['M01'], 'condition':'RAP质量基准、原料关联、允许变量、通过项目验证门槛的代理模型及独立评价路径明确',
       'acceptance':'有上限的合法组成搜索和独立验证，未实测状态清晰'}])
    write('planning/v02_alignment_backlog.json',{'schema_version':'2.0-design','design_date':'2026-10-19',
        'scope':'赛题对齐增量，不重置或代替v0.1工程验收历史；本轮仅完成设计与诊断',
        'capacity':{'developers':1,'p0_estimated_hours':sum(t['estimate_hours'] for t in tasks if t['priority']=='P0_alignment'),
                    'conditional_estimated_hours':16,'suggested_buffer_hours':12,'deadline':None,
                    'note':'初步估算，不代表已消耗工时；外部试验劳动和企业联调等待不计入'},'tasks':tasks})
    targets=[{'metric':m,'operator':'>','value':v,'unit':u,'source_kind':origin,'reference':ref,
              'comparison_basis':'legacy_workbook_numeric_demo','test_method':None,'conditions_status':'unverified'}
             for m,v,u,origin,ref in [('DS',8000,'次/mm','constructed_demo','DEMO-HT-V1'),
                 ('strain',2000,'με','enterprise_reference','设计流程!E12'),
                 ('TSR',75,'%','enterprise_reference','设计流程!E10'),
                 ('residual',85,'%','enterprise_reference','设计流程!E10')]]
    write('design/design_contract_v2.example.json',{'implementation_status':'proposed_not_implemented',
        'scope':'仅演示设计契约，路径不是当前可调用的v1接口；示例目标不可当正式项目要求',
        'metric_registry_design':{'value_types':['scalar','range','grade'],'condition_keys':['test_method','temperature','frequency','aging'],
            'known_but_unsupported':['PG_grade','fatigue_life','dynamic_modulus'],'unsupported_request_behavior':'保留合法需求并报告证据缺失，不替换或忽略'},
        'proposed_endpoint':'POST /v2/demand-resolutions',
        'request':{'schema_version':'2.0','decision_id':'DEMO-UPSTREAM-001','context_kind':'constructed_demo',
            'scene':{'maintenance_method':'演示：已由上游确定的面层铣刨重铺','layer':'演示上面层',
                'climate':{'class':'demo_hot','source':'scenario_assumption'},'traffic':{'class':'demo_heavy','source':'scenario_assumption'},
                'distress':{'type':'rutting','severity':'demo_moderate','mechanism':'upstream_confirmation_required'}},
            'inventory':{'source_codes':None,'product_versions':None,'status':'not_yet_confirmed'},
            'construction':{'mixing_window':None,'compaction_window':None,'status':'unknown'},
            'constraints':{'budget':None,'schedule_days':None,'rap_min_pct':0,'carbon_cap':None}},
        'demand_resolution':{'status':'demo_targets_require_confirmation','targets':targets,'priority_order':['DS','strain','TSR','residual'],
            'unresolved':['正式场景规则适用性','库存来源范围','具体试验和施工条件'],'project_approved':False},
        'proposed_recommendation_response':{'candidate_pool':{'retrieval_policy':'scene_and_inventory_v2','snapshot_sha256':None,'status':'not_executed'},
            'candidate_card_schema':{'recipe_version_id':'required','product_version':'required','modifier':{'type':None,'dosage':None,'disclosure_status':'not_provided'},
                'gradation':{'full_id':'required','components':'array_or_unknown','curve_reference':'required_when_available'},
                'binder':{'oil_stone_ratio_pct':'number_or_unknown','new_binder_amount':None,'mass_basis_status':'unconfirmed'},
                'rap':{'nominal_pct':'number_or_unknown','mass_basis':'unconfirmed'},'functional_additives':{'items':None,'disclosure_status':'not_provided'},
                'performance':{'historical':'value_method_conditions_source','oof_prediction':'value_fold_error_or_unavailable',
                               'research_prediction':'value_model_applicability_or_unavailable'},
                'construction_compatibility':'compatible_incompatible_or_unknown','cost':None,'carbon':None,'service_life':None,
                'decision_state':'historical_review_needs_test_excluded_or_context_invalid','evidence_links':'required'},
            'versions':['dataset','demand','rule','candidate_pool','recipe','model','report']}})
    doc=ROOT/'design/数智选材_赛题对齐与深化设计_v2.md'
    body=doc.read_text(encoding='utf-8').split('\n\n',1)[1].strip()
    manifest_path=ROOT/'design/alignment_design_manifest_v2.json'
    previous=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    manifest={'title':'数智选材赛题对齐与深化设计','date':'2026-10-19','status':'design_only_app_v1_unchanged',
        'parent_page_id':'page_b3e90ae7e0a88191967a4234479f66dd','idempotency_key':previous.get('idempotency_key') or str(uuid4()),
        'local_document':str(doc),'document_sha256':hashlib.sha256(doc.read_bytes()).hexdigest(),
        'evidence_file':'competition_alignment_evidence_v2.json','requirement_count':len(requirements),
        'requirements_by_kind':{k:sum(r['kind']==k for r in requirements) for k in ['basic','technical_detail','bonus']},
        'incremental_tasks':len(tasks),'p0_estimated_hours':68,
        'original_release_unchanged':True,'source_pdf_sha256':diagnostic['official_pdf_sha256'],
        'workbook_sha256':diagnostic['workbook_sha256'],'page_id':previous.get('page_id'),'page_url':previous.get('page_url'),
        'page_synced_document_sha256':previous.get('page_synced_document_sha256'),'page_layout_preview':'not_inspected'}
    write('design/alignment_design_manifest_v2.json',manifest)
    write('design/alignment_page_blocks_v2.json',{'title':manifest['title'],'blocks':body.split('\n\n')})
    print(json.dumps({'requirements':len(requirements),'tasks':len(tasks),'p0_hours':68,
                      'document_characters':len(body),'page_blocks':len(body.split('\n\n'))},ensure_ascii=False))


if __name__=='__main__':main()
