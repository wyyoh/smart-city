"""Small-budget nested group benchmark with explicit split and label manifests."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import time

import joblib
import numpy as np
import sklearn
from sklearn.base import clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlmodel import Session
from threadpoolctl import threadpool_limits

from .features import FEATURES, FEATURE_VERSION, training_rows
from ..domain.contracts import CORE_METRICS
from ..services import latest_dataset
from ..settings import ARTIFACTS_DIR
from ..storage import engine, initialize, now

SEED = 20261018
THRESHOLDS = {'DS':800,'strain':2000,'TSR':75,'residual':85}
SCENARIO_THRESHOLDS = {'DS':[800,6000,8000],'strain':[2000,2200,2500],'TSR':[75,85,90],'residual':[85,90]}


def candidates(include_gpr=True):
    estimators = [('dummy',DummyRegressor(strategy='mean')),
        ('nearest',KNeighborsRegressor(n_neighbors=3,weights='distance')),
        ('nearest',KNeighborsRegressor(n_neighbors=7,weights='distance')),
        *[('ridge',Ridge(alpha=a)) for a in [1,10,100]],
        *[('random_forest',RandomForestRegressor(n_estimators=80,max_depth=d,min_samples_leaf=3,random_state=SEED,n_jobs=1)) for d in [4,None]]]
    if include_gpr:
        # Fixed kernel hyperparameters keep this comparison deterministic and modest in budget.
        estimators.append(('gpr',GaussianProcessRegressor(kernel=ConstantKernel(1)*Matern(length_scale=2,nu=1.5)+WhiteKernel(.15),
                                                        optimizer=None,normalize_y=True,random_state=SEED)))
    return [(name,Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)),
                            ('scale',StandardScaler()),('model',model)])) for name,model in estimators]


def scores(y,pred,metric):
    return {'mae':float(mean_absolute_error(y,pred)), 'rmse':float(np.sqrt(mean_squared_error(y,pred))),
            'r2':float(r2_score(y,pred)), 'threshold_errors':int(np.sum((y>THRESHOLDS[metric]) != (pred>THRESHOLDS[metric]))),
            'n':len(y), 'threshold_errors_by_target':{str(t):int(np.sum((y>t)!=(pred>t))) for t in SCENARIO_THRESHOLDS[metric]}}


def select_models(X,y,groups,options):
    splits = list(GroupKFold(n_splits=min(3,len(set(groups)))).split(X,y,groups))
    losses=[]
    for name,pipeline in options:
        residuals=[]
        for train,valid in splits:
            model=clone(pipeline).fit(X[train],y[train])
            residuals.extend(abs(y[valid]-model.predict(X[valid])))
        losses.append(float(np.mean(residuals)))
    best = {}
    for i,(name,_) in enumerate(options):
        if name not in best or losses[i] < losses[best[name]]:
            best[name]=i
    return int(np.argmin(losses)),best,losses


def calibration_experiment(X,y,groups,options,metric,output):
    unique=np.array(sorted(set(groups)))
    if len(unique)<30:
        return {'status':'分组数量不足，未发布校准区间','n_groups':len(unique)},None
    rng=np.random.default_rng(SEED)
    rng.shuffle(unique)
    cal_groups,test_groups,train_groups=unique[:12],unique[12:20],unique[20:]
    tr=np.flatnonzero(np.isin(groups,train_groups));ca=np.flatnonzero(np.isin(groups,cal_groups));te=np.flatnonzero(np.isin(groups,test_groups))
    chosen,_,_=select_models(X[tr],y[tr],groups[tr],options)
    name,pipeline=options[chosen]
    model=clone(pipeline).fit(X[tr],y[tr])
    errors=abs(y[ca]-model.predict(X[ca]))
    # Maximum residual per held-out group, not exchangeability of repeated specimens.
    group_errors=[float(max(errors[groups[ca]==g])) for g in cal_groups]
    rank=math.ceil((len(cal_groups)+1)*.9)
    q=float(sorted(group_errors)[rank-1])
    pred=model.predict(X[te]); covered=abs(y[te]-pred)<=q
    group_covered=[bool(np.all(covered[groups[te]==g])) for g in test_groups]
    details={'status':'研究性90%分组校准区间；需满足组可交换性假设', 'family':name,
        'n_train':len(tr),'n_calibration':len(ca),'n_test':len(te),'n_calibration_groups':len(cal_groups),
        'n_test_groups':len(test_groups),'coverage':float(np.mean(covered)),
        'group_coverage':float(np.mean(group_covered)),'width':2*q,'radius':q,
        'selection_scope':'仅训练组内层选择；校准组与测试组未参与拟合或选择',
        'train_groups':train_groups.tolist(),'calibration_groups':cal_groups.tolist(),'test_groups':test_groups.tolist(),
        'test_point_scores':scores(y[te],pred,metric),
        'limitations':['仅一个预先固定的分组留出，测试组仅8组，覆盖率不稳定。',
                       '来源代码并非已确认的物理料源，不能据此保证工程覆盖率。',
                       '四个指标分别校准，不提供四指标同时满足目标的联合概率。']}
    return details,{'model':model,'radius':q,'family':name,'training_X':X[tr]}


def run_benchmark(session, output:Path=ARTIFACTS_DIR/'models', include_gpr=True):
    output.mkdir(parents=True,exist_ok=True)
    ds=latest_dataset(session)
    options=candidates(include_gpr)
    manifest={'created_at':now(),'seed':SEED,'dataset_id':ds.id,'dataset_sha256':ds.sha256,'dataset_revision':ds.revision,
        'feature_version':FEATURE_VERSION,'features':FEATURES,'sklearn_version':sklearn.__version__, 'importer_version':ds.importer_version,
        'protocol':'按来源代码及完整非零原料曲线族阻断；外层5折估计，内层3折选择模型与参数。指标按操作配方聚合，重复试件不跨折。物理料源身份待确认。',
        'status':'research_only','models':[], 'code_sha256':hashlib.sha256((Path(__file__).read_bytes()+Path(__file__).with_name('features.py').read_bytes())).hexdigest(),
        'budget':{'max_seconds_per_metric':120,'candidate_pipelines':len(options),'forest_trees':80}}
    for metric in CORE_METRICS:
        start=time.perf_counter()
        X,y,groups,ids,provenance,excluded=training_rows(session,ds.id,metric)
        n_groups=len(set(groups))
        if n_groups<5:
            raise ValueError(f'{metric}分组不足，不能按当前协议训练')
        predictions={name:np.full(len(y),np.nan) for name,_ in options}
        selected_pred=np.full(len(y),np.nan)
        folds=[]
        for fold,(tr,te) in enumerate(GroupKFold(n_splits=5).split(X,y,groups)):
            if time.perf_counter()-start > 120:
                raise RuntimeError(f'{metric}超过单指标120秒预算，保留已有历史初筛功能')
            chosen,best,losses=select_models(X[tr],y[tr],groups[tr],options)
            for name,index in best.items():
                predictions[name][te]=clone(options[index][1]).fit(X[tr],y[tr]).predict(X[te])
            selected_pred[te]=predictions[options[chosen][0]][te]
            folds.append({'fold':fold,'train_ids':[ids[i] for i in tr],'test_ids':[ids[i] for i in te],
                'train_groups':sorted(set(groups[tr])),'test_groups':sorted(set(groups[te])),
                'selected_family':options[chosen][0], 'inner_mae':losses[chosen],
                'family_parameter_indices':best,'test_scores':scores(y[te],selected_pred[te],metric)})
        chosen,_,_=select_models(X,y,groups,options)
        name,pipeline=options[chosen]
        fitted=clone(pipeline).fit(X,y)
        calibration,calibrated=calibration_experiment(X,y,groups,options,metric,output)
        payload={'metric':metric,'model':fitted,'family':name,'training_X':X,'training_groups':groups,
                 'feature_version':FEATURE_VERSION,'features':FEATURES,'dataset_sha256':ds.sha256,
                 'dataset_revision':ds.revision,'calibrated':calibrated}
        joblib.dump(payload,output/f'{metric}.joblib')
        card={'metric':metric,'n':len(y),'groups':n_groups,'excluded':excluded,'selected_family':name,
              'outer_selected':scores(y,selected_pred,metric),
              'models':{family:scores(y,pred,metric) for family,pred in predictions.items()},
              'folds':folds,'label_provenance':provenance,'calibration':calibration,
              'oof_predictions':[{'recipe_id':ids[i],'group':groups[i],'actual':float(y[i]),'selected':float(selected_pred[i]),
                                   'by_model':{family:float(pred[i]) for family,pred in predictions.items()}} for i in range(len(y))],
              'training_seconds':round(time.perf_counter()-start,3),
              'caveats':['外层结果衡量内层选择流程；全量重拟合模型没有独立实测性能保证。',
                         '标签来自企业工作簿及审核正式回流，试验条件尚需确认；演示回流不参与训练。',
                         '未知名义RAP计量基准与跨来源差异限制外推，预测不参与历史硬约束的通过判定。']}
        card['deployment_status']='research_only'
        card['outer_selection_beats_dummy_mae']=card['outer_selected']['mae']<card['models']['dummy']['mae']
        if not card['outer_selection_beats_dummy_mae']:
            card['caveats'].insert(0,'当前选择流程的外层MAE未优于均值基线，尚无稳定泛化改进证据。')
        manifest['models'].append(card)
        print(json.dumps({'metric':metric,'n':len(y),'groups':n_groups,'family':name,'outer_selected':card['outer_selected'],
                          'seconds':card['training_seconds']},ensure_ascii=False),flush=True)
    manifest['artifact_hashes']={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in output.glob('*.joblib')}
    (output/'model_cards.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--without-gpr',action='store_true')
    args=parser.parse_args()
    initialize(engine)
    with threadpool_limits(limits=1),Session(engine) as session:
        run_benchmark(session,include_gpr=not args.without_gpr)
