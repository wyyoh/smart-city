"""Design-time features. Post-test VV/VMA and measured outcomes never enter X."""
import re
import numpy as np
from sqlmodel import select

from ..storage import Measurement, Observation, Recipe

FEATURE_VERSION = 'design-pre-1.0.0'
FEATURES = ['oil_stone_ratio_pct', 'rap_nominal_pct', 'nmas_mm', 'binder_70', 'binder_90', 'binder_110', 'binder_130'] + [f'passing_{i}' for i in range(12)]
FORBIDDEN_FEATURES = ['DS','strain','TSR','residual','VV','VMA','stability','flow','source','specimen']


def design_features(recipe):
    d = recipe if isinstance(recipe, dict) else recipe.model_dump()
    payload = d['payload']
    grade = re.search(r'AC[-－]?(\d+)', d['gradation'])
    binder = re.search(r'(70|90|110|130)#', d['product'])
    row = [d['oil_stone_ratio_pct'], d['rap_nominal_pct'], int(grade[1]) if grade else None]
    row += [int(binder is not None and binder[1] == str(n)) for n in [70,90,110,130]]
    g = payload.get('gradation')
    curve = g.get('curve') if g and 'component_curve_requires_review' not in payload['flags'] else None
    row += curve if curve and len(curve) == 12 else [None]*12
    return np.array([np.nan if v is None else float(v) for v in row])


def source_groups(recipes):
    """Union entire source codes sharing a complete, non-zero ingredient profile."""
    parents = {r.source:r.source for r in recipes}
    def root(x):
        while parents[x] != x:
            parents[x] = parents[parents[x]]
            x = parents[x]
        return x
    profiles = {}
    for r in recipes:
        grade = r.payload.get('gradation') or {}
        components = [c for c in grade.get('components',[]) if c.get('nominal_weight') and c['type'] != '矿粉']
        p = grade.get('profile_id')
        if p and len(components) >= 2:
            if p in profiles:
                a,b = sorted([root(r.source),root(profiles[p])])
                parents[b] = a
            else:
                profiles[p] = r.source
    return {r.id:'source_profile_'+root(r.source) for r in recipes}


def training_rows(session, dataset_id, metric):
    recipes = session.exec(select(Recipe).where(Recipe.dataset_id == dataset_id, Recipe.kind == 'historical')).all()
    grouping = source_groups(recipes)
    labels = {m.recipe_id:m for m in session.exec(select(Measurement).where(Measurement.dataset_id == dataset_id, Measurement.metric == metric)).all()}
    observations = session.exec(select(Observation).where(Observation.state == 'approved', Observation.data_scope == 'official',
                                                         Observation.use_for_recommendation == True, Observation.metric == metric)).all()
    reviewed = {}
    superseded = {o.payload.get('supersedes_id') for o in observations}
    for o in sorted(observations,key=lambda o:o.payload['review']['reviewed_at']):
        if o.id not in superseded:
            reviewed[o.recipe_id] = o
    X,y,groups,ids,label_provenance,excluded = [],[],[],[],[],[]
    for r in recipes:
        m, observation = labels.get(r.id), reviewed.get(r.id)
        if m is None and observation is None:
            continue
        features = design_features(r)
        if 'oil_input_requires_review' in r.payload['flags'] or np.isnan(features[:3]).any():
            excluded.append({'recipe_id':r.id,'reason':'design_input_missing_or_flagged'})
            continue
        value = observation.value if observation else m.value
        if value is None or not np.isfinite(value):
            continue
        X.append(features);y.append(value);groups.append(grouping[r.id]);ids.append(r.id)
        label_provenance.append({'recipe_id':r.id,'measurement_id':m.id if m and not observation else None,
                                 'observation_id':observation.id if observation else None,'data_scope':'official',
                                 'source_code':r.source,'gradation':r.gradation})
    return np.array(X),np.array(y),np.array(groups),ids,label_provenance,excluded
