"""Reconcile the live competition index with completed internal research only."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT/'configs/review_evidence_v3.json'
UPDATES = {
    'B04': ('prototype', '接口与研究资料可交接', '历史接口与研究API、规则、字段及运行说明已提供；新主机需安装依赖并保留冻结研究输入库。',
            ['docs/api-research-v4.openapi.json', 'docs/research-workbench-v5.md']),
    'T04': ('partial', '历史检索与未试验配方研究', '支持历史目录、微调失效及1098个待试验假设的检索和组分对比；可靠新配方性能提升仍待独立试验。',
            ['backend/app/research_workbench/service.py', 'artifacts/research-v04/formulation-search.json']),
    'T07': ('research_only', '多性能计算实验已有结果', '独立模型与多任务方法均有历史分组实验；新回退规则仍有两项退步，尚不能证明四项稳定提升，未替换正式模型。',
            ['artifacts/research-workbench/head-fallback.json', 'artifacts/research-workbench/study-verification.json']),
    'X01': ('research_only', '配方假设与试验选点研究', '731个假设位于既定观测支持范围内；支持按设计差异安排试验。RAP质量基准待确认，工程自动优化仍关闭。',
            ['artifacts/research-v04/formulation-search.json', 'backend/app/research_workbench/service.py']),
    'X02': ('research_only', '协同预测完成计算实验', '降秩多任务等方法已做历史分组实验；四项可靠提升与外部泛化尚未证实，不将研究预测用于工程放行。',
            ['artifacts/research-v04/advanced.json', 'artifacts/research-workbench/head-fallback.json']),
    'X05': ('pending_external', '送检方案已备 独立试验待开展', '已备五配方送检包与可保存的试验安排；没有实验室，新增独立材料试验为0，方法、试件数和计量口径待确认。',
            ['artifacts/research-v04/laboratory-handoff.zip', 'docs/research-workbench-v5.md']),
}


def update():
    data = json.loads(PATH.read_text(encoding='utf-8'))
    for row in data['requirements']:
        if row['id'] not in UPDATES: continue
        status, label, scope, paths = UPDATES[row['id']]
        row.update({'status': status, 'status_label': label, 'delivered_scope': scope})
        for name in paths:
            key = 'ev_'+hashlib.sha256(name.encode()).hexdigest()[:14]
            data['evidence'][key] = {'id': key, 'path': name, 'label': Path(name).name,
                                      'sha256': hashlib.sha256((ROOT/name).read_bytes()).hexdigest()}
            if key not in row['evidence_ids']: row['evidence_ids'].append(key)
    for item in data['questions']:
        if item['question'] == 'AI模型效果怎样？':
            item['answer'] = '正式独立模型仍保留研究状态。已开展多任务与集成实验；本轮固定小模型集成的弯拉应变MAE在十次分组平均下降4.51%，但没有证明四项都可靠改善。新逐指标回退仍有退步，预测不替代实测。'
        if item['question'] == '能设计任意新配方吗？':
            item['answer'] = '提供1098个待试验计算假设及组分改动对比，可保存小批配方试验安排。它们没有新增实测，不能继承父配方结论；任意新配方可靠优化仍受质量基准和验证证据限制。'
    data['research_workbench_update'] = {'updated_at': datetime.now(timezone.utc).isoformat(), 'application_version': '0.4.0',
        'requirement_ids': list(UPDATES), 'independent_material_tests': 0, 'production_model_promoted': False,
        'previous_registry': 'artifacts/research-workbench/previous-review-evidence-v3.json',
        'scope': '更新当前进度与证据；历史冻结研究文件和旧交付包保留原样。'}
    if (ROOT/'configs/creative_scope_v6.json').exists():
        sys.path.insert(0, str(ROOT))
        from scripts.apply_creative_scope_v6 import apply_scope
        data = apply_scope(data)
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print({'updated_requirements': len(UPDATES), 'evidence_files': len(data['evidence']), 'material_tests': 0})


if __name__ == '__main__':
    update()
