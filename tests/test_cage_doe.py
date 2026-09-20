"""Unit and end-to-end tests (the end-to-end test uses the mock nTopCL)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cage_doe import design, objectives, surrogate  # noqa: E402
from cage_doe.config import load_config, normalise_name  # noqa: E402
from cage_doe.discover import Variant, build_variant, match_name, output_entries  # noqa: E402
from cage_doe.ntopcl import build_input_json, parse_output_json  # noqa: E402


# ---------------------------------------------------------------- designs
def test_designs_shapes():
    assert design.full_factorial(3).shape == (8, 3)
    assert design.fractional_factorial(5).shape == (16, 5)
    assert design.fractional_factorial(6).shape == (16, 6)
    assert design.ccd_face(3).shape == (14, 3)
    assert design.box_behnken(3).shape == (12, 3)
    X = design.lhs(10, 3, seed=1)
    assert X.shape == (10, 3) and X.min() >= -1 and X.max() <= 1


def test_fractional_factorial_is_resolution_iv():
    X = design.fractional_factorial(5)
    # no main effect is aliased with another main effect
    C = np.abs(X.T @ X) / len(X)
    assert np.allclose(C, np.eye(5))


def test_encode_decode_roundtrip_and_dedupe():
    lows, highs = np.array([1.5, 0.3]), np.array([4.0, 0.9])
    Xr = np.array([[1.5, 0.3], [4.0, 0.9], [2.75, 0.6]])
    Xc = design.encode(Xr, lows, highs)
    assert np.allclose(Xc, [[-1, -1], [1, 1], [0, 0]])
    assert np.allclose(design.decode(Xc, lows, highs), Xr)
    new = design.dedupe(np.array([[0, 0], [0.5, 0.5], [0.5, 0.5]]), Xc)
    assert new.shape == (1, 2)


# ---------------------------------------------------------------- surrogate
def test_quadratic_rsm_recovers_polynomial():
    rng = np.random.default_rng(0)
    X = rng.uniform(-1, 1, size=(30, 3))
    y = 1 + 2 * X[:, 0] - X[:, 1] ** 2 + 0.5 * X[:, 0] * X[:, 2]
    m = surrogate.QuadraticRSM(3).fit(X, y)
    assert m.order == "quadratic"
    assert m.r2 > 0.9999
    assert np.max(np.abs(m.predict(X) - y)) < 1e-6


def test_response_model_log_and_choice():
    rng = np.random.default_rng(1)
    X = rng.uniform(-1, 1, size=(25, 2))
    y = np.exp(1.5 * X[:, 0] + 0.3 * X[:, 1] ** 2)
    m = surrogate.ResponseModel("y", 2, log=True).fit(X, y)
    assert m.log is True
    assert m.diagnostics["loo_rmse_rel"] < 0.2
    assert np.all(m.predict(X) > 0)


# ---------------------------------------------------------------- objectives
def test_derive_metrics_and_desirability():
    cfg = load_config()
    resp = {"lattice_volume": 2200.0, "max_stress": 120.0, "max_displacement": 0.05, "surface_area": 9000.0}
    m = objectives.derive_metrics(resp, {"Cell Size": 2.5, "Strut Thickness": 0.5, "Shell Thickness": 1.0}, "octet", cfg)
    assert abs(m["porosity"] - (1 - 2200 / 6000)) < 1e-9
    assert abs(m["stiffness_N_mm"] - 1200 / 0.05) < 1e-9
    assert abs(m["E_app_GPa"] - 24000 * 12 / 500 / 1000) < 1e-9
    assert abs(m["sf_yield"] - 950 / (120 * 2000 / 1200)) < 1e-9
    assert m["pore_estimated"] == 1.0
    d = objectives.desirability(m, cfg, {"mass_g": (5, 15), "surface_area_mm2": (3000, 12000)})
    assert d["feasible"] and 0 < d["D"] <= 1
    # a stress above the yield limit makes the design infeasible
    m2 = dict(m, sf_yield=1.0)
    d2 = objectives.desirability(m2, cfg)
    assert d2["feasible"] is False and d2["D"] == 0.0 and d2["soft"] < 0


def test_unit_conversion():
    assert objectives.to_canonical(0.01, "kg", "mass") == pytest.approx(10.0)
    assert objectives.to_canonical(2.0, "cm^3", "lattice_volume") == pytest.approx(2000.0)
    assert objectives.to_canonical(1.5e8, "Pa", "max_stress") == pytest.approx(150.0)
    assert objectives.to_canonical(600, "um", "pore_size") == pytest.approx(0.6)


# ---------------------------------------------------------------- discovery / nTopCL JSON
def test_name_matching():
    cands = ["Unit Cell Size (mm)", "Strut Thickness", "Rim Thickness", "Compressive Load"]
    assert match_name(cands, "Cell Size", ["cell size", "unit cell"]) == "Unit Cell Size (mm)"
    assert match_name(cands, "Shell Thickness", ["shell", "rim thickness"]) == "Rim Thickness"
    assert match_name(cands, "Nothing", ["xyz"]) is None
    assert normalise_name("Max von Mises (MPa)") == "max von mises"


def test_template_mutation_preserves_layout(tmp_path):
    cfg = load_config()
    template = {"description": "t", "inputs": [
        {"name": "Cell Size", "type": "scalar", "values": 3.0, "units": "mm"},
        {"name": "Strut Thickness", "type": "real", "value": {"val": 0.5, "unit": "mm"}},
        {"name": "Export", "type": "text", "value": "out.stl"}]}
    v = Variant("v", "octet", tmp_path / "x.ntop", None, template,
                factor_map={"Cell Size": "Cell Size", "Strut Thickness": "Strut Thickness"})
    data = build_input_json(v, cfg, {"Cell Size": 2.0, "Strut Thickness": 0.4}, tmp_path)
    e = {x["name"]: x for x in data["inputs"]}
    assert e["Cell Size"]["values"] == 2.0 and e["Cell Size"]["units"] == "mm"
    assert e["Strut Thickness"]["value"] == {"val": 0.4, "unit": "mm"}
    assert e["Export"]["value"] == "out.stl"
    assert data["description"] == "t"


def test_output_parsing_variants(tmp_path):
    p = tmp_path / "o.json"
    p.write_text(json.dumps({"outputs": [{"name": "Mass", "type": "scalar", "value": 0.01, "units": "kg"},
                                         {"name": "Vol", "type": "scalar", "values": [2200.0], "units": "mm^3"}]}))
    out = parse_output_json(p)
    assert out["Mass"]["value"] == 0.01 and out["Vol"]["value"] == 2200.0
    assert output_entries({"outputs": {"A": 1.0, "B": {"value": 2.0, "units": "mm"}}})["B"]["value"] == 2.0


def test_build_variant_from_folder(tmp_path):
    cfg = load_config()
    ntop = tmp_path / "cage_gyroid.ntop"
    ntop.write_text("x")
    (tmp_path / "cage_gyroid_input.json").write_text(json.dumps({"inputs": [
        {"name": "Cell size", "type": "scalar", "values": 3.0}, {"name": "Thickness", "type": "scalar", "values": 0.5},
        {"name": "STL path", "type": "text", "value": "a.stl"}]}))
    v = build_variant(cfg, ntop)
    assert v.lattice == "gyroid"
    assert v.factor_map == {"Cell Size": "Cell size", "Strut Thickness": "Thickness"}
    assert "Shell Thickness" not in v.factor_map
    assert v.path_like_inputs == ["STL path"]


# ---------------------------------------------------------------- end-to-end with the mock
def test_end_to_end_mock(tmp_path):
    root = tmp_path / "files"
    subprocess.run([sys.executable, str(ROOT / "mock" / "make_demo_folder.py"), str(root)], check=True)
    from cage_doe.pipeline import run_campaign
    from cage_doe.plots import make_all_figures
    from cage_doe.report import write_report
    cfg = load_config(overrides={"project": {"root": str(root)},
                                 "doe": {"profile": "quick", "lhs_runs": 8, "infill_iterations": 1,
                                         "infill_per_iteration": 2, "verify_top_n": 1, "budget_per_variant": 12}})
    cr = run_campaign(cfg, mock=True)
    assert len(cr.variants) == 4
    assert not cr.ranking.empty and cr.ranking["rank"].tolist() == [1, 2, 3, 4]
    octet = next(v for v in cr.variants if v.variant.lattice == "octet")
    assert (octet.runs["phase"] == "prior").sum() == 1          # the existing octet run was imported
    assert (root / "DOE_results" / "data" / "runs_all.csv").exists()
    figs = make_all_figures(cr)
    assert len(figs) >= 30
    md, htm = write_report(cr, figs)
    assert md.exists() and htm.exists()
    # re-analysis without new runs must reuse the cache
    cr2 = run_campaign(cfg, mock=True, analyze_only=True)
    assert cr2.runs["status"].isin(["ok", "cached"]).sum() == cr.runs["status"].isin(["ok", "cached"]).sum()
    # ... also from a different Python process (different hash seed): identical ranking, no new runs
    import os
    cfg_path = root / "doe_config.json"
    cfg_path.write_text(json.dumps({"doe": cfg["doe"]}))
    env = dict(os.environ, PYTHONHASHSEED="12345")
    subprocess.run([sys.executable, "-m", "cage_doe", "run", "--root", str(root), "--config", str(cfg_path),
                    "--mock", "--analyze-only", "--no-figures", "--no-pptx"], check=True, env=env, cwd=str(ROOT),
                   capture_output=True)
    import pandas as pd
    rk2 = pd.read_csv(root / "DOE_results" / "data" / "ranking.csv")
    assert rk2["variant"].tolist() == cr.ranking["variant"].tolist()
    assert np.allclose(rk2["D_recommended"].to_numpy(float), cr.ranking["D_recommended"].to_numpy(float))
    assert (rk2["n_ok"].to_numpy() == cr.ranking["n_ok"].to_numpy()).all()
