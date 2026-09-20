"""Surrogate models fitted to the nTop responses in coded factor space.

Two model families are fitted to every response and the one with the lower
leave-one-out error is used for prediction; their disagreement is used as an
uncertainty proxy for adaptive infill.

* :class:`QuadraticRSM` - classical response-surface polynomial (order chosen
  from the number of runs), with R^2, adjusted R^2 and LOO-RMSE from the hat
  matrix.
* :class:`RBFSurrogate` - thin-plate-spline radial basis interpolator with a
  linear tail (handles curvature the quadratic misses).
"""
from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field

import numpy as np
from scipy.interpolate import RBFInterpolator

log = logging.getLogger(__name__)


class QuadraticRSM:
    def __init__(self, k: int, order: str | None = None):
        self.k = k
        self.order = order          # linear | interactions | quadratic (auto if None)
        self.beta: np.ndarray | None = None
        self.terms: list[tuple[int, ...]] = []
        self.r2 = self.adj_r2 = self.loo_rmse = float("nan")
        self.n = 0

    # ---- features ---------------------------------------------------------
    def _choose_order(self, n: int) -> str:
        if self.order:
            return self.order
        k = self.k
        if n >= 1 + 2 * k + k * (k - 1) // 2 + 2:
            return "quadratic"
        if n >= 1 + k + k * (k - 1) // 2 + 2:
            return "interactions"
        return "linear"

    def _build_terms(self, order: str) -> list[tuple[int, ...]]:
        terms: list[tuple[int, ...]] = [()]
        terms += [(i,) for i in range(self.k)]
        if order in ("interactions", "quadratic"):
            terms += [(i, j) for i, j in itertools.combinations(range(self.k), 2)]
        if order == "quadratic":
            terms += [(i, i) for i in range(self.k)]
        return terms

    def features(self, X: np.ndarray) -> np.ndarray:
        X = np.atleast_2d(np.asarray(X, float))
        cols = []
        for t in self.terms:
            if not t:
                cols.append(np.ones(len(X)))
            else:
                cols.append(np.prod(X[:, list(t)], axis=1))
        return np.column_stack(cols)

    # ---- fit / predict ----------------------------------------------------
    def fit(self, X: np.ndarray, y: np.ndarray) -> "QuadraticRSM":
        X = np.atleast_2d(np.asarray(X, float))
        y = np.asarray(y, float)
        self.n = len(y)
        self.order = self._choose_order(self.n)
        self.terms = self._build_terms(self.order)
        F = self.features(X)
        p = F.shape[1]
        # tiny ridge on non-intercept terms for numerical stability
        lam = 1e-8
        A = F.T @ F + lam * np.diag([0.0] + [1.0] * (p - 1))
        self.beta = np.linalg.solve(A, F.T @ y)
        yhat = F @ self.beta
        res = y - yhat
        sst = np.sum((y - y.mean()) ** 2)
        sse = np.sum(res ** 2)
        self.r2 = 1.0 - sse / sst if sst > 0 else 1.0
        dof = self.n - p
        self.adj_r2 = 1.0 - (1.0 - self.r2) * (self.n - 1) / dof if dof > 0 else float("nan")
        if dof > 0:
            H = F @ np.linalg.solve(A, F.T)
            h = np.clip(np.diag(H), 0.0, 1.0 - 1e-9)
            self.loo_rmse = float(np.sqrt(np.mean((res / (1.0 - h)) ** 2)))
        else:
            self.loo_rmse = float("nan")
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.features(X) @ self.beta

    def coefficient_table(self, names: list[str]) -> list[dict]:
        rows = []
        for t, b in zip(self.terms, self.beta):
            if not t:
                label = "intercept"
            elif len(t) == 1:
                label = names[t[0]]
            elif t[0] == t[1]:
                label = f"{names[t[0]]}^2"
            else:
                label = f"{names[t[0]]} x {names[t[1]]}"
            rows.append({"term": label, "coef": float(b)})
        return rows


class RBFSurrogate:
    def __init__(self, k: int, smoothing: float = 1e-3):
        self.k = k
        self.smoothing = smoothing
        self.model: RBFInterpolator | None = None
        self.loo_rmse = float("nan")
        self.X: np.ndarray | None = None
        self.y: np.ndarray | None = None

    def _make(self, X: np.ndarray, y: np.ndarray) -> RBFInterpolator:
        degree = 1 if len(y) >= self.k + 2 else 0
        return RBFInterpolator(X, y, kernel="thin_plate_spline", smoothing=self.smoothing, degree=degree)

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RBFSurrogate":
        X = np.atleast_2d(np.asarray(X, float))
        y = np.asarray(y, float)
        self.X, self.y = X, y
        self.model = self._make(X, y)
        n = len(y)
        if n >= self.k + 3:
            errs = []
            for i in range(n):
                m = np.ones(n, bool)
                m[i] = False
                try:
                    mdl = self._make(X[m], y[m])
                    errs.append(float(mdl(X[i:i + 1])[0] - y[i]))
                except (ValueError, np.linalg.LinAlgError):
                    continue
            if errs:
                self.loo_rmse = float(np.sqrt(np.mean(np.square(errs))))
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model(np.atleast_2d(np.asarray(X, float)))


