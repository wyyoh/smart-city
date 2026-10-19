import importlib.util

from app.settings import ROOT


def test_five_constructed_cases_preserve_strong_baseline_and_report_escaping(client):
    spec=importlib.util.spec_from_file_location('compare_cases_v2',ROOT/'scripts/compare_cases_v2.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for case in client.get('/v2/benchmark-cases').json()['cases']:
        report,decision=module.execute_case(client,case)
        assert report['strong_B1_agrees_on_feasible_set']
        assert len(decision['results'])==84
        html=client.get(f"/v2/decisions/{decision['id']}/report.html")
        assert html.status_code==200 and decision['sha256'] in html.text
        assert '独立试验' in html.text
    case['example_request']['name']='<script>alert(1)</script>'
    _,decision=module.execute_case(client,case)
    html=client.get(f"/v2/decisions/{decision['id']}/report.html").text
    assert '<script>alert(1)</script>' not in html and '&lt;script&gt;' in html
