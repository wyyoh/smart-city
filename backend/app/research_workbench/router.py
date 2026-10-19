import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import Field

from ..decision.records import get_record
from ..domain.contracts_v2 import Model
from .service import artifact, candidate_detail, candidate_list, overview, plan_html, registry, save_plan, verified_path


class ResearchFilters(Model):
    source: str = Field(default='', max_length=80)
    kind: Literal['all', 'oil_ratio', 'nominal_blend'] = 'all'
    supported_only: bool = True
    q: str = Field(default='', max_length=100)


class ResearchPlanRequest(Model):
    title: str = Field(default='待确认配方试验计划', min_length=1, max_length=120)
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{8,80}$')
    scope_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    filters: ResearchFilters = Field(default_factory=ResearchFilters)
    budget: int = Field(default=3, ge=1, le=8)
    pinned_ids: list[str] = Field(default_factory=list, max_length=8)


def research_router(session_dependency):
    router = APIRouter(prefix='/v4/research', tags=['配方研究与试验安排'])

    @router.get('/overview')
    def get_overview(session=Depends(session_dependency)):
        return overview(session)

    @router.get('/candidates')
    def get_candidates(source: str = Query(default='', max_length=80), kind: Literal['all', 'oil_ratio', 'nominal_blend'] = 'all',
                       supported_only: bool = True, q: str = Query(default='', max_length=100),
                       offset: int = Query(default=0, ge=0), limit: int = Query(default=12, ge=1, le=50)):
        return candidate_list({'source': source, 'kind': kind, 'supported_only': supported_only, 'q': q}, offset, limit)

    @router.get('/candidates/{candidate_id}')
    def get_candidate(candidate_id: str):
        return candidate_detail(candidate_id)

    @router.get('/audit')
    def get_audit():
        return artifact('source_audit')

    @router.get('/evidence/{evidence_id}')
    def get_evidence(evidence_id: str):
        entry = registry()['evidence'].get(evidence_id)
        if not entry or not entry['downloadable']: raise HTTPException(404, '该研究资料不提供下载。')
        _, path, _ = verified_path(evidence_id)
        return FileResponse(path, filename=path.name, headers={'X-Content-Type-Options': 'nosniff'})

    @router.post('/plans', status_code=201)
    def create_plan(request: ResearchPlanRequest, session=Depends(session_dependency)):
        return save_plan(session, request)

    @router.get('/plans/{plan_id}')
    def get_plan(plan_id: str, session=Depends(session_dependency)):
        return get_record(session, plan_id, 'research_test_plan')

    @router.get('/plans/{plan_id}/export.json', response_class=Response)
    def export_plan(plan_id: str, session=Depends(session_dependency)):
        plan = get_record(session, plan_id, 'research_test_plan')
        return Response(json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False)+'\n', media_type='application/json',
                        headers={'Content-Disposition': f'attachment; filename="{plan["id"]}.json"',
                                 'X-Content-Type-Options': 'nosniff'})

    @router.get('/plans/{plan_id}/print.html', response_class=HTMLResponse)
    def get_plan_print(plan_id: str, session=Depends(session_dependency)):
        return plan_html(get_record(session, plan_id, 'research_test_plan'))

    return router
