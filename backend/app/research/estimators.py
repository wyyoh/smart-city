"""Small-sample estimators including a masked multi-task kernel model.

The multi-task kernel uses a training-only, PSD-projected/shrunk task correlation.
It is an empirical-Bayes research implementation, not a claim to optimized MTGP.
"""
from __future__ import annotations

import numpy as np
from scipy.linalg import cho_factor, cho_solve
from sklearn.base import clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.impute import SimpleImputer
from sklearn.kernel_ridge import KernelRidge
from sklearn.linear_model import BayesianRidge, ElasticNet, Ridge
from sklearn.metrics.pairwise import rbf_kernel
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR


def feature_map(X, name):
    X = np.asarray(X, dtype=float)
    base = X[:, :7]
    if name == 'basic':
        return base.copy()
    if name == 'curve':
        return X.copy()
    if name == 'compact':
        p475, p236, p060, p015, p0075 = (X[:, i] for i in [12, 13, 15, 17, 18])
        # Only design-time algebra, without asserting an effective/reclaimed binder mass basis.
        return np.column_stack([base, p475, p236, p060, p0075, p475-p236, p236-p060,
                                p060-p015, X[:, 0]*X[:, 1]/100, X[:, 0]**2, X[:, 1]**2/100])
    raise ValueError(name)


def configurations():
    out = []
    def add(family, features='basic', **params):
        ident = f'{features}:{family}:' + ','.join(f'{k}={v}' for k, v in sorted(params.items()))
        out.append({'id': ident, 'family': family, 'features': features, 'params': params})
    add('mean'); add('median'); add('mean', group_weighted=True)
    for features in ['basic', 'curve', 'compact']:
        for alpha in [1, 10, 100, 1000]: add('ridge', features, alpha=alpha)
        add('bayes_ridge', features)
        for C in [.5, 2, 10]: add('svr', features, C=C)
        for factor in [.5, 1.5]: add('gpr', features, factor=factor, noise=.5)
        for leaf in [3, 8]: add('extra_trees', features, leaf=leaf)
        add('hist_boost', features)
        add('kernel_ridge', features)
        for alpha in [.02, .1]: add('elastic_net', features, alpha=alpha)
        for alpha in [10, 100]: add('ridge', features, alpha=alpha, log_ds=True)
    for features in ['basic', 'compact']:
        for strength in [0, .3, .7]:
            for factor in [1, 3]: add('task_kernel', features, strength=strength, factor=factor, noise=.5)
        for rank in [1, 2]:
            for alpha in [10, 100]: add('reduced_rank', features, rank=rank, alpha=alpha)
        for alpha in [10, 100]: add('ridge', features, alpha=alpha, group_weighted=True)
    assert len({c['id'] for c in out}) == len(out)
    return out


class TaskKernel:
    def __init__(self, strength=.3, factor=3, noise=.5):
        self.strength, self.factor, self.noise = strength, factor, noise

    def fit(self, X, Y):
        self.X = np.array(X)
        self.mean = np.nanmean(Y, axis=0)
        self.scale = np.maximum(np.nanstd(Y, axis=0), 1e-6)
        Z = (Y-self.mean)/self.scale
        B = np.eye(Y.shape[1])
        for a in range(Y.shape[1]):
            for b in range(a+1, Y.shape[1]):
                keep = np.isfinite(Z[:, a]) & np.isfinite(Z[:, b])
                if keep.sum() >= 8 and np.std(Z[keep, a]) > 1e-6 and np.std(Z[keep, b]) > 1e-6:
                    B[a, b] = B[b, a] = np.corrcoef(Z[keep, a], Z[keep, b])[0, 1]
        values, vectors = np.linalg.eigh(B)
        B = (vectors*np.maximum(values, .05))@vectors.T
        d = np.sqrt(np.diag(B)); B = B/d[:, None]/d[None, :]
        self.B = (1-self.strength)*np.eye(len(B)) + self.strength*B
        self.row, self.task = np.where(np.isfinite(Z))
        self.gamma = 1/(2*max(X.shape[1], 1)*self.factor**2)
        Kx = rbf_kernel(X, gamma=self.gamma)
        K = Kx[self.row[:, None], self.row[None, :]]*self.B[self.task[:, None], self.task[None, :]]
        K.flat[::len(K)+1] += self.noise + 1e-8
        self.factorization = cho_factor(K, lower=True, check_finite=False)
        self.weights = cho_solve(self.factorization, Z[self.row, self.task], check_finite=False)
        return self

    def predict(self, X, return_std=False):
        Kx = rbf_kernel(X, self.X, gamma=self.gamma)
        predictions, stds = [], []
        for t in range(len(self.B)):
            K = Kx[:, self.row]*self.B[t, self.task][None, :]
            predictions.append(self.mean[t]+self.scale[t]*(K@self.weights))
            if return_std:
                # Latent model uncertainty; not a calibrated material-test tolerance interval.
                solved = cho_solve(self.factorization, K.T, check_finite=False)
                variance = np.maximum(self.B[t, t]-np.sum(K*solved.T, axis=1), 1e-10)
                stds.append(self.scale[t]*np.sqrt(variance+self.noise))
        pred = np.array(predictions).T
        return (pred, np.array(stds).T) if return_std else pred


