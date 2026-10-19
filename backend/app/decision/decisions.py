from copy import deepcopy

from pydantic import Field

from ..domain.contracts_v2 import Model
from .comparison import compare_feasible
from .constraints import assess_recipe
from .materials import material_scheme
from .diagnosis import diagnose
from .test_planning import build_test_plan
from .candidate_pool import require_current_pool
from .records import append_record, get_record


class DecisionRequest(Model):
    pool_id: str = Field(min_length=1)


def run_decision(session, request: DecisionRequest):
    from .freshness import engine_fingerprint
    pool = get_record(session, request.pool_id, 'candidate_pool')
    demand = get_record(session, pool['confirmation_id'], 'demand_confirmation')
    require_current_pool(session, pool, demand)
    results = []
    for recipe in pool['candidates']:
        result = assess_recipe(recipe, demand)
        result.update({'scheme': material_scheme(recipe, demand), 'metrics': deepcopy(recipe['metrics']),
                       'evidence': deepcopy(recipe['evidence'])})
        results.append(result)
    comparison = compare_feasible(results, demand)
    results.sort(key=lambda r: (0 if r['passes_known_requirements'] else 1 if r['status'] == 'needs_evidence' else 2,
                                r.get('preference_rank', 1000), r['id']))
    return append_record(session, 'material_decision', {
        'schema_version': '2.0', 'engine_version': 'decision-2.0.0', 'engine_sha256': engine_fingerprint(), 'pool_id': pool['id'], 'pool_sha256': pool['pool_sha256'],
        'confirmation_id': demand['id'], 'confirmation_sha256': demand['sha256'], 'demand': demand,
        'scope': pool['scope'], 'pool_summary': pool['summary'], 'excluded_from_pool': pool['excluded'],
        'comparison': comparison, 'results': results,
        'diagnosis': diagnose(results, demand, pool['pool_sha256']),
        'test_plan': build_test_plan(results, demand, pool['pool_sha256']),
        'summary': {status: sum(r['status'] == status for r in results) for status in ['excluded', 'needs_evidence', 'numeric_review', 'evidence_review']},
        'release_status': 'awaiting_engineer_review_and_testing',
    }, parent_id=pool['id'], dataset_id=pool['scope']['dataset']['id'])
