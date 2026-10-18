import hashlib
import json
import joblib
import numpy as np
from fastapi import HTTPException
from sklearn.neighbors import NearestNeighbors
from sqlmodel import Session

from .features import design_features, FEATURE_VERSION
from ..domain.contracts import CORE_METRICS
from ..services import latest_dataset, require_recipe
from ..settings import ARTIFACTS_DIR


def applicability(features, training_X):
    low=np.nanmin(training_X[:,:3],axis=0);high=np.nanmax(training_X[:,:3],axis=0)
    return not np.isnan(features[:3]).any() and bool(np.all(features[:3]>=low)&np.all(features[:3]<=high))


def predict_recipe(session:Session,recipe_id):
    recipe=require_recipe(session,recipe_id)
    ds=latest_dataset(session)
    if recipe.dataset_id != ds.id:
        raise HTTPException(409,'此方案属于其他数据版本，不能混用当前模型')
    cards_path=ARTIFACTS_DIR/'models'/'model_cards.json'
    if not cards_path.exists():
        raise HTTPException(503,'模型尚未训练，历史初筛不受影响')
    cards=json.loads(cards_path.read_text(encoding='utf-8'))
    from pathlib import Path
    code_hash=hashlib.sha256(Path(__file__).with_name('train.py').read_bytes()+Path(__file__).with_name('features.py').read_bytes()).hexdigest()
    if cards.get('code_sha256')!=code_hash:
        raise HTTPException(409,'模型代码指纹已改变，请重新训练')
    if cards['dataset_sha256']!=ds.sha256 or cards['dataset_revision']!=ds.revision or cards.get('dataset_id')!=ds.id:
        raise HTTPException(409,'数据版本已改变，模型需要重新训练验证')
    features=design_features(recipe)
    missing=np.isnan(features[:3]).any()
    if missing or 'oil_input_requires_review' in recipe.payload['flags'] or features[3:7].sum()==0:
        return {'recipe_id':recipe.id,'status':'abstained','reason':'设计输入缺失、用油待复核或沥青名义牌号未见','predictions':{}}
    predictions={}
    for metric in CORE_METRICS:
        path=ARTIFACTS_DIR/'models'/f'{metric}.joblib'
        if not path.exists():
            raise HTTPException(503,f'{metric}模型文件缺失；可继续使用历史初筛')
        if cards['artifact_hashes'].get(path.name)!=hashlib.sha256(path.read_bytes()).hexdigest():
            raise HTTPException(409,'模型文件指纹不匹配，请重新训练')
        artifact=joblib.load(path)
        if artifact['feature_version']!=FEATURE_VERSION:
            raise HTTPException(409,'特征版本不一致')
        supported=applicability(features,artifact['training_X'])
        # Compare distances in the fitted design-feature space, using leave-one-out training distances.
        pipe=artifact['model'];transform=pipe[:-1]
        Z=transform.transform(artifact['training_X']);z=transform.transform(features.reshape(1,-1))
        nn=NearestNeighbors(n_neighbors=2).fit(Z)
        reference=float(np.quantile(nn.kneighbors(Z)[0][:,1],.95))
        distance=float(nn.kneighbors(z,n_neighbors=1)[0][0,0])
        near=distance<=max(reference,1e-9)
        item={'value':float(pipe.predict(features.reshape(1,-1))[0]),'family':artifact['family'],
              'state':'research_reference' if supported and near else 'outside_observed_design_support',
              'within_numeric_range':supported,'nearest_design_distance':distance,'training_distance_p95':reference,
              'interval':None, 'historical_identity_seen':recipe.kind=='historical'}
        calibrated=artifact.get('calibrated')
        if calibrated and supported and near and applicability(features,calibrated['training_X']):
            center=float(calibrated['model'].predict(features.reshape(1,-1))[0]);q=calibrated['radius']
            item['interval']={'lower':center-q,'upper':center+q,'center':center,
                'nominal_coverage':.9,'family':calibrated['family'],'state':'research_group_calibrated',
                'note':'另一个仅用训练组拟合的模型给出区间；需组可交换性，不代表工程验收或多指标联合保证。'}
        predictions[metric]=item
    return {'recipe_id':recipe.id,'status':'research_only','predictions':predictions,
            'note':'全量拟合点预测；历史身份可能参与过训练。模型值不替代实测，不用于硬约束通过判定。'}
