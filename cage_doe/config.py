"""Configuration: defaults, loading and validation.

Everything an engineer might want to change lives in ``doe_config.json``.
Unknown keys are preserved so the file can carry notes.  Names of nTop inputs
and outputs are matched *case- and punctuation-insensitively* against the
``aliases`` lists below, so the defaults work for most naming conventions; the
discovery report (``report/discovery.md``) shows exactly what was matched.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "project": {
        "name": "Lumbar fusion cage - lattice DOE and optimisation",
        # Folder that holds the four .ntop variants (searched recursively).
        "root": ".",
        # Results folder created inside root.
        "results_dirname": "DOE_results",
        # Path to ntopcl.exe; null = auto-detect (env NTOPCL_EXE, then common
        # install locations).  Use mock/mock_ntopcl.py for dry runs.
        "ntopcl_exe": r"C:\Program Files\nTopology\nTopology\ntopcl.exe",
        "extra_ntopcl_args": [],
        "timeout_s": 3600,
        # nTopCL holds one licence seat: keep 1 unless you know you can run more.
        "workers": 1,
        "random_seed": 42,
        # Re-use runs that already exist in results/runs (safe to re-launch).
        "resume": True,
        # Re-run designs whose nTop run failed earlier (normally deterministic, so off).
        "retry_failed": False,
    },
    # "auto" discovers every .ntop under root.  Or list explicitly:
    # [{"name": "Octet", "ntop": "octet/cage.ntop", "template": "octet/input.json",
    #   "lattice": "octet"}]
    "variants": "auto",
    "exclude_patterns": ["backup", "_old", "~$", ".bak"],   # path components to skip (results folder is always skipped)
    # ---- Factors swept by the DOE (nTop *Input* blocks) ----------------------
    "factors": [
        {"name": "Cell Size", "units": "mm", "low": 1.5, "high": 4.0,
         "type": "scalar",
         "aliases": ["cell size", "unit cell size", "unit cell", "cell",
                     "lattice cell size", "cell length", "period", "cell_size"]},
        {"name": "Strut Thickness", "units": "mm", "low": 0.3, "high": 0.9,
         "type": "scalar",
         "aliases": ["strut thickness", "thickness", "beam thickness",
                     "lattice thickness", "strut diameter", "beam diameter",
                     "strut", "rib thickness", "sheet thickness",
                     "wall thickness lattice", "lattice wall thickness"]},
        {"name": "Shell Thickness", "units": "mm", "low": 0.5, "high": 1.5,
         "type": "scalar",
         "aliases": ["shell thickness", "shell", "rim thickness", "rim",
                     "wall thickness", "outer wall", "frame thickness",
                     "skin thickness"]},
    ],
    # Inputs held constant (name -> value) in every run; names are matched
    # with the same alias logic.  Leave empty to keep the template values.
    "fixed_inputs": {},
    # Text/file inputs that must be unique per run (e.g. an export path).
    "per_run_path_inputs": [],
    # ---- Responses read from nTop *Output* blocks -----------------------------
    "responses": [
        {"key": "lattice_volume", "units": "mm^3",
         "aliases": ["volume", "lattice volume", "total volume", "cage volume",
                     "part volume", "solid volume", "final volume", "vol"]},
        {"key": "envelope_volume", "units": "mm^3",
         "aliases": ["envelope volume", "bounding volume", "design volume",
                     "design space volume", "solid cage volume", "cad volume",
                     "reference volume"]},
        {"key": "mass", "units": "g",
         "aliases": ["mass", "weight", "part mass"]},
        {"key": "surface_area", "units": "mm^2",
         "aliases": ["surface area", "area", "total surface area",
                     "lattice surface area"]},
        {"key": "porosity", "units": "-",
         "aliases": ["porosity", "void fraction", "pore fraction"]},
        {"key": "relative_density", "units": "-",
         "aliases": ["relative density", "volume fraction", "density ratio",
                     "solid fraction", "fill fraction"]},
        {"key": "max_stress", "units": "MPa",
         "aliases": ["max von mises", "max von mises stress", "von mises",
                     "von mises stress", "max stress", "maximum stress",
                     "peak stress", "stress max", "max vm stress",
                     "max principal stress"]},
        {"key": "max_displacement", "units": "mm",
         "aliases": ["max displacement", "displacement", "max disp",
                     "maximum displacement", "deflection", "max deflection",
                     "displacement max", "total displacement"]},
        {"key": "stiffness", "units": "N/mm",
         "aliases": ["stiffness", "axial stiffness", "cage stiffness"]},
        {"key": "pore_size", "units": "um",
         "aliases": ["pore size", "pore diameter", "pore", "mean pore size",
                     "max inscribed sphere"]},
        {"key": "min_thickness", "units": "mm",
         "aliases": ["min thickness", "minimum thickness", "min feature",
                     "minimum feature size", "min strut"]},
        {"key": "contact_area", "units": "mm^2",
         "aliases": ["contact area", "endplate area", "endplate contact area",
                     "footprint area", "footprint"]},
        {"key": "safety_factor", "units": "-",
         "aliases": ["safety factor", "factor of safety", "fos", "sf"]},
    ],
    # ---- Geometry used to derive metrics when nTop does not output them ------
    "geometry": {
        "footprint_area_mm2": 500.0,   # endplate footprint (used for E_app)
        "height_mm": 12.0,             # cage height along the load axis
        "envelope_volume_mm3": None,   # null -> footprint * height
        # Pore size estimate when nTop has no pore output:
        # pore ~= kappa[lattice] * cell_size - strut_thickness
        "pore_kappa": {"octet": 0.55, "gyroid": 0.55, "diamond": 0.65,
                       "kelvin": 0.60, "bcc": 0.65, "fcc": 0.55,
                       "schwarz": 0.55, "default": 0.58},
    },
    # ---- Loads and material (Ti-6Al-4V ELI, laser powder-bed fusion) ---------
    "physics": {
        "design_load_N": 1200.0,   # walking / moderate activity, L4-L5
        "peak_load_N": 2000.0,     # lifting; stresses scaled linearly
        "yield_MPa": 950.0,        # heat-treated LPBF Ti-6Al-4V
        "fatigue_MPa": 350.0,      # 10^7 cycle endurance (machined surface)
        "E_solid_GPa": 110.0,
        "density_g_cm3": 4.43,
        "load_is_in_model": True,  # nTop FE already applies design_load_N
    },
    # ---- What "optimal" means (Derringer-Suich desirability) -----------------
    "objectives": {
        "target_modulus_GPa": 3.0,            # PEEK-like, between cancellous and cortical bone
        "modulus_band_GPa": [2.0, 5.0],       # full desirability inside the band
        "modulus_hard_GPa": [0.5, 20.0],      # zero desirability outside
        "porosity_band": [0.60, 0.75],
        "porosity_hard": [0.40, 0.90],
        "pore_band_um": [500.0, 800.0],
        "pore_hard_um": [300.0, 1000.0],
        "sf_yield_min": 2.0,                  # hard constraint at design load
        "sf_yield_good": 4.0,                 # desirability saturates here
        "sf_fatigue_min": 1.0,                # hard constraint
        "sf_fatigue_good": 2.0,
        "min_strut_mm": 0.30,                 # LPBF manufacturability
        "good_strut_mm": 0.45,
        "mass_weight_relative": True,         # mass desirability relative to the campaign range
        "weights": {
            "modulus": 0.30, "porosity": 0.22, "pore_size": 0.22,
            "sf_fatigue": 0.12, "sf_yield": 0.06, "strut": 0.04,
            "mass": 0.02, "surface_area": 0.02,
        },
    },
    # ---- Campaign design -----------------------------------------------------
    "doe": {
        "profile": "standard",       # standard | quick | thorough
        "screening": "full_factorial",  # full_factorial | fractional | none
        "center_points": 3,
        "rsm": "ccd_face",           # ccd_face | box_behnken | none
        "lhs_runs": 10,
        "infill_iterations": 2,
        "infill_per_iteration": 3,
        "verify_top_n": 3,
        "budget_per_variant": 45,
        "log_transform_responses": ["max_stress", "max_displacement"],
    },
    "figures": {"dpi": 200, "format": "png", "watermark": None},
}

PROFILES = {
    "quick": {"screening": "none", "center_points": 1, "rsm": "none",
              "lhs_runs": 12, "infill_iterations": 2, "infill_per_iteration": 2,
              "verify_top_n": 1, "budget_per_variant": 18},
    "standard": {},
    "thorough": {"screening": "full_factorial", "center_points": 3,
                 "rsm": "ccd_face", "lhs_runs": 20, "infill_iterations": 4,
                 "infill_per_iteration": 3, "verify_top_n": 3,
                 "budget_per_variant": 80},
}


def normalise_name(s: str) -> str:
    """Lower-case, strip units in brackets and all punctuation/whitespace."""
    s = re.sub(r"[\(\[].*?[\)\]]", " ", str(s))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config(path: str | Path | None = None,
                overrides: dict | None = None) -> dict:
    """Load ``doe_config.json`` (if given) on top of the defaults."""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if path is not None:
        p = Path(path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as fh:
                user = json.load(fh)
            cfg = _deep_merge(cfg, user)
        else:
            raise FileNotFoundError(f"config file not found: {p}")
    if overrides:
        cfg = _deep_merge(cfg, overrides)
    profile = cfg["doe"].get("profile", "standard")
    if profile not in PROFILES:
        raise ValueError(f"unknown doe.profile '{profile}'; use one of {list(PROFILES)}")
    # Profile values apply only where the user did not set the key explicitly.
    user_doe = (overrides or {}).get("doe", {})
    if path is not None and Path(path).exists():
        with open(path, "r", encoding="utf-8") as fh:
            user_doe = {**json.load(fh).get("doe", {}), **user_doe}
    for k, v in PROFILES[profile].items():
        if k not in user_doe:
            cfg["doe"][k] = v
    validate_config(cfg)
    return cfg


def validate_config(cfg: dict) -> None:
    if not cfg["factors"]:
        raise ValueError("at least one factor is required")
    for f in cfg["factors"]:
        for key in ("name", "low", "high"):
            if key not in f:
                raise ValueError(f"factor {f} is missing '{key}'")
        if not f["low"] < f["high"]:
            raise ValueError(f"factor {f['name']}: low must be < high")
        f.setdefault("aliases", [])
        f.setdefault("type", "scalar")
        f.setdefault("units", "")
    w = cfg["objectives"]["weights"]
    if sum(w.values()) <= 0:
        raise ValueError("objective weights must sum to a positive number")
    if cfg["project"]["workers"] < 1:
        raise ValueError("project.workers must be >= 1")


def write_default_config(path: str | Path, root: str | None = None) -> Path:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if root:
        cfg["project"]["root"] = root
    p = Path(path)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
    return p


def factor_names(cfg: dict) -> list[str]:
    return [f["name"] for f in cfg["factors"]]
