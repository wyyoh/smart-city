from fastapi import APIRouter, Depends
from sqlmodel import select
from fastapi.responses import HTMLResponse

from ..domain.contracts_v2 import DemandConfirmation, DemandRequest, metric_registry
from .demands import confirm_demand, resolve_demand
from .records import DecisionRecord, get_record
from .rules import profiles
from .materials import get_scheme, material_options
from .candidate_pool import PoolRequest, freeze_pool
from .decisions import DecisionRequest, run_decision
from .differences import get_difference
from .freshness import decision_freshness
from .model_view import model_validation_view
from .integration import (FeedbackReview, FieldFeedback, LabFeedback, SelectionRequest, UpstreamRequest,
                          receive_upstream, return_selection, review_feedback, submit_feedback)
from .cases import demonstration_cases
from .reports import html_report


def decision_router(session_dependency):
    router = APIRouter(prefix='/v2', tags=['场景选材'])

    @router.get('/metric-registry')
    def get_metrics():
        return metric_registry()

    @router.get('/scene-profiles')
    def get_profiles():
        return profiles()

    @router.get('/benchmark-cases')
    def get_demonstration_cases():
        return demonstration_cases()

    @router.post('/demand-resolutions', status_code=201)
    def post_resolution(request: DemandRequest, session=Depends(session_dependency)):
        return resolve_demand(session, request)

    @router.get('/records/{record_id}')
    def read_record(record_id: str, session=Depends(session_dependency)):
        return get_record(session, record_id)

    @router.get('/material-options')
    def get_options(session=Depends(session_dependency)):
        return material_options(session)

    @router.get('/materials/{recipe_id}')
    def read_material(recipe_id: str, confirmation_id: str | None = None, session=Depends(session_dependency)):
        demand = get_record(session, confirmation_id, 'demand_confirmation') if confirmation_id else None
        return get_scheme(session, recipe_id, demand)

    @router.post('/demand-resolutions/{resolution_id}/confirm', status_code=201)
    def post_confirmation(resolution_id: str, request: DemandConfirmation, session=Depends(session_dependency)):
        return confirm_demand(session, resolution_id, request)

    @router.post('/candidate-pools', status_code=201)
    def post_pool(request: PoolRequest, session=Depends(session_dependency)):
        return freeze_pool(session, request)

    @router.post('/decisions', status_code=201)
    def post_decision(request: DecisionRequest, session=Depends(session_dependency)):
        return run_decision(session, request)

    @router.get('/decisions')
    def list_decisions(session=Depends(session_dependency)):
        records = session.exec(select(DecisionRecord).where(DecisionRecord.kind == 'material_decision').order_by(DecisionRecord.created_at.desc()).limit(50)).all()
        return [{'id': r.id, 'created_at': r.created_at, 'name': r.payload['demand']['request']['name'],
                 'diagnosis': r.payload['diagnosis']['status'], 'sha256': r.payload['sha256']} for r in records]

    @router.get('/decision-diff')
    def read_difference(before_id: str, after_id: str, session=Depends(session_dependency)):
        return get_difference(session, before_id, after_id)

    @router.get('/decisions/{decision_id}/freshness')
    def read_freshness(decision_id: str, session=Depends(session_dependency)):
        return decision_freshness(session, decision_id)

    @router.get('/decisions/{decision_id}/models/{candidate_id}')
    def read_model_view(decision_id: str, candidate_id: str, session=Depends(session_dependency)):
        return model_validation_view(session, decision_id, candidate_id)

    @router.get('/decisions/{decision_id}/report.html', response_class=HTMLResponse)
    def read_html_report(decision_id: str, session=Depends(session_dependency)):
        return html_report(get_record(session, decision_id, 'material_decision'))

    @router.post('/upstream-requests', status_code=201)
    def post_upstream(request: UpstreamRequest, session=Depends(session_dependency)):
        return receive_upstream(session, request)

    @router.post('/upstream-requests/{upstream_id}/selection', status_code=201)
    def post_selection(upstream_id: str, request: SelectionRequest, session=Depends(session_dependency)):
        return return_selection(session, upstream_id, request)

    @router.post('/lab-feedback', status_code=201)
    def post_lab_feedback(request: LabFeedback, session=Depends(session_dependency)):
        return submit_feedback(session, request)

    @router.post('/field-feedback', status_code=201)
    def post_field_feedback(request: FieldFeedback, session=Depends(session_dependency)):
        return submit_feedback(session, request)

    @router.post('/feedback/{feedback_id}/review', status_code=201)
    def post_feedback_review(feedback_id: str, request: FeedbackReview, session=Depends(session_dependency)):
        return review_feedback(session, feedback_id, request)

    return router
