"""Optimisation, Pareto analysis and sensitivity on the fitted surrogates."""
from __future__ import annotations

import logging

import numpy as np
from scipy.optimize import differential_evolution, minimize
from scipy.stats import qmc

from . import objectives
from .design import coded_to_assignments, maximin_select
from .surrogate import FailureModel, ResponseModel

log = logging.getLogger(__name__)

PARETO_AXES = [  # (metric, minimise?, label)
    ("modulus_dev", True, "|E_app - target| (GPa)"),
    ("porosity", False, "Porosity (-)"),
    ("sf_fatigue", False, "Fatigue safety factor (-)"),
    ("mass_g", True, "Mass (g)"),
]


class Predictor:
    """Predicts raw responses, derived metrics and desirability at coded points."""

    def __init__(self, models: dict[str, ResponseModel], factors: list[dict], lattice: str,
                 cfg: dict, ranges: dict[str, tuple[float, float]],
                 failure: FailureModel | None = None, weights: dict[str, float] | None = None,
                 constants: dict[str, float] | None = None):
        self.models = models
        self.constants = dict(constants or {})
        self.factors = factors
        self.lattice = lattice
        self.cfg = cfg
        self.ranges = ranges
        self.failure = failure
        self.weights = weights

    def raw(self, Xc: np.ndarray) -> dict[str, np.ndarray]:
        Xc = np.atleast_2d(np.asarray(Xc, float))
        out = {k: np.full(len(Xc), v, float) for k, v in self.constants.items()}
        out.update({k: m.predict(Xc) for k, m in self.models.items()})
        return out

    def rows(self, Xc: np.ndarray) -> list[dict]:
        Xc = np.atleast_2d(np.asarray(Xc, float))
        raw = self.raw(Xc)
        pfail = self.failure.predict(Xc) if self.failure is not None else np.zeros(len(Xc))
        out = []
        for i in range(len(Xc)):
            assign = coded_to_assignments(Xc[i], self.factors)
            resp = {k: float(v[i]) for k, v in raw.items()}
            met = objectives.derive_metrics(resp, assign, self.lattice, self.cfg)
            des = objectives.desirability(met, self.cfg, self.ranges, self.weights)
            row = {**assign, **{f"resp_{k}": v for k, v in resp.items()}, **met,
                   **{f"d_{k}": v for k, v in des["components"].items()},
                   "D": des["D"], "feasible": des["feasible"], "soft": des["soft"],
                   "p_fail": float(pfail[i]),
                   "D_adj": (des["D"] if np.isfinite(des["D"]) else 0.0) * (1.0 - float(pfail[i]))}
            row["modulus_dev"] = abs(met["E_app_GPa"] - self.cfg["objectives"]["target_modulus_GPa"]) \
                if np.isfinite(met["E_app_GPa"]) else np.nan
            out.append(row)
        return out

    def objective(self, xc: np.ndarray) -> float:
        r = self.rows(np.asarray(xc, float)[None, :])[0]
        score = r["soft"] if not r["feasible"] else r["D"] * (1.0 - r["p_fail"])
        return -float(score)

    def disagreement(self, Xc: np.ndarray) -> np.ndarray:
        Xc = np.atleast_2d(np.asarray(Xc, float))
        if not self.models:
            return np.zeros(len(Xc))
        return np.mean([m.disagreement(Xc) for m in self.models.values()], axis=0)


def optimise(pred: Predictor, k: int, seed: int = 0, n_polish: int = 3) -> tuple[np.ndarray, float]:
    """Global search (differential evolution) + local polish in the coded cube."""
    bounds = [(-1.0, 1.0)] * k
    res = differential_evolution(pred.objective, bounds, seed=seed, maxiter=200, popsize=20,
                                 tol=1e-7, polish=False, init="sobol")
    best_x, best_f = np.asarray(res.x, float), float(res.fun)
    rng = np.random.default_rng(seed)
    starts = [best_x] + [np.clip(best_x + rng.normal(0, 0.15, k), -1, 1) for _ in range(n_polish - 1)]
    for x0 in starts:
        r = minimize(pred.objective, x0, method="Nelder-Mead",
                     options={"xatol": 1e-4, "fatol": 1e-7, "maxiter": 400})
        x = np.clip(r.x, -1, 1)
        f = pred.objective(x)
        if f < best_f:
            best_x, best_f = x, f
    return best_x, -best_f


