"""Reproduce C5 certificates in a disposable database; production is never opened writable."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'tests'))

sys.path.insert(0, str(ROOT / 'scripts'))
from v2_isolation import copy_baseline

from fastapi.testclient import TestClient
from app.main import create_app
from app.storage import make_engine
from app.decision.diagnosis import verify_certificate
from app.decision.differences import compare_decisions
from decision_helpers import run_case


def main():
    with tempfile.TemporaryDirectory(prefix='material-v2-') as temporary:
        path = Path(temporary) / 'verification.sqlite'
        copy_baseline(path)
        engine = make_engine(path)
        try:
            with TestClient(create_app(engine)) as client:
                decision = run_case(client)
                validations = [verify_certificate(cert, decision['results'], decision['pool_sha256'], decision['confirmation_sha256'], decision['demand'])
                               for cert in decision['diagnosis']['certificates']]
                assert len(validations) == 4 and all(v['valid'] for v in validations)
                report = {'case': 'C5', 'context_kind': 'constructed_demo', 'scope': decision['scope'],
                          'pool_sha256': decision['pool_sha256'], 'confirmation_sha256': decision['confirmation_sha256'],
                          'candidate_count': len(decision['results']), 'diagnosis': decision['diagnosis'], 'validations': validations,
                          'note': '完整数值子池回放；不是物理不可行结论或工程准确率。'}
                output = ROOT / 'artifacts/next-phase/conflict-certificates/C5.json'
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                print(json.dumps({'case': 'C5', 'candidates': len(decision['results']), 'verified_certificates': len(validations)}, ensure_ascii=False))
                before, after = run_case(client, 'C1'), run_case(client, 'C2')
                changed = compare_decisions(before, after)
                unchanged = compare_decisions(before, run_case(client, 'C1'))
                assert changed['changed'] and not unchanged['changed']
                output = ROOT / 'artifacts/next-phase/week3-what-if/differences.json'
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps({'C1_to_C2': changed, 'C1_repeated': unchanged}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                print(json.dumps({'changed_target_metrics': [c['metric'] for c in changed['target_changes']], 'identical_conditions_changed': unchanged['changed']}))
        finally:
            engine.dispose()


if __name__ == '__main__':
    main()
