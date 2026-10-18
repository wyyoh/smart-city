from contextlib import asynccontextmanager
import json
import hashlib
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from .domain.contracts import ObservationInput, ReviewInput, Scenario, VariantInput
from .services import (case_cards, catalog, create_observation, create_variant, get_snapshot, html_report,
                       latest_dataset, recipe_detail, recommend, review_observation, scene_rules)
from .settings import ARTIFACTS_DIR, FRONTEND_DIST, ROOT, VERSION
from .storage import Observation, Recommendation, SourceRow, engine, initialize


def create_app(database_engine=engine):
    @asynccontextmanager
    async def lifespan(app):
        initialize(database_engine)
        yield

    app = FastAPI(title='数智选材', version=VERSION, lifespan=lifespan)

    def session_dependency():
        with Session(database_engine) as session:
            yield session

    @app.get('/health')
    def health():
        return {'status':'ok','version':VERSION}

    @app.get('/v1/catalog')
    def get_catalog(session=Depends(session_dependency)):
        ds = latest_dataset(session)
        return {'dataset':ds.model_dump(), 'recipes':catalog(session)}

    @app.get('/v1/cases')
    def get_cases():
        return case_cards()

    @app.get('/v1/rules')
    def get_rules():
        return scene_rules()

    @app.get('/v1/features')
    def get_features():
        return json.loads((ROOT/'configs/features.json').read_text(encoding='utf-8'))

    @app.get('/v1/recipes/{recipe_id}')
    def get_recipe(recipe_id: str, context_kind: str = 'project', session=Depends(session_dependency)):
        if context_kind not in ['project','constructed_demo']:
            raise HTTPException(422, '场景类型无效')
        return recipe_detail(session, recipe_id, context_kind)

    @app.post('/v1/recipes/{recipe_id}/variants', status_code=201)
    def post_variant(recipe_id: str, request: VariantInput, session=Depends(session_dependency)):
        return create_variant(session, recipe_id, request)

    @app.post('/v1/recommendations', status_code=201)
    def post_recommendation(request: Scenario, session=Depends(session_dependency)):
        return recommend(session, request)

    @app.get('/v1/recommendations/{recommendation_id}')
    def get_recommendation(recommendation_id: str, session=Depends(session_dependency)):
        return get_snapshot(session, recommendation_id)

    @app.get('/v1/recommendations/{recommendation_id}/report.html', response_class=HTMLResponse)
    def get_html(recommendation_id: str, session=Depends(session_dependency)):
        return html_report(get_snapshot(session, recommendation_id))

    @app.get('/v1/reports')
    def get_reports(session=Depends(session_dependency)):
        return [{'id':r.id, 'created_at':r.created_at,'name':r.payload['scenario']['name'],
                 'summary':r.payload['summary'],'sha256':r.payload['snapshot_sha256']}
                for r in session.exec(select(Recommendation).order_by(Recommendation.created_at.desc()).limit(50)).all()]

    @app.get('/v1/evidence/{dataset_id}/{sheet}/{row}')
    def get_evidence(dataset_id: str, sheet: str, row: int, session=Depends(session_dependency)):
        record = session.get(SourceRow, f'{dataset_id}:{sheet}:{row}')
        if not record:
            raise HTTPException(404, '原始行不存在')
        return record.model_dump()

    @app.get('/v1/quality')
    def get_quality(session=Depends(session_dependency)):
        return latest_dataset(session).model_dump()

    @app.get('/v1/observations')
    def get_observations(session=Depends(session_dependency)):
        return [o.model_dump() for o in session.exec(select(Observation).order_by(Observation.created_at.desc())).all()]

    @app.post('/v1/observations', status_code=201)
    def post_observation(request: ObservationInput, session=Depends(session_dependency)):
        return create_observation(session, request)

    @app.post('/v1/observations/{observation_id}/review')
    def post_review(observation_id: str, request: ReviewInput, session=Depends(session_dependency)):
        return review_observation(session, observation_id, request)

    @app.get('/v1/models')
    def get_models(session=Depends(session_dependency)):
        path = ARTIFACTS_DIR/'models'/'model_cards.json'
        if not path.exists():
            return {'status':'not_trained','models':[], 'message':'模型尚未训练，初筛使用历史试验记录'}
        cards = json.loads(path.read_text(encoding='utf-8'))
        ds = latest_dataset(session)
        cards['stale'] = cards.get('dataset_revision') != ds.revision or cards.get('dataset_sha256') != ds.sha256 or cards.get('dataset_id') != ds.id
        ml_root=Path(__file__).parent/'ml'
        code_hash=hashlib.sha256((ml_root/'train.py').read_bytes()+(ml_root/'features.py').read_bytes()).hexdigest()
        cards['stale'] = cards['stale'] or cards.get('code_sha256') != code_hash
        return cards

    @app.post('/v1/predictions/{recipe_id}')
    def post_prediction(recipe_id: str, session=Depends(session_dependency)):
        from .ml.predict import predict_recipe
        return predict_recipe(session, recipe_id)

    if FRONTEND_DIST.exists():
        app.mount('/', StaticFiles(directory=FRONTEND_DIST, html=True), name='frontend')
    return app


app = create_app()
