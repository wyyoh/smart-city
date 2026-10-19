"""Register exact research evidence bytes and verify the new internal rerun."""
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from app.research.data import dump, sha
from app.research_workbench.experiments import OUTPUT, protect_previous
from app.storage import now

protect_previous()
a = np.load(OUTPUT/'head-fallback-oof.npz')
b = np.load(OUTPUT/'reproduction/head-fallback-oof.npz')
assert set(a.files) == set(b.files) and all(np.array_equal(a[k], b[k]) for k in a.files)
folds = json.loads((OUTPUT/'head-fallback-folds.json').read_text(encoding='utf-8'))
for f in folds:
    assert not set(f['train_groups']) & set(f['test_groups'])
    assert not set(f['train_ids']) & set(f['test_ids'])
audit = json.loads((OUTPUT/'source-audit.json').read_text(encoding='utf-8'))
references = [r for issue in audit['issues'] for e in issue['entries'] for m in e['labels'].values() for r in m['references']]
assert all(r['source_row_exists'] for r in references)
dump(OUTPUT/'study-verification.json', {'created_at': now(), 'status': 'passed', 'outer_folds': 50,
    'all_predictions_and_head_acceptance_exactly_reproduced': True, 'source_references_checked': len(references),
    'group_separation': True, 'independent_material_tests': 0})

entries = {
    'candidate_pool': ('artifacts/research-v04/formulation-search.json', '全部未试验配方'),
    'row_manifest': ('artifacts/research-v04/row-manifest.json', '原始标签与来源组'),
    'benchmark': ('artifacts/research-v04/benchmark.json', '首轮完整模型结果'),
    'ensemble': ('artifacts/research-v04/advanced.json', '第二轮完整模型结果'),
    'acquisition': ('artifacts/research-v04/baseline-sensitivity.json', '空间覆盖与随机基线回放'),
    'source_audit': ('artifacts/research-workbench/source-audit.json', '原表待复核清单'),
    'head_study': ('artifacts/research-workbench/head-fallback.json', '逐指标回退实验'),
    'study_verification': ('artifacts/research-workbench/study-verification.json', '新实验复现记录'),
    'report': ('docs/research-v04-report.md', '完整研究报告'),
    'lab_handoff': ('artifacts/research-v04/laboratory-handoff.zip', '五配方送检资料包'),
    'lab_print': ('docs/research-v04-lab-handoff.html', '可打印送检方案'),
    'baseline': ('artifacts/next-phase/baseline/workbench-v01.sqlite', '冻结历史输入库'),
}
registry = {'created_at': now(), 'version': 'research-workbench-1', 'dataset': audit['dataset'],
            'prior_completion_sha256': sha(ROOT/'artifacts/research-v04/completion.json'),
            'evidence': {key: {'path': relative, 'title': title, 'sha256': sha(ROOT/relative),
                               'downloadable': key not in ['baseline', 'candidate_pool', 'row_manifest']}
                         for key, (relative, title) in entries.items()},
            'notes': ['只登记实际计算证据。', '新配方均待实测，不参与正式硬约束通过判定。']}
dump(ROOT/'configs/research_workbench_v5.json', registry)
print({'registered': len(entries), 'source_cells_checked': len(references), 'exact_rerun': True})
