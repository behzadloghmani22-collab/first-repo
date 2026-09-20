"""From raw nTop outputs to clinical metrics and a single desirability score.

Optimality for a lumbar interbody fusion cage is defined here as a weighted
Derringer-Suich desirability built from:

* **apparent modulus** close to bone / PEEK (~3 GPa) to limit stress shielding
  and subsidence while keeping enough support for fusion,
* **porosity** 60-75 % and **pore size** 500-800 um for vascularised bone
  in-growth (hard limits 40-90 % and 300-1000 um),
* **strength**: yield safety factor >= 2 at the 2 kN peak load (hard) and a
  fatigue margin at the 1.2 kN cyclic design load,
* **manufacturability**: strut (sheet) thickness >= 0.3 mm for LPBF Ti-6Al-4V,
* light **mass** and high **surface area** as weak tie-breakers.

Every threshold and weight is read from ``doe_config.json`` so the definition
can be argued about in the open.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from .config import normalise_name
from .discover import match_name

METRIC_LABELS = {
    "porosity": "Porosity (-)",
    "relative_density": "Relative density (-)",
    "mass_g": "Mass (g)",
    "stiffness_N_mm": "Axial stiffness (N/mm)",
    "E_app_GPa": "Apparent modulus (GPa)",
    "max_stress_MPa": "Max von Mises stress at design load (MPa)",
    "max_stress_peak_MPa": "Max von Mises stress at peak load (MPa)",
    "sf_yield": "Yield safety factor at peak load (-)",
    "sf_fatigue": "Fatigue safety factor (-)",
    "pore_um": "Pore size (um)",
    "strut_mm": "Strut / sheet thickness (mm)",
    "surface_area_mm2": "Surface area (mm^2)",
    "specific_surface_1_mm": "Specific surface (mm^2/mm^3)",
    "lattice_volume_mm3": "Solid volume (mm^3)",
    "max_displacement_mm": "Max displacement (mm)",
}

COMPONENT_LABELS = {
    "modulus": "Modulus match", "porosity": "Porosity", "pore_size": "Pore size",
    "sf_fatigue": "Fatigue margin", "sf_yield": "Yield margin", "strut": "Printability",
    "mass": "Low mass", "surface_area": "Surface area",
}

_UNIT = {
    "volume": {"mm^3": 1.0, "mm3": 1.0, "cm^3": 1e3, "cm3": 1e3, "m^3": 1e9, "m3": 1e9,
               "in^3": 16387.064, "in3": 16387.064, "l": 1e6, "ml": 1e3},
    "area": {"mm^2": 1.0, "mm2": 1.0, "cm^2": 1e2, "cm2": 1e2, "m^2": 1e6, "m2": 1e6,
             "in^2": 645.16, "in2": 645.16},
    "length": {"mm": 1.0, "m": 1e3, "cm": 10.0, "um": 1e-3, "micron": 1e-3, "microns": 1e-3,
               "in": 25.4, "inch": 25.4, "nm": 1e-6},
    "stress": {"mpa": 1.0, "pa": 1e-6, "kpa": 1e-3, "gpa": 1e3, "n/mm^2": 1.0, "n/mm2": 1.0,
               "psi": 6.894757e-3, "ksi": 6.894757, "n/m^2": 1e-6},
    "mass": {"g": 1.0, "kg": 1e3, "mg": 1e-3, "lb": 453.592, "lbs": 453.592, "t": 1e6},
    "stiffness": {"n/mm": 1.0, "n/m": 1e-3, "kn/mm": 1e3, "n/um": 1e3, "lbf/in": 0.175127},
    "none": {"": 1.0, "-": 1.0, "%": 0.01, "percent": 0.01},
}
_KIND = {"lattice_volume": "volume", "envelope_volume": "volume", "surface_area": "area",
         "contact_area": "area", "max_displacement": "length", "pore_size": "length",
         "min_thickness": "length", "max_stress": "stress", "mass": "mass",
         "stiffness": "stiffness", "porosity": "none", "relative_density": "none",
         "safety_factor": "none"}
_CANON = {"volume": "mm^3", "area": "mm^2", "length": "mm", "stress": "mpa", "mass": "g",
          "stiffness": "n/mm", "none": ""}


def _norm_unit(u: Any) -> str:
    s = str(u or "").strip().lower()
    s = (s.replace("³", "^3").replace("²", "^2").replace("μ", "u").replace("µ", "u")
         .replace(" ", "").replace("**", "^"))
    return s


def to_canonical(value: Any, units: Any, key: str) -> float:
    """Convert an nTop output to the canonical unit for its response key."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float("nan")
    kind = _KIND.get(key, "none")
    table = _UNIT[kind]
    u = _norm_unit(units)
    if u in table:
        v = v * table[u]
    elif kind == "none" and u == "%":
        v = v / 100.0
    # otherwise assume the canonical unit already
    return v


