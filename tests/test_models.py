import json
import joblib
import numpy as np
import pytest
from sqlmodel import Session

from app.ml.features import FEATURES, FORBIDDEN_FEATURES, design_features, source_groups, training_rows
from app.services import create_observation, create_variant, latest_dataset, recipe_detail, require_recipe, review_observation
from app.domain.contracts import ObservationInput, ReviewInput, VariantInput
from app.settings import ARTIFACTS_DIR


def test_features_exclude_post_test_outcomes(client):
    recipe=client.get('/v1/recipes/R1').json()
    before=design_features(recipe)
    recipe['metrics']={key:-1000 for key in FORBIDDEN_FEATURES}
    assert np.array_equal(before,design_features(recipe),equal_nan=True)
    assert not set(FEATURES)&set(FORBIDDEN_FEATURES)


def test_model_splits_and_artifacts():
    cards=json.loads((ARTIFACTS_DIR/'models/model_cards.json').read_text(encoding='utf-8'))
    for card in cards['models']:
        assert len(card['oof_predictions'])==card['n']
        assert len({p['recipe_id'] for p in card['oof_predictions']})==card['n']
        all_tests=[]
        for fold in card['folds']:
            assert not set(fold['train_groups'])&set(fold['test_groups'])
            assert not set(fold['train_ids'])&set(fold['test_ids'])
            all_tests+=fold['test_ids']
        assert len(all_tests)==len(set(all_tests))==card['n']
        assert set(card['models'])=={'dummy','nearest','ridge','random_forest','gpr'}
        cal=card['calibration']
        assert not set(cal['train_groups'])&(set(cal['calibration_groups'])|set(cal['test_groups']))
        assert not set(cal['calibration_groups'])&set(cal['test_groups'])
        model=joblib.load(ARTIFACTS_DIR/'models'/f'{card["metric"]}.joblib')
        assert model['feature_version']==cards['feature_version']


def test_no_demo_label_or_variant_enters_training(database):
    with Session(database) as s:
        ds=latest_dataset(s)
        before=training_rows(s,ds.id,'DS')
        o=create_observation(s,ObservationInput(recipe_id='R1',metric='DS',value=99999,unit='次/mm',test_group='demo',method='demo',conditions='demo',source_reference='tests/synthetic-local-fixture', sample_count=2,idempotency_key='model-demo-key',data_scope='demo'))
        review_observation(s,o['id'],ReviewInput(state='approved',reviewer='demo',note='demo',conditions_confirmed=True,use_for_recommendation=True))
        create_variant(s,'R1',VariantInput(oil_stone_ratio_pct=5.6,note='new hypothesis'))
        after=training_rows(s,ds.id,'DS')
        assert np.array_equal(before[1],after[1])
        assert before[3]==after[3]


def test_offline_saved_model_matches_prediction(client):
    recipe=client.get('/v1/recipes/R1').json()
    response=client.post('/v1/predictions/'+recipe['id'],json={})
    assert response.status_code==200,response.text
    for metric,item in response.json()['predictions'].items():
        model=joblib.load(ARTIFACTS_DIR/'models'/f'{metric}.joblib')
        expected=model['model'].predict(design_features(recipe).reshape(1,-1))[0]
        assert item['value']==pytest.approx(expected)
        assert item['historical_identity_seen']


def test_prediction_abstains_unknown_binder_and_stale_revision(client):
    variant=client.post('/v1/recipes/R1/variants',json={'product':'未知新产品','note':'需要新材料证据'}).json()
    assert client.post('/v1/predictions/'+variant['id'],json={}).json()['status']=='abstained'
    o=client.post('/v1/observations',json={'recipe_id':'R1','metric':'DS','value':9000,'unit':'次/mm','test_group':'formal-test','method':'method','conditions':'conditions','source_reference':'tests/synthetic-local-fixture','sample_count':2,'idempotency_key':'stale-model-test','data_scope':'official'}).json()
    client.post('/v1/observations/'+o['id']+'/review',json={'state':'approved','reviewer':'tester','note':'test','conditions_confirmed':True,'use_for_recommendation':True})
    assert client.post('/v1/predictions/R1',json={}).status_code==409
