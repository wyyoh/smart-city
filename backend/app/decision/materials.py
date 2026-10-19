"""Material/requirement/evidence relations without inventing undisclosed ingredients."""
from copy import deepcopy

from ..services import catalog, latest_dataset, recipe_detail
from .records import digest


def material_version(recipe):
    return 'mat_' + digest({k: recipe.get(k) for k in ['id', 'dataset_id', 'source', 'product', 'gradation',
                                                      'oil_stone_ratio_pct', 'rap_nominal_pct', 'payload']})[:24]


def field(value, unit=None, reference=None, status=None):
    return {'value': value, 'unit': unit, 'reference': reference,
            'status': status or ('recorded' if value is not None else 'unknown')}


def material_scheme(recipe, demand=None):
    grade = recipe['payload'].get('gradation') or {}
    paths = []
    if demand:
        for target in demand['targets']:
            evidence = recipe['evidence'].get(target['metric']) or {}
            sources = [{'dataset_id': recipe['dataset_id'], 'sheet': label['sheet'], 'row': label['row'],
                        'cell': label['cell'], 'value': label['value'], 'raw_value': label.get('raw_value'),
                        'transform': label.get('transform')} for label in evidence.get('raw_labels', [])]
            if evidence.get('observation_id'):
                sources.append({'observation_id': evidence['observation_id'], 'reference': evidence.get('source_reference')})
            paths.append({'target_id': target['target_id'], 'metric': target['metric'],
                          'scene_rule_ids': [r['id'] for r in demand['rules']['matches']],
                          'requirement_source': target['source'], 'material_id': recipe['id'],
                          'observation_id': evidence.get('observation_id') or evidence.get('id'),
                          'observed_value': evidence.get('value'), 'sources': sources,
                          'relation': ['scene', 'requirement', 'material_version', 'observation', 'source_reference']})
    construction = recipe['payload'].get('applicability', {}).get('construction', {})
    return {
        'recipe_id': recipe['id'], 'display_id': recipe['display_id'], 'material_version': material_version(recipe),
        'dataset_id': recipe['dataset_id'], 'kind': recipe['kind'], 'parent_id': recipe['parent_id'],
        'fields': {
            'source_code': field(recipe['source'], reference='工作簿来源标识；独立料源身份尚未外部核实'),
            'product': field(recipe['product'], reference='工作簿产品标识；不推断为PG等级'),
            'gradation': field(recipe['gradation'], reference=grade.get('curve_reference')),
            'oil_stone_ratio_pct': field(recipe['oil_stone_ratio_pct'], '%', '试件所属历史操作键'),
            'binder_content_pct': field(recipe['binder_content_pct'], '%', '由油石比 r 计算 100r/(100+r)，非新增试验'),
            'rap_nominal_pct': field(recipe['rap_nominal_pct'], '%', grade.get('curve_reference'),
                                     'mass_basis_unconfirmed' if recipe['rap_nominal_pct'] is not None and grade.get('rap_mass_basis') != 'confirmed' else None),
            'modifier': field(recipe['payload'].get('modifier'), reference=recipe['payload'].get('modifier_reference')),
            'additive': field(recipe['payload'].get('additive'), reference=recipe['payload'].get('additive_reference')),
            'mixing_window': field(construction.get('mixing_window'), reference=construction.get('source')),
            'compaction_window': field(construction.get('compaction_window'), reference=construction.get('source')),
            'equipment': field(construction.get('equipment'), reference=construction.get('source')),
        },
        'components': deepcopy(grade.get('components', [])),
        'component_basis': grade.get('rap_mass_basis', 'unconfirmed'),
        'gradation_curve': {'sieves_mm': grade.get('sieves_mm', []), 'passing_pct': grade.get('curve', []),
                            'reference': grade.get('curve_reference')},
        'identity_links': deepcopy(recipe['payload'].get('identity_links', {})),
        'flags': recipe['payload'].get('flags', []), 'changes': recipe['payload'].get('changes', {}),
        'relation_paths': paths,
        'release_status': 'awaiting_engineer_review_and_testing',
        'note': '完整卡片包含已知组成与未披露字段；空白不表示未掺加。历史操作键不等同独立配方。',
    }


def material_options(session):
    dataset = latest_dataset(session)
    recipes = catalog(session)
    return {'dataset': {'id': dataset.id, 'sha256': dataset.sha256, 'revision': dataset.revision},
            'source_codes': sorted(set(r['source'] for r in recipes)),
            'gradation_families': sorted(set(r['gradation'].split('-')[0] + '-' + r['gradation'].split('-')[1]
                                            if '-' in r['gradation'] else r['gradation'] for r in recipes)),
            'product_versions': [{'id': material_version(r), 'recipe_id': r['id'],
                                   'label': f"{r['display_id']} / {r['source']} / {r['gradation']} / {r['product']} / 油石比{r['oil_stone_ratio_pct']}"}
                                  for r in recipes]}


def get_scheme(session, recipe_id, demand=None):
    return material_scheme(recipe_detail(session, recipe_id,
                                        demand['request']['context_kind'] if demand else 'project'), demand)