@dataclass
class ResponseModel:
    """Best-of-two surrogate for one response, with optional log transform."""
    key: str
    k: int
    log: bool = False
    rsm: QuadraticRSM | None = None
    rbf: RBFSurrogate | None = None
    chosen: str = "rsm"
    n: int = 0
    y_min: float = float("nan")
    y_max: float = float("nan")
    diagnostics: dict = field(default_factory=dict)

    def _fwd(self, y: np.ndarray) -> np.ndarray:
        return np.log(y) if self.log else y

    def _inv(self, z: np.ndarray) -> np.ndarray:
        return np.exp(z) if self.log else z

    def fit(self, X: np.ndarray, y: np.ndarray) -> "ResponseModel":
        X = np.atleast_2d(np.asarray(X, float))
        y = np.asarray(y, float)
        ok = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
        X, y = X[ok], y[ok]
        self.n = len(y)
        if self.log and np.any(y <= 0):
            self.log = False
        self.y_min, self.y_max = (float(y.min()), float(y.max())) if self.n else (float("nan"),) * 2
        z = self._fwd(y)
        self.rsm = QuadraticRSM(self.k).fit(X, z)
        self.rbf = None
        if self.n >= self.k + 2:
            try:
                self.rbf = RBFSurrogate(self.k).fit(X, z)
            except (ValueError, np.linalg.LinAlgError) as exc:
                log.debug("RBF fit failed for %s: %s", self.key, exc)
        rbf_loo = self.rbf.loo_rmse if self.rbf is not None else float("nan")
        if self.rbf is not None and np.isfinite(rbf_loo) and (
                not np.isfinite(self.rsm.loo_rmse) or rbf_loo < self.rsm.loo_rmse):
            self.chosen = "rbf"
        else:
            self.chosen = "rsm"
        scale = float(np.std(z)) if self.n > 1 else 1.0
        self.diagnostics = {
            "n": self.n, "log": self.log, "chosen": self.chosen, "order": self.rsm.order,
            "rsm_r2": self.rsm.r2, "rsm_adj_r2": self.rsm.adj_r2,
            "rsm_loo_rmse": self.rsm.loo_rmse, "rbf_loo_rmse": rbf_loo,
            "loo_rmse_rel": (min(x for x in (self.rsm.loo_rmse, rbf_loo) if np.isfinite(x)) / scale)
            if scale > 0 and any(np.isfinite(x) for x in (self.rsm.loo_rmse, rbf_loo)) else float("nan"),
        }
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        X = np.atleast_2d(np.asarray(X, float))
        if self.chosen == "rbf" and self.rbf is not None:
            z = self.rbf.predict(X)
        else:
            z = self.rsm.predict(X)
        y = self._inv(z)
        if self.log:
            # keep physically sensible magnitudes when extrapolating
            y = np.clip(y, self.y_min / 10.0, self.y_max * 10.0)
        return y

    def disagreement(self, X: np.ndarray) -> np.ndarray:
        """|RSM - RBF| in transformed space, normalised by response spread (0 if one model)."""
        X = np.atleast_2d(np.asarray(X, float))
        if self.rbf is None:
            return np.zeros(len(X))
        z1, z2 = self.rsm.predict(X), self.rbf.predict(X)
        spread = abs(self._fwd(np.array([self.y_max]))[0] - self._fwd(np.array([self.y_min]))[0])
        return np.abs(z1 - z2) / (spread if spread > 0 else 1.0)


def fit_response_models(X: np.ndarray, Y: dict[str, np.ndarray], k: int,
                        log_keys: list[str]) -> dict[str, ResponseModel]:
    models: dict[str, ResponseModel] = {}
    for key, y in Y.items():
        y = np.asarray(y, float)
        if np.sum(np.isfinite(y)) < max(3, k + 1):
            continue
        if np.nanstd(y) == 0:
            continue
        models[key] = ResponseModel(key, k, log=key in log_keys).fit(X, y)
    return models


class FailureModel:
    """k-nearest-neighbour estimate of the probability that nTop fails at x."""

    def __init__(self, X: np.ndarray, failed: np.ndarray, n_neighbors: int = 4):
        self.X = np.atleast_2d(np.asarray(X, float))
        self.f = np.asarray(failed, float)
        self.nn = max(1, min(n_neighbors, len(self.f)))

    def predict(self, X: np.ndarray) -> np.ndarray:
        X = np.atleast_2d(np.asarray(X, float))
        if len(self.f) == 0 or not np.any(self.f > 0):
            return np.zeros(len(X))
        d = np.linalg.norm(X[:, None, :] - self.X[None, :, :], axis=2)
        idx = np.argsort(d, axis=1)[:, :self.nn]
        w = 1.0 / (np.take_along_axis(d, idx, axis=1) + 0.05)
        return np.sum(w * self.f[idx], axis=1) / np.sum(w, axis=1)