def map_outputs(raw: dict[str, dict], cfg: dict) -> tuple[dict[str, float], dict[str, str], dict[str, float]]:
    """Match nTop output names to response keys.

    Returns (values in canonical units, mapping key -> nTop name, unmatched numeric outputs).
    """
    names = list(raw)
    used: set[str] = set()
    values: dict[str, float] = {}
    mapping: dict[str, str] = {}
    for r in cfg["responses"]:
        cands = [n for n in names if n not in used]
        m = match_name(cands, r["key"].replace("_", " "), r.get("aliases", []))
        if m is None:
            continue
        val = raw[m].get("value")
        if isinstance(val, (list, tuple)) and len(val) == 1:
            val = val[0]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
        values[r["key"]] = to_canonical(val, raw[m].get("units", ""), r["key"])
        mapping[r["key"]] = m
        used.add(m)
    extra: dict[str, float] = {}
    for n in names:
        if n in used:
            continue
        v = raw[n].get("value")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            extra[n] = float(v)
    return values, mapping, extra


def factor_role(name: str) -> str:
    n = normalise_name(name)
    if "cell" in n or "period" in n:
        return "cell"
    if any(w in n for w in ("shell", "rim", "wall", "frame", "skin", "outer")):
        return "shell"
    if any(w in n for w in ("strut", "thick", "beam", "diameter", "sheet", "rib")):
        return "strut"
    return "other"


