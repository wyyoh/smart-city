import numpy as np

from app.research.benchmark import grouped_splits, select_indices
from app.research.estimators import ResearchModel, TaskKernel, configurations, feature_map


def sample():
    rng = np.random.default_rng(7)
    X = rng.normal(size=(32, 19))
    Y = np.column_stack([X[:, 0]*a+rng.normal(size=32)*.05 for a in [1, -2, 3, 4]])
    Y[::3, 1] = np.nan
    return X, Y, np.repeat(np.arange(16), 2)


def test_research_common_folds_block_entire_groups():
    X, Y, groups = sample()
    tests = []
    for tr, te in grouped_splits(X, groups, 5, 20261019):
        assert not set(groups[tr]) & set(groups[te])
        tests.extend(te.tolist())
    assert sorted(tests) == list(range(len(X)))


def test_masked_task_kernel_transfer_and_diagonal_control():
    X, Y, _ = sample()
    diagonal = TaskKernel(strength=0).fit(X[:24], Y[:24])
    transfer = TaskKernel(strength=.7).fit(X[:24], Y[:24])
    assert np.linalg.eigvalsh(transfer.B).min() > 0
    assert np.count_nonzero(transfer.B-np.diag(np.diag(transfer.B))) > 0
    assert np.allclose(diagonal.B, np.eye(4))
    pred, std = transfer.predict(X[24:], return_std=True)
    assert pred.shape == std.shape == (8, 4)
    assert np.isfinite(pred).all() and (std > 0).all()
    # With an identity task kernel, changing other training tasks cannot alter task 0.
    modified = Y[:24].copy(); modified[:, 1:] *= -5
    other = TaskKernel(strength=0).fit(X[:24], modified)
    assert np.allclose(diagonal.predict(X[24:])[:, 0], other.predict(X[24:])[:, 0])


def test_research_prediction_does_not_accept_hidden_test_labels():
    X, Y, groups = sample()
    c = next(c for c in configurations() if c['family'] == 'task_kernel' and c['params']['strength'] == .3)
    fitted = ResearchModel(c).fit(X[:24], Y[:24], groups[:24])
    before = fitted.predict(X[24:])
    Y[24:] = 1e12
    assert np.array_equal(before, fitted.predict(X[24:]))


def test_research_baseline_is_selected_by_one_se_when_indistinguishable():
    configs = configurations()[:3]
    loss = np.array([[1.0]*4, [.99]*4, [1.01]*4])
    selection = select_indices(loss, np.full_like(loss, .1), configs)
    assert selection['nested_min'] == [1]*4
    assert selection['nested_one_se'] == [0]*4


def test_research_feature_maps_preserve_unknown_curves():
    X, _, _ = sample(); X[0, 7:] = np.nan
    assert np.isnan(feature_map(X, 'compact')[0, 7:14]).all()
    assert not np.isnan(feature_map(X, 'basic')).any()


def test_material_descriptors_ignore_post_test_outcomes_and_flag_unreconciled_inputs():
    from copy import deepcopy
    from app.research.advanced import material_descriptors
    curves = np.linspace(100, 2, 12)
    components = [{'nominal_weight': .6, 'curve': curves.tolist(), 'type': '粗集料', 'density_bulk': 2.6, 'density_apparent': 2.7},
                  {'nominal_weight': .4, 'curve': curves.tolist(), 'type': '粗RAP料', 'density_bulk': 2.5, 'density_apparent': 2.65}]
    r = {'payload': {'flags': [], 'gradation': {'components': components, 'curve': curves.tolist()}}}
    expected = material_descriptors(r)
    changed = deepcopy(r); changed['metrics'] = {'DS': 1e9}; changed['VV'] = -10
    assert np.array_equal(material_descriptors(changed), expected, equal_nan=True)
    assert expected[0] == .6 and expected[3] == .4
    changed['payload']['gradation']['components'][0]['nominal_weight'] = .8
    assert np.isnan(material_descriptors(changed)).all()


def test_convex_ensemble_is_nonnegative_and_normalized():
    from app.research.advanced import convex_weights
    _, Y, _ = sample()
    Y = Y[:8]
    rng = np.random.default_rng(19)
    pred = np.stack([np.nan_to_num(Y)+rng.normal(size=Y.shape)*s for s in [.1, 1, 2]])
    weights = convex_weights(pred, Y, 1)
    assert (weights >= -1e-10).all() and abs(weights.sum()-1) < 1e-8


def test_nominal_search_rejects_bad_mass_balance_and_does_not_inherit_measurements():
    from app.research.optimization import checked_components, pareto_indices
    r = {'payload': {'flags': [], 'gradation': {'components': [{'nominal_weight': 1.2, 'curve': [100]*12}], 'curve': [100]*12}}}
    assert checked_components(r)[1] == 'weights_not_a_normalized_nominal_basis'
    assert pareto_indices([[1, 2], [2, 1], [0, 0], [1, 2]]) == [0, 1, 3]
