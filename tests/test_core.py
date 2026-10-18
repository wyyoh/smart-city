import hashlib
import math

from pydantic import ValidationError
import pytest
from sqlmodel import Session, select

from app.domain.calculations import binder_content_pct, mineral_blend
from app.domain.contracts import ObservationInput, Target, satisfies
from app.importer import import_workbook, verify_layout
from app.settings import ROOT
from app.storage import Measurement, Recipe


def test_import_provenance_counts_and_idempotency(database):
    source = ROOT/'再生沥青混合料实验数据表.xlsx'
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    with Session(database) as session:
        ds, created = import_workbook(source, session)
        assert not created
        assert ds.summary['specimen_total'] == 2052
        assert ds.summary['gradation_blocks'] == 68
        assert ds.summary['source_codes'] == 44
        assert ds.summary['operational_recipes'] == 180
        assert len(session.exec(select(Recipe)).all()) == 180
        assert ds.summary['suspected_mean_DS_groups'] == 21
        assert len(ds.summary['formula_errors']) == 2
        assert len(ds.summary['curve_mismatches']) == 52
        tsr = session.exec(select(Measurement).where(Measurement.metric == 'TSR')).all()
        assert sum(len(m.payload['raw_labels']) for m in tsr) == 87
        assert all(70 < m.value < 100 for m in tsr)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_strict_threshold_null_and_zero():
    assert not satisfies(8000, Target(metric='DS', value=8000))
    assert satisfies(0, Target(metric='DS', value=0, operator='>='))
    assert not satisfies(float('nan'), Target(metric='DS', value=0))
    assert satisfies(3, Target(metric='VV', operator='between', value=3, upper=5))
    with pytest.raises(ValidationError):
        Target(metric='DS', value=1, operator='between', upper=0)


def test_oil_and_mass_basis():
    assert binder_content_pct(5) == pytest.approx(100*5/105)
    with pytest.raises(ValueError):
        mineral_blend([.5,.5], [[100,20],[80,0]], mass_basis='unconfirmed')
    assert mineral_blend([.5,.5], [[100,20],[80,0]], mass_basis='mineral_mass') == [90,10]
    with pytest.raises(ValueError):
        mineral_blend([.5,.4], [[100,20],[80,0]], mass_basis='mineral_mass')


@pytest.mark.parametrize('case_id,expected', [('C1',['R1']),('C2',['R4']),('C3',['R7']),('C4',['R5']),('C5',[])])
def test_five_cases_real_import(client, case_id, expected):
    case = next(c for c in client.get('/v1/cases').json() if c['id'] == case_id)
    result = client.post('/v1/recommendations', json=case['scenario'])
    assert result.status_code == 201, result.text
    snapshot = result.json()
    assert [r['display_id'] for r in snapshot['results'] if r['passes_targets']] == expected
    if not expected:
        assert snapshot['empty_reason']
    assert client.get('/v1/recommendations/'+snapshot['id']).json() == snapshot
    assert 'snapshot_sha256' in snapshot


def test_label_aggregation_and_raw_row(client):
    r = client.get('/v1/recipes/R7').json()
    assert r['evidence']['DS']['n_recorded'] == 3
    assert r['evidence']['DS']['n_independent_assumed'] == 2
    assert r['evidence']['DS']['suspected_derived_mean']
    tsr = r['evidence']['TSR']['raw_labels'][0]
    assert tsr['value'] == pytest.approx(tsr['raw_value']*100)
    row = client.get(f'/v1/evidence/{r["dataset_id"]}/{tsr["sheet"]}/{tsr["row"]}').json()
    assert row['payload']['cells'][tsr['cell']]['value'] == tsr['raw_value']


def test_variant_invalidates_parent_measurements(client):
    r = client.post('/v1/recipes/R1/variants',json={'oil_stone_ratio_pct':5.6,'note':'演示微调'}).json()
    assert r['kind'] == 'variant'
    assert r['metrics'] == {}
    assert r['evidence'] == {}
    case = client.get('/v1/cases').json()[0]['scenario']
    case['candidate_ids'] = [r['id']]
    snapshot = client.post('/v1/recommendations', json=case).json()
    assert snapshot['results'][0]['status'] == 'needs_test'
    assert snapshot['recommended_for_review'] == []


def observation(client, **kwargs):
    data = dict(recipe_id='R1',metric='DS',value=12000,unit='次/mm',test_group='demo-1',method='演示试验方法',
                conditions='演示条件，不作为真实试验', source_reference='tests/synthetic-local-fixture', sample_count=2, idempotency_key='demo-key-0001',data_scope='demo')
    data.update(kwargs)
    return data


def test_observation_review_idempotency_scope_and_immutable_report(client):
    case = client.get('/v1/cases').json()[0]['scenario']
    initial = client.post('/v1/recommendations',json=case).json()
    data = observation(client)
    r = client.post('/v1/observations',json=data)
    assert r.status_code == 201
    oid = r.json()['id']
    assert client.post('/v1/observations',json=data).json()['id'] == oid
    assert client.post('/v1/observations',json=dict(data,value=13000)).status_code == 409
    review = dict(state='approved',reviewer='本地演示审核',note='测试审核流程',conditions_confirmed=False,use_for_recommendation=True)
    assert client.post(f'/v1/observations/{oid}/review',json=review).status_code == 422
    review['conditions_confirmed'] = True
    assert client.post(f'/v1/observations/{oid}/review',json=review).status_code == 200
    assert client.post(f'/v1/observations/{oid}/review',json=review).status_code == 409
    assert client.get('/v1/recipes/R1').json()['metrics']['DS'] == pytest.approx(9327.303846153834)
    assert client.get('/v1/recipes/R1?context_kind=constructed_demo').json()['metrics']['DS'] == 12000
    assert client.get('/v1/recommendations/'+initial['id']).json() == initial
    assert client.post('/v1/observations',json=data).json()['id'] == oid
    assert client.post('/v1/observations',json=observation(client,idempotency_key='correction-0002',value=11000,supersedes_id=oid)).status_code == 201


def test_html_escaping_and_unavailable_constraints(client):
    case = client.get('/v1/cases').json()[0]['scenario']
    case['name'] = '<script>alert(1)</script>'
    case['budget'] = 100
    snapshot = client.post('/v1/recommendations',json=case).json()
    assert snapshot['recommended_for_review'] == []
    assert 'unit_cost' in snapshot['results'][0]['missing_metrics']
    html = client.get('/v1/recommendations/'+snapshot['id']+'/report.html').text
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    case['candidate_ids'] = ['does-not-exist']
    assert client.post('/v1/recommendations',json=case).status_code == 422
