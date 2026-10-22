import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, Response

from .contracts import AdjustmentPreview, CaseRunRequest, DraftRequest, LockedField, PreferenceRequest
from .printing import record_html
from .service import cases, exploration, history, preference_comparison, preview_adjustment, run_case, save_draft, saved_record


def creative_router(session_dependency):
    router = APIRouter(prefix='/v5/design', tags=['案例与协同设计'])

    @router.get('/cases')
    def get_cases():
        return cases()

    @router.post('/cases/{case_id}/runs', status_code=201)
    def post_case(case_id: str, request: CaseRunRequest, session=Depends(session_dependency)):
        return run_case(session, case_id, request)

    @router.post('/preferences')
    def post_preference(request: PreferenceRequest, session=Depends(session_dependency)):
        return preference_comparison(session, request)

    @router.post('/decisions/{decision_id}/adjustment-preview')
    def post_adjustment_preview(decision_id: str, request: AdjustmentPreview, session=Depends(session_dependency)):
        return preview_adjustment(session, decision_id, request)

    @router.get('/explorations/{decision_id}/{parent_id}')
    def get_exploration(decision_id: str, parent_id: str, supported_only: bool = True,
                        locked_fields: list[LockedField] = Query(default=[]), session=Depends(session_dependency)):
        return exploration(session, decision_id, parent_id, supported_only, locked_fields)

    @router.post('/drafts', status_code=201)
    def post_draft(request: DraftRequest, session=Depends(session_dependency)):
        return save_draft(session, request)

    @router.get('/history')
    def get_history(kind: str = 'design_draft', session=Depends(session_dependency)):
        return history(session, kind)

    @router.get('/records/{record_id}')
    def get_saved(record_id: str, session=Depends(session_dependency)):
        return saved_record(session, record_id)

    @router.get('/records/{record_id}/export.json', response_class=Response)
    def export_saved(record_id: str, session=Depends(session_dependency)):
        record = saved_record(session, record_id)
        return Response(json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False)+'\n', media_type='application/json',
                        headers={'Content-Disposition': f'attachment; filename="{record["id"]}.json"',
                                 'X-Content-Type-Options': 'nosniff'})

    @router.get('/records/{record_id}/print.html', response_class=HTMLResponse)
    def print_saved(record_id: str, session=Depends(session_dependency)):
        return record_html(saved_record(session, record_id))

    return router
