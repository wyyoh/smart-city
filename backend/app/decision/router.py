from fastapi import APIRouter, Depends

from ..domain.contracts_v2 import DemandConfirmation, DemandRequest, metric_registry
from .demands import confirm_demand, resolve_demand
from .records import get_record
from .rules import profiles


def decision_router(session_dependency):
    router = APIRouter(prefix='/v2', tags=['场景选材'])

    @router.get('/metric-registry')
    def get_metrics():
        return metric_registry()

    @router.get('/scene-profiles')
    def get_profiles():
        return profiles()

    @router.post('/demand-resolutions', status_code=201)
    def post_resolution(request: DemandRequest, session=Depends(session_dependency)):
        return resolve_demand(session, request)

    @router.get('/records/{record_id}')
    def read_record(record_id: str, session=Depends(session_dependency)):
        return get_record(session, record_id)

    @router.post('/demand-resolutions/{resolution_id}/confirm', status_code=201)
    def post_confirmation(resolution_id: str, request: DemandConfirmation, session=Depends(session_dependency)):
        return confirm_demand(session, resolution_id, request)

    return router
