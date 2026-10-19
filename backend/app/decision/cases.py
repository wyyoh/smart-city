from copy import deepcopy
import hashlib
import json

from ..settings import ROOT
from .rules import profiles


def casebook():
    path = ROOT / 'configs/case_scenarios_v2.json'
    return {**json.loads(path.read_text(encoding='utf-8')), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def demonstration_cases():
    book = casebook()
    templates = {p['id']: p['example_request'] for p in profiles()['profiles']}
    cases = []
    for case in book['cases']:
        request = deepcopy(templates[case['profile_id']])
        request.update({'name': case['title'], 'demo_case_id': case['id']})
        request['constraints']['rap_min_pct'] = case['rap_min_pct']
        cases.append({**case, 'example_request': request, 'source': '明确选择的团队构造案例；未进行工程验证'})
    return {**book, 'cases': cases}