def candidate_cloud(pred: Predictor, k: int, n: int = 4000, seed: int = 0) -> tuple[np.ndarray, list[dict]]:
    Xc = qmc.Sobol(d=k, scramble=True, seed=seed).random_base2(int(np.ceil(np.log2(n))))[:n] * 2 - 1
    return Xc, pred.rows(Xc)


def pareto_mask(F: np.ndarray) -> np.ndarray:
    """Non-dominated mask for objectives to *minimise* (rows with NaN are dominated)."""
    F = np.asarray(F, float)
    n = len(F)
    ok = np.all(np.isfinite(F), axis=1)
    mask = np.zeros(n, bool)
    idx = np.where(ok)[0]
    for i in idx:
        fi = F[i]
        dominated = np.any(np.all(F[idx] <= fi, axis=1) & np.any(F[idx] < fi, axis=1))
        mask[i] = not dominated
    return mask


def infill_points(pred: Predictor, existing_c: np.ndarray, k: int, n: int, seed: int = 0
                  ) -> tuple[np.ndarray, list[str]]:
    """Exploit (max D), explore (max model disagreement x distance), space-fill."""
    Xc, rows = candidate_cloud(pred, k, seed=seed)
    D = np.array([r["D_adj"] if np.isfinite(r["D_adj"]) else 0.0 for r in rows])
    soft = np.array([r["soft"] for r in rows])
    chosen, kinds = [], []
    best_x, _ = optimise(pred, k, seed=seed)
    chosen.append(best_x)
    kinds.append("exploit")
    if n >= 2:
        dist = np.min(np.linalg.norm(Xc[:, None, :] - existing_c[None, :, :], axis=2), axis=1)
        score = pred.disagreement(Xc) * dist * (0.2 + np.clip(soft, 0, 1))
        # keep the explore point away from the exploit point
        far = np.linalg.norm(Xc - best_x, axis=1) > 0.3
        cand = np.where(far, score, -1)
        chosen.append(Xc[int(np.argmax(cand))])
        kinds.append("explore")
    if n >= 3:
        # top decile by predicted desirability, then maximin among them
        top = Xc[np.argsort(-D)[: max(20, len(D) // 10)]]
        ref = np.vstack([existing_c] + [c[None, :] for c in chosen])
        extra = maximin_select(top, n - 2, ref)
        for e in extra:
            chosen.append(e)
            kinds.append("diversify")
    return np.array(chosen), kinds


def sobol_indices(pred: Predictor, k: int, n: int = 1024, seed: int = 0,
                  target: str = "D_adj") -> dict[str, np.ndarray]:
    """First-order (Saltelli 2010) and total (Jansen) Sobol indices on the surrogate."""
    n = int(2 ** np.ceil(np.log2(n)))
    A = qmc.Sobol(d=k, scramble=True, seed=seed).random(n) * 2 - 1
    B = qmc.Sobol(d=k, scramble=True, seed=seed + 1).random(n) * 2 - 1

    def f(X):
        rows = pred.rows(X)
        v = np.array([r.get(target, np.nan) for r in rows], float)
        return np.nan_to_num(v, nan=0.0)

    fA, fB = f(A), f(B)
    V = np.var(np.concatenate([fA, fB]))
    S1, ST = np.zeros(k), np.zeros(k)
    for i in range(k):
        AB = A.copy()
        AB[:, i] = B[:, i]
        fAB = f(AB)
        if V > 0:
            S1[i] = np.mean(fB * (fAB - fA)) / V
            ST[i] = 0.5 * np.mean((fA - fAB) ** 2) / V
    return {"S1": np.clip(S1, 0, 1), "ST": np.clip(ST, 0, 1), "variance": np.array([V])}


PARETO_PAIRS = {  # name: (x metric, minimise x?, y metric, minimise y?)
    "stiffness_vs_fatigue": ("modulus_dev", True, "sf_fatigue", False),
    "porosity_vs_fatigue": ("porosity", False, "sf_fatigue", False),
}


def pareto_masks(rows: list[dict]) -> dict[str, np.ndarray]:
    """Non-dominated masks (feasible designs only) for each pair in PARETO_PAIRS."""
    out = {}
    for name, (mx, minx, my, miny) in PARETO_PAIRS.items():
        F = np.array([[(r[mx] if minx else -r[mx]) if r["feasible"] else np.nan,
                       (r[my] if miny else -r[my]) if r["feasible"] else np.nan] for r in rows], float)
        out[name] = pareto_mask(F) if len(F) else np.zeros(0, bool)
    return out


def main_effects(pred: Predictor, k: int, n_grid: int = 25, metrics: list[str] | None = None,
                 base: np.ndarray | None = None) -> dict[str, dict[str, np.ndarray]]:
    """Predicted metric vs each factor, the other factors held at ``base`` (default: centre)."""
    metrics = metrics or ["E_app_GPa", "porosity", "pore_um", "sf_fatigue", "mass_g", "D_adj"]
    g = np.linspace(-1, 1, n_grid)
    base = np.zeros(k) if base is None else np.asarray(base, float)
    out: dict[str, dict[str, np.ndarray]] = {}
    for i in range(k):
        X = np.tile(base, (n_grid, 1))
        X[:, i] = g
        rows = pred.rows(X)
        out[str(i)] = {"grid": g, **{m: np.array([r.get(m, np.nan) for r in rows], float) for m in metrics}}
    return out


def interaction_effects(pred: Predictor, k: int, metric: str = "D_adj", n_grid: int = 15,
                        base: np.ndarray | None = None) -> dict[tuple[int, int], dict[str, np.ndarray]]:
    g = np.linspace(-1, 1, n_grid)
    base = np.zeros(k) if base is None else np.asarray(base, float)
    out = {}
    for i in range(k):
        for j in range(k):
            if i == j:
                continue
            curves = []
            for lvl in (-1.0, 0.0, 1.0):
                X = np.tile(base, (n_grid, 1))
                X[:, i] = g
                X[:, j] = lvl
                rows = pred.rows(X)
                curves.append(np.array([r.get(metric, np.nan) for r in rows], float))
            out[(i, j)] = {"grid": g, "levels": np.array([-1.0, 0.0, 1.0]), "curves": np.array(curves)}
    return out


def response_grid(pred: Predictor, k: int, i: int, j: int, fixed: np.ndarray, n: int = 41
                  ) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    gi, gj = np.meshgrid(np.linspace(-1, 1, n), np.linspace(-1, 1, n), indexing="xy")
    X = np.tile(np.asarray(fixed, float), (n * n, 1))
    X[:, i] = gi.ravel()
    X[:, j] = gj.ravel()
    return gi, gj, pred.rows(X)


def weight_robustness(components: dict[str, dict[str, float]], base_w: dict[str, float],
                      n: int = 500, seed: int = 0, concentration: float = 30.0) -> dict[str, np.ndarray]:
    """Rank frequency of each variant's optimum under Dirichlet-perturbed weights."""
    names = list(components)
    keys = [k for k in base_w if base_w[k] > 0]
    rng = np.random.default_rng(seed)
    alpha = np.array([base_w[k] for k in keys]) / sum(base_w[k] for k in keys) * concentration
    ranks = np.zeros((len(names), len(names)))
    for _ in range(n):
        w = dict(zip(keys, rng.dirichlet(alpha)))
        scores = np.array([objectives.overall_from_components(components[nm], w) for nm in names])
        scores = np.nan_to_num(scores, nan=-1.0)
        order = np.argsort(-scores)
        for r, idx in enumerate(order):
            ranks[idx, r] += 1
    return {"names": np.array(names), "rank_freq": ranks / n}
