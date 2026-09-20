"""Experimental designs in coded space (each factor in [-1, 1]).

* two-level (fractional) factorials for screening,
* face-centred central composite and Box-Behnken designs for response surfaces,
* Latin hypercube / Sobol space-filling points and maximin infill.
"""
from __future__ import annotations

import itertools

import numpy as np
from scipy.stats import qmc


def full_factorial(k: int) -> np.ndarray:
    return np.array(list(itertools.product([-1.0, 1.0], repeat=k)), dtype=float)


_GENERATORS = {   # resolution >= IV designs; generator columns as index tuples
    5: [(0, 1, 2, 3)],
    6: [(0, 1, 2), (1, 2, 3)],
    7: [(0, 1, 2), (1, 2, 3), (0, 2, 3)],
    8: [(1, 2, 3), (0, 2, 3), (0, 1, 2), (0, 1, 3)],
}


def fractional_factorial(k: int) -> np.ndarray:
    """2^(k-p) design of resolution IV or better (full factorial for k <= 4)."""
    if k <= 4:
        return full_factorial(k)
    if k in _GENERATORS:
        gens = _GENERATORS[k]
        base = full_factorial(k - len(gens))
        cols = [base] + [np.prod(base[:, list(g)], axis=1, keepdims=True) for g in gens]
        return np.hstack(cols)
    # Beyond 8 factors fall back to a two-level LHS-like corner sample.
    rng = np.random.default_rng(0)
    pts = rng.choice([-1.0, 1.0], size=(2 * k + 2, k))
    return np.unique(pts, axis=0)


def center_points(k: int, n: int) -> np.ndarray:
    return np.zeros((max(n, 0), k), dtype=float)


def ccd_face(k: int) -> np.ndarray:
    """Face-centred CCD without centre points (add them with :func:`center_points`)."""
    axial = []
    for i in range(k):
        for s in (-1.0, 1.0):
            row = np.zeros(k)
            row[i] = s
            axial.append(row)
    return np.vstack([fractional_factorial(k), np.array(axial)])


def box_behnken(k: int) -> np.ndarray:
    if k < 3:
        return ccd_face(k)
    rows = []
    for i, j in itertools.combinations(range(k), 2):
        for si, sj in itertools.product([-1.0, 1.0], repeat=2):
            row = np.zeros(k)
            row[i], row[j] = si, sj
            rows.append(row)
    return np.array(rows)


def lhs(n: int, k: int, seed: int = 0) -> np.ndarray:
    if n <= 0:
        return np.zeros((0, k))
    sampler = qmc.LatinHypercube(d=k, optimization="random-cd" if n > 1 else None, seed=seed)
    return sampler.random(n) * 2.0 - 1.0


def sobol_points(n: int, k: int, seed: int = 0) -> np.ndarray:
    m = int(np.ceil(np.log2(max(n, 2))))
    pts = qmc.Sobol(d=k, scramble=True, seed=seed).random_base2(m)[:n]
    return pts * 2.0 - 1.0


def encode(x_real: np.ndarray, lows: np.ndarray, highs: np.ndarray) -> np.ndarray:
    return 2.0 * (np.asarray(x_real, float) - lows) / (highs - lows) - 1.0


def decode(x_coded: np.ndarray, lows: np.ndarray, highs: np.ndarray) -> np.ndarray:
    return lows + (np.asarray(x_coded, float) + 1.0) * (highs - lows) / 2.0


def dedupe(new: np.ndarray, existing: np.ndarray | None, tol: float = 1e-6) -> np.ndarray:
    """Rows of ``new`` that are not already (within tol) in ``existing`` or earlier in ``new``."""
    keep = []
    pool = [] if existing is None or len(existing) == 0 else [np.asarray(existing, float)]
    for row in np.asarray(new, float):
        if pool:
            allp = np.vstack(pool)
            if np.any(np.all(np.abs(allp - row) <= tol, axis=1)):
                continue
        keep.append(row)
        pool.append(row[None, :])
    return np.array(keep) if keep else np.zeros((0, new.shape[1]))


def maximin_select(candidates: np.ndarray, n: int, existing: np.ndarray | None) -> np.ndarray:
    """Greedy maximin: pick ``n`` candidates far from existing points and each other."""
    chosen: list[np.ndarray] = []
    base = np.zeros((0, candidates.shape[1])) if existing is None else np.asarray(existing, float)
    for _ in range(min(n, len(candidates))):
        ref = np.vstack([base] + chosen) if (len(base) or chosen) else None
        if ref is None or len(ref) == 0:
            idx = 0
        else:
            d = np.min(np.linalg.norm(candidates[:, None, :] - ref[None, :, :], axis=2), axis=1)
            idx = int(np.argmax(d))
        chosen.append(candidates[idx][None, :])
        candidates = np.delete(candidates, idx, axis=0)
        if len(candidates) == 0:
            break
    return np.vstack(chosen) if chosen else np.zeros((0, base.shape[1]))


def clip_coded(x: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(x, float), -1.0, 1.0)


def coded_to_assignments(x_coded: np.ndarray, factors: list[dict]) -> dict[str, float]:
    lows = np.array([f["low"] for f in factors], float)
    highs = np.array([f["high"] for f in factors], float)
    real = decode(np.asarray(x_coded, float), lows, highs)
    out = {}
    for f, v in zip(factors, real):
        v = float(v)
        if f.get("type") == "integer":
            v = float(int(round(v)))
        else:
            v = float(np.round(v, 4))
        out[f["name"]] = v
    return out
