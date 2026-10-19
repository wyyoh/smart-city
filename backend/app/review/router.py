from fastapi import APIRouter, Depends, Body
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import Field

from ..domain.contracts_v2 import Model
from ..decision.records import append_record, digest, get_record

from .assessment import build_review
from .registry import download_evidence, overview, registry
from .reports import handbook_html, review_html
from .templates import check_external_evidence, validation_template


class ReviewRequest(Model):
    decision_id: str = Field(min_length=1)
    candidate_id: str | None = None
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{8,80}$')


def review_router(session_dependency):
    router = APIRouter(prefix='/v2/review', tags=['成果与复核'])

    @router.get('/overview')
    def read_overview(session=Depends(session_dependency)):
        return overview(session)

    @router.get('/sources')
    def read_sources():
        return {'sources': registry()['sources'], 'note': '官方公告登记不授权构造阈值用于正式工程。'}

    @router.get('/evidence/{evidence_id}')
    def read_evidence(evidence_id: str):
        _, path = download_evidence(evidence_id)
        return FileResponse(path, filename=path.name, headers={'X-Content-Type-Options': 'nosniff'})

    @router.get('/handbook.html', response_class=HTMLResponse)
    def read_handbook(session=Depends(session_dependency)):
        return handbook_html(overview(session))

    @router.get('/decisions/{decision_id}')
    def read_review(decision_id: str, candidate_id: str | None = None, session=Depends(session_dependency)):
        return build_review(session, decision_id, candidate_id)

    @router.get('/decisions/{decision_id}/report.html', response_class=HTMLResponse)
    def read_review_report(decision_id: str, candidate_id: str | None = None, session=Depends(session_dependency)):
        return review_html(build_review(session, decision_id, candidate_id))

    @router.post('/reports', status_code=201)
    def save_review(request: ReviewRequest, session=Depends(session_dependency)):
        review = build_review(session, request.decision_id, request.candidate_id)
        review['request_fingerprint'] = digest(request.model_dump())
        return append_record(session, 'decision_review', review, parent_id=request.decision_id,
                             dataset_id=review['scope']['dataset']['id'], record_id='rev_' + request.request_id)

    @router.get('/reports/{review_id}')
    def read_saved_review(review_id: str, session=Depends(session_dependency)):
        return get_record(session, review_id, 'decision_review')

    @router.get('/reports/{review_id}/report.html', response_class=HTMLResponse)
    def read_saved_report(review_id: str, session=Depends(session_dependency)):
        return review_html(get_record(session, review_id, 'decision_review'))

    @router.get('/validation-template')
    def read_validation_template():
        return validation_template()

    @router.post('/validate-input')
    def validate_input(payload: dict = Body(...)):
        return check_external_evidence(payload)

    return router
