"""Keep measured values, each metric's own OOF prediction and fitted research values distinct."""
import hashlib
import json
import math
from pathlib import Path

from fastapi import HTTPException

from ..domain.contracts_v2 import metric_registry
from ..ml.predict import predict_recipe
from ..settings import ARTIFACTS_DIR
from .records import get_record


def model_validation_view(session, decision_id, candidate_id):
    decision = get_record(session, decision_id, 'material_decision')
    row = next((r for r in decision['results'] if r['id'] == candidate_id), None)
    if row is None:
        raise HTTPException(404, '候选不属于此冻结决策')
    path = ARTIFACTS_DIR / 'models/model_cards.json'
    if not path.exists():
        return {'status': 'unavailable', 'reason': '没有已保存模型验证档案', 'metrics': [], 'research_prediction_reason': '模型不可用'}
    cards = json.loads(path.read_text(encoding='utf-8'))
    ml = Path(__file__).parents[1] / 'ml'
    code_sha = hashlib.sha256((ml / 'train.py').read_bytes() + (ml / 'features.py').read_bytes()).hexdigest()
    version_matches = cards.get('code_sha256') == code_sha and all(cards.get('dataset_' + k) == decision['scope']['dataset'][k]
                                                                    for k in ['id', 'sha256', 'revision'])
    point, point_reason = {}, None
    try:
        prediction = predict_recipe(session, candidate_id)
        point = prediction.get('predictions', {})
        if not point:
            point_reason = prediction.get('reason', '当前输入无法预测')
    except HTTPException as error:
        point_reason = error.detail
    metrics = []
    for card in cards['models']:
        metric = card['metric']
        oof = next((p for p in card['oof_predictions'] if p['recipe_id'] == candidate_id), None)
        fold = next((f for f in card['folds'] if candidate_id in f['test_ids']), None)
        measured = row['metrics'].get(metric)
        eligible = version_matches and row['scheme']['kind'] == 'historical' and oof and fold and oof['group'] not in fold['train_groups'] and measured is not None and math.isclose(oof['actual'], measured, abs_tol=1e-9)
        calibration = card['calibration']
        metrics.append({'metric': metric, 'unit': metric_registry()['metrics'][metric]['unit'], 'measured': measured,
                        'measured_kind': 'frozen_historical_or_reviewed_record' if measured is not None else 'missing',
                        'own_fold_oof': {'value': oof['selected'], 'actual': oof['actual'], 'fold': fold['fold'],
                                         'group': oof['group'], 'selected_family_in_fold': fold['selected_family']} if eligible else None,
                        'oof_unavailable_reason': None if eligible else '此材料未参加该指标离折验证，或输入/标签/代码版本与档案不符',
                        'research_fitted_prediction': point.get(metric), 'n': card['n'], 'groups': card['groups'],
                        'selected_family_full_fit': card['selected_family'], 'outer_selected': card['outer_selected'],
                        'dummy': card['models']['dummy'], 'beats_dummy_mae': card['outer_selection_beats_dummy_mae'],
                        'calibration': {key: calibration[key] for key in ['status', 'family', 'n_calibration_groups', 'n_test_groups', 'group_coverage', 'width', 'limitations']}})
    return {'status': 'research_only', 'decision_id': decision_id, 'candidate_id': candidate_id,
            'model_cards_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'versions_match_snapshot': version_matches,
            'metrics': metrics, 'research_prediction_reason': point_reason,
            'note': '四项指标使用各自分组折，不能称共享验证；研究预测和区间均不参与硬要求判定，不提供联合达标概率。'}