def derive_metrics(resp: dict[str, float], factors: dict[str, float], lattice: str,
                   cfg: dict) -> dict[str, float]:
    """Compute the clinical metrics from canonical responses + factor settings."""
    g, ph = cfg["geometry"], cfg["physics"]
    nan = float("nan")
    get = lambda k: float(resp.get(k, nan)) if resp.get(k) is not None else nan  # noqa: E731
    A = float(g.get("footprint_area_mm2") or nan)
    H = float(g.get("height_mm") or nan)
    V_env = get("envelope_volume")
    if not np.isfinite(V_env):
        V_env = float(g.get("envelope_volume_mm3") or (A * H if np.isfinite(A * H) else nan))
    V_lat = get("lattice_volume")
    porosity = get("porosity")
    if not np.isfinite(porosity):
        rd = get("relative_density")
        if np.isfinite(rd):
            porosity = 1.0 - rd
        elif np.isfinite(V_lat) and np.isfinite(V_env) and V_env > 0:
            porosity = 1.0 - V_lat / V_env
    if np.isfinite(porosity) and porosity > 1.0:      # given in percent
        porosity /= 100.0
    mass = get("mass")
    if not np.isfinite(mass) and np.isfinite(V_lat):
        mass = V_lat * float(ph["density_g_cm3"]) / 1000.0
    F = float(ph["design_load_N"])
    Fpk = float(ph["peak_load_N"])
    k = get("stiffness")
    disp = get("max_displacement")
    if not np.isfinite(k) and np.isfinite(disp) and disp > 0:
        k = F / disp
    E_app = k * H / A / 1000.0 if all(np.isfinite([k, H, A])) and A > 0 else nan
    sigma = get("max_stress")
    sigma_pk = sigma * Fpk / F if np.isfinite(sigma) else nan
    sf_y = float(ph["yield_MPa"]) / sigma_pk if np.isfinite(sigma_pk) and sigma_pk > 0 else nan
    sf_f = float(ph["fatigue_MPa"]) / sigma if np.isfinite(sigma) and sigma > 0 else nan
    sf_given = get("safety_factor")
    if np.isfinite(sf_given) and not np.isfinite(sf_y):
        sf_y = sf_given
    # factor roles
    cell = strut = nan
    for name, val in factors.items():
        role = factor_role(name)
        if role == "cell" and not np.isfinite(cell):
            cell = float(val)
        elif role == "strut" and not np.isfinite(strut):
            strut = float(val)
    min_t = get("min_thickness")
    strut_eff = min_t if np.isfinite(min_t) else strut
    pore = get("pore_size")                    # canonical mm
    pore_um = pore * 1000.0 if np.isfinite(pore) else nan
    if np.isfinite(pore_um) and pore_um < 5.0:  # value was already in um
        pore_um = pore * 1.0
    pore_estimated = False
    if not np.isfinite(pore_um) and np.isfinite(cell) and np.isfinite(strut):
        kappa = g.get("pore_kappa", {})
        kap = kappa.get(lattice, kappa.get("default", 0.58))
        pore_um = max(kap * cell - strut, 0.0) * 1000.0
        pore_estimated = True
    area = get("surface_area")
    spec_surf = area / V_lat if np.isfinite(area) and np.isfinite(V_lat) and V_lat > 0 else nan
    return {
        "porosity": porosity, "relative_density": 1.0 - porosity if np.isfinite(porosity) else nan,
        "mass_g": mass, "stiffness_N_mm": k, "E_app_GPa": E_app,
        "max_stress_MPa": sigma, "max_stress_peak_MPa": sigma_pk,
        "sf_yield": sf_y, "sf_fatigue": sf_f, "pore_um": pore_um,
        "pore_estimated": float(pore_estimated), "strut_mm": strut_eff,
        "surface_area_mm2": area, "specific_surface_1_mm": spec_surf,
        "lattice_volume_mm3": V_lat, "max_displacement_mm": disp,
        "cell_mm": cell,
    }


# --------------------------------------------------------------------------- #
# Desirability
# --------------------------------------------------------------------------- #
def d_window(x: float, hard_lo: float, band_lo: float, band_hi: float, hard_hi: float) -> float:
    if not np.isfinite(x):
        return float("nan")
    if x <= hard_lo or x >= hard_hi:
        return 0.0
    if band_lo <= x <= band_hi:
        return 1.0
    if x < band_lo:
        return (x - hard_lo) / (band_lo - hard_lo)
    return (hard_hi - x) / (hard_hi - band_hi)


def d_larger(x: float, lo: float, good: float) -> float:
    if not np.isfinite(x):
        return float("nan")
    if x < lo:
        return 0.0
    if x >= good:
        return 1.0
    return (x - lo) / (good - lo)


def d_relative(x: float, best: float, worst: float, floor: float = 0.25, larger: bool = False) -> float:
    """Soft, campaign-relative desirability in [floor, 1] (never a hard cut)."""
    if not np.isfinite(x) or not np.isfinite(best) or not np.isfinite(worst) or best == worst:
        return 1.0
    t = (x - worst) / (best - worst) if larger else (worst - x) / (worst - best)
    t = float(np.clip(t, 0.0, 1.0))
    return floor + (1.0 - floor) * t