class ReducedRank:
    """Training-only iterative missing-target completion with reduced-rank ridge."""
    def __init__(self, rank=2, alpha=100):
        self.rank, self.alpha = rank, alpha

    def fit(self, X, Y):
        self.mean = np.nanmean(Y, axis=0)
        self.scale = np.maximum(np.nanstd(Y, axis=0), 1e-6)
        Z = (Y-self.mean)/self.scale
        missing = ~np.isfinite(Z)
        fill = np.nan_to_num(Z)
        for _ in range(12):
            self.model = Ridge(alpha=self.alpha).fit(X, fill)
            U, s, V = np.linalg.svd(self.model.coef_, full_matrices=False)
            s[self.rank:] = 0
            self.coef = (U*s)@V
            pred = X@self.coef.T+self.model.intercept_
            fill[missing] = pred[missing]
        return self

    def predict(self, X):
        return self.mean+self.scale*(X@self.coef.T+self.model.intercept_)


class ResearchModel:
    def __init__(self, config):
        self.config = config

    def fit(self, X, Y, groups=None):
        c, p = self.config, self.config['params']
        raw = feature_map(X, c['features'])
        self.imputer = SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True)
        self.scaler = StandardScaler()
        Z = self.scaler.fit_transform(self.imputer.fit_transform(raw))
        self.family = c['family']
        target = np.array(Y, copy=True)
        if p.get('log_ds'): target[:, 0] = np.log(target[:, 0])
        self.mean = np.nanmean(target, axis=0)
        self.scale = np.maximum(np.nanstd(target, axis=0), 1e-6)
        if self.family in ['task_kernel', 'reduced_rank']:
            cls = TaskKernel if self.family == 'task_kernel' else ReducedRank
            self.joint = cls(**p).fit(Z, target)
            return self
        self.models = []
        for t in range(Y.shape[1]):
            keep = np.isfinite(target[:, t])
            if not keep.any(): raise ValueError('Every training fold needs at least one observed label per task.')
            y = (target[keep, t]-self.mean[t])/self.scale[t]
            family = self.family
            if family in ['mean', 'median']: model = DummyRegressor(strategy=family)
            elif family == 'ridge': model = Ridge(alpha=p['alpha'])
            elif family == 'bayes_ridge': model = BayesianRidge()
            elif family == 'svr': model = SVR(C=p['C'], epsilon=.1)
            elif family == 'kernel_ridge': model = KernelRidge(alpha=1, kernel='rbf', gamma=1/max(Z.shape[1], 1))
            elif family == 'gpr':
                model = GaussianProcessRegressor(kernel=ConstantKernel(1)*Matern(length_scale=p['factor']*np.sqrt(Z.shape[1]), nu=1.5)+WhiteKernel(p['noise']), optimizer=None, normalize_y=False)
            elif family == 'extra_trees': model = ExtraTreesRegressor(n_estimators=64, min_samples_leaf=p['leaf'], max_features=.8, random_state=20261019, n_jobs=1)
            elif family == 'hist_boost': model = HistGradientBoostingRegressor(max_iter=60, max_leaf_nodes=5, min_samples_leaf=8, l2_regularization=10, random_state=20261019)
            elif family == 'elastic_net': model = ElasticNet(alpha=p['alpha'], l1_ratio=.5, max_iter=5000)
            else: raise ValueError(family)
            weight = None
            if p.get('group_weighted'):
                subset = np.asarray(groups)[keep]
                weight = np.array([1/np.sum(subset == g) for g in subset])
                weight /= weight.mean()
            if weight is None: model.fit(Z[keep], y)
            else: model.fit(Z[keep], y, sample_weight=weight)
            self.models.append(model)
        return self

    def predict(self, X):
        Z = self.scaler.transform(self.imputer.transform(feature_map(X, self.config['features'])))
        if hasattr(self, 'joint'): out = self.joint.predict(Z)
        else: out = np.column_stack([m.predict(Z) for m in self.models])*self.scale+self.mean
        if self.config['params'].get('log_ds'): out[:, 0] = np.exp(out[:, 0])
        return out

    def predict_with_std(self, X):
        if not isinstance(getattr(self, 'joint', None), TaskKernel):
            raise ValueError('Only the research task kernel exposes model uncertainty.')
        Z = self.scaler.transform(self.imputer.transform(feature_map(X, self.config['features'])))
        return self.joint.predict(Z, return_std=True)
