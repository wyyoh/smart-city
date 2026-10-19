"""Explicit rule matching; no inferred numerical defaults for unknown/formal scenes."""
from copy import deepcopy
import hashlib
import json

from ..domain.contracts_v2 import DemandRequest, PerformanceRequirement
from ..settings import ROOT


RULE_PATH = ROOT / 'configs/scene_rules_v2.json'


def rulebook():
    data = json.loads(RULE_PATH.read_text(encoding='utf-8'))
    data['sha256'] = hashlib.sha256(RULE_PATH.read_bytes()).hexdigest()
    # Fail closed on an invalid rule definition rather than accepting unchecked thresholds.
    for target in data['baseline']:
        PerformanceRequirement.model_validate(target)
    for profile in data['profiles']:
        for target in profile['target_overrides']:
            PerformanceRequirement.model_validate(target)
    return data


def scene_value(scene, path):
    value = scene
    for key in path.split('.'):
        value = value.get(key) if isinstance(value, dict) else None
    return value


def profiles():
    book = rulebook()
    return {'version': book['version'], 'sha256': book['sha256'], 'policy': book['policy'], 'profiles': [
        {**p, 'example_request': DemandRequest(
            name=p['title'], context_kind='constructed_demo', scene=p['example_scene'],
            inventory={'gradation_family': 'AC-13'}, requested_metrics=['DS', 'strain', 'TSR', 'residual'],
        ).model_dump(mode='json', by_alias=True)} for p in book['profiles']
    ]}


def match_rules(request: DemandRequest):
    book = rulebook()
    scene = request.scene.model_dump(by_alias=True)
    matches, unmatched = [], []
    for profile in book['profiles']:
        evaluation = [{'field': key, 'actual': scene_value(scene, key), 'allowed': allowed,
                       'matches': scene_value(scene, key) in allowed}
                      for key, allowed in profile['conditions'].items()]
        applicable = request.context_kind == profile['context_kind'] and all(x['matches'] for x in evaluation)
        entry = {'id': profile['id'], 'title': profile['title'], 'version': profile['version'],
                 'rationale': profile['rationale'], 'conditions': evaluation}
        if applicable:
            targets = {t['metric']: deepcopy(t) for t in book['baseline']}
            history = {t['metric']: [deepcopy(t)] for t in book['baseline']}
            for replacement in profile['target_overrides']:
                old = targets[replacement['metric']]
                if (old['unit'], old['test_method'], old['conditions'], old['comparison_basis']) != (
                    replacement['unit'], replacement['test_method'], replacement['conditions'], replacement['comparison_basis']
                ):
                    raise ValueError('规则替换口径不一致，须建立独立目标，不允许自动合并')
                targets[replacement['metric']] = deepcopy(replacement)
                history[replacement['metric']].append(deepcopy(replacement))
            matches.append({**entry, 'targets': list(targets.values()), 'target_history': history,
                            'priority': profile['priority']})
        else:
            unmatched.append({**entry, 'scope_matches': request.context_kind == profile['context_kind']})
    return {'version': book['version'], 'sha256': book['sha256'], 'matches': matches, 'unmatched': unmatched}