def desirability(m: dict[str, float], cfg: dict, ranges: dict[str, tuple[float, float]] | None = None,
                 weights: dict[str, float] | None = None) -> dict[str, Any]:
    """Return components, overall D (geometric mean), feasibility and a soft score."""
    o = cfg["objectives"]
    w = dict(o["weights"])
    if weights:
        w.update(weights)
    ranges = ranges or {}
    comp: dict[str, float] = {}
    t = o["target_modulus_GPa"]
    band, hard = o["modulus_band_GPa"], o["modulus_hard_GPa"]
    comp["modulus"] = d_window(m.get("E_app_GPa", np.nan), hard[0], band[0], band[1], hard[1])
    pb, ph_ = o["porosity_band"], o["porosity_hard"]
    comp["porosity"] = d_window(m.get("porosity", np.nan), ph_[0], pb[0], pb[1], ph_[1])
    sb, sh = o["pore_band_um"], o["pore_hard_um"]
    comp["pore_size"] = d_window(m.get("pore_um", np.nan), sh[0], sb[0], sb[1], sh[1])
    comp["sf_yield"] = d_larger(m.get("sf_yield", np.nan), o["sf_yield_min"], o["sf_yield_good"])
    comp["sf_fatigue"] = d_larger(m.get("sf_fatigue", np.nan), o["sf_fatigue_min"], o["sf_fatigue_good"])
    comp["strut"] = d_larger(m.get("strut_mm", np.nan), o["min_strut_mm"], o["good_strut_mm"])
    lo, hi = ranges.get("mass_g", (np.nan, np.nan))
    comp["mass"] = d_relative(m.get("mass_g", np.nan), lo, hi)
    lo, hi = ranges.get("surface_area_mm2", (np.nan, np.nan))
    comp["surface_area"] = d_relative(m.get("surface_area_mm2", np.nan), hi, lo, larger=True)
    # components with missing data are dropped from the mean (reported as NaN)
    used = {k: v for k, v in comp.items() if np.isfinite(v) and w.get(k, 0) > 0}
    wsum = sum(w[k] for k in used)
    if not used or wsum <= 0:
        D = float("nan")
    elif any(v <= 0 for v in used.values()):
        D = 0.0
    else:
        D = math.exp(sum(w[k] * math.log(v) for k, v in used.items()) / wsum)
    # Soft score: keeps a gradient inside the infeasible region for the optimiser.
    viol = 0.0
    for k, v in used.items():
        if v <= 0:
            viol += w[k] / wsum
    hard_missing = [k for k in ("modulus", "porosity", "pore_size", "sf_yield") if k not in used]
    feasible = bool(used) and all(v > 0 for v in used.values())
    soft = D if feasible else -viol - 0.01 * _violation_distance(m, o)
    return {"D": D, "components": comp, "feasible": feasible, "soft": soft,
            "missing": hard_missing}


def _violation_distance(m: dict[str, float], o: dict) -> float:
    """Normalised distance to the feasible window (for the soft score only)."""
    d = 0.0
    def outside(x, lo, hi, scale):
        if not np.isfinite(x):
            return 0.0
        if x < lo:
            return (lo - x) / scale
        if x > hi:
            return (x - hi) / scale
        return 0.0
    d += outside(m.get("E_app_GPa", np.nan), *o["modulus_hard_GPa"], o["target_modulus_GPa"])
    d += outside(m.get("porosity", np.nan), *o["porosity_hard"], 0.2)
    d += outside(m.get("pore_um", np.nan), *o["pore_hard_um"], 300.0)
    d += outside(m.get("sf_yield", np.nan), o["sf_yield_min"], 1e9, 1.0)
    d += outside(m.get("sf_fatigue", np.nan), o["sf_fatigue_min"], 1e9, 1.0)
    return d


def overall_from_components(comp: dict[str, float], weights: dict[str, float]) -> float:
    used = {k: v for k, v in comp.items() if np.isfinite(v) and weights.get(k, 0) > 0}
    if not used:
        return float("nan")
    if any(v <= 0 for v in used.values()):
        return 0.0
    wsum = sum(weights[k] for k in used)
    return math.exp(sum(weights[k] * math.log(v) for k, v in used.items()) / wsum)
