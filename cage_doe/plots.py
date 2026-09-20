"""Presentation figures for the campaign (matplotlib, PNG).

Every figure follows the same conventions: one colour job per chart
(categorical = lattice variant in fixed order with marker shapes, sequential
blue for magnitude, blue/red for signed effects, status red only for failed
runs), thin marks, hairline grid, legends whenever two or more series appear,
and the acceptance windows drawn as neutral grey bands.
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from . import palette as P
from .design import decode
from .objectives import COMPONENT_LABELS, METRIC_LABELS, d_larger, d_window

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

log = logging.getLogger(__name__)
P.apply_style()

PHASE_COLORS = {"prior": "#86b6ef", "screen": "#5598e7", "rsm": "#2a78d6", "lhs": "#1c5cab",
                "infill": "#104281", "verify": "#0d366b"}
PHASE_LABELS = {"prior": "Prior run", "screen": "Screening (2-level factorial)", "rsm": "RSM (face-centred CCD)",
                "lhs": "Space filling (LHS)", "infill": "Adaptive infill", "verify": "Verification"}
BAND = "#f0efec"
SURFACE_METRICS = [("E_app_GPa", "Apparent modulus (GPa)"), ("porosity", "Porosity (-)"),
                   ("pore_um", "Pore size (um)"), ("max_stress_peak_MPa", "Peak von Mises (MPa)"),
                   ("mass_g", "Mass (g)"), ("D_adj", "Desirability D")]
EFFECT_METRICS = [("E_app_GPa", "E_app (GPa)"), ("porosity", "Porosity"), ("pore_um", "Pore (um)"),
                  ("sf_fatigue", "SF fatigue"), ("mass_g", "Mass (g)"), ("D_adj", "Desirability")]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _phase_key(p: str) -> str:
    return "infill" if str(p).startswith("infill") else str(p)


def _label(f: dict) -> str:
    return f"{f['name']} ({f['units']})" if f.get("units") else f["name"]


def _finish(fig, path: Path, cfg: dict) -> Path:
    wm = cfg.get("figures", {}).get("watermark")
    if wm:
        fig.text(0.5, 0.5, wm, rotation=28, ha="center", va="center", fontsize=30,
                 color=P.INK_2, alpha=0.13, zorder=1000, transform=fig.transFigure)
    fig.savefig(path, dpi=int(cfg.get("figures", {}).get("dpi", 200)))
    plt.close(fig)
    return path


def _band_y(ax, lo, hi, label=None):
    ax.axhspan(lo, hi, color=BAND, zorder=0, lw=0)
    if label:
        ax.text(0.01, (lo + hi) / 2, label, transform=ax.get_yaxis_transform(), fontsize=7,
                color=P.MUTED, va="center", ha="left")


def _band_x(ax, lo, hi):
    ax.axvspan(lo, hi, color=BAND, zorder=0, lw=0)


def _metric_band(ax, metric: str, cfg: dict, axis: str = "y"):
    o = cfg["objectives"]
    band = {"E_app_GPa": o["modulus_band_GPa"], "porosity": o["porosity_band"],
            "pore_um": o["pore_band_um"]}.get(metric)
    if band is None:
        return
    (_band_y if axis == "y" else _band_x)(ax, band[0], band[1])


def _threshold(ax, metric: str, cfg: dict, axis: str = "y"):
    o, ph = cfg["objectives"], cfg["physics"]
    thr = {"sf_fatigue": o["sf_fatigue_min"], "sf_yield": o["sf_yield_min"],
           "max_stress_peak_MPa": ph["yield_MPa"] / o["sf_yield_min"]}.get(metric)
    if thr is None:
        return
    (ax.axhline if axis == "y" else ax.axvline)(thr, color=P.INK_2, lw=1.0, ls=(0, (4, 3)), zorder=2)


def _real_axis(vr, i: int, coded: np.ndarray) -> np.ndarray:
    return decode(coded, vr.lows[i], vr.highs[i])


def _variant_legend(ax, cr, loc="best", **kw):
    handles = [Line2D([], [], color=P.variant_style(n)["color"], marker=P.variant_style(n)["marker"],
                      ls="", ms=7, label=vr.variant.name) for n, vr in enumerate(cr.variants)]
    ax.legend(handles=handles, loc=loc, **kw)


def _rows_to_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# --------------------------------------------------------------------------- #
# campaign-level figures
# --------------------------------------------------------------------------- #
def fig_objective_definition(cr, out: Path) -> Path:
    o, cfg = cr.cfg["objectives"], cr.cfg
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.4))
    fig.suptitle("What 'optimal' means: desirability of each clinical criterion", fontsize=13, fontweight="bold")
    specs = [
        ("Apparent modulus E_app (GPa)", np.linspace(0, 12, 400),
         lambda x: d_window(x, *[o["modulus_hard_GPa"][0], *o["modulus_band_GPa"], o["modulus_hard_GPa"][1]]),
         f"target {o['target_modulus_GPa']:g} GPa - bone/PEEK-like, limits stress shielding", "modulus"),
        ("Porosity (-)", np.linspace(0.3, 1.0, 400),
         lambda x: d_window(x, *[o["porosity_hard"][0], *o["porosity_band"], o["porosity_hard"][1]]),
         "open volume for bone in-growth", "porosity"),
        ("Pore size (um)", np.linspace(150, 1150, 400),
         lambda x: d_window(x, *[o["pore_hard_um"][0], *o["pore_band_um"], o["pore_hard_um"][1]]),
         "vascularised osteogenesis window", "pore_size"),
        (f"Yield safety factor at {cfg['physics']['peak_load_N']:g} N (-)", np.linspace(0, 6, 400),
         lambda x: d_larger(x, o["sf_yield_min"], o["sf_yield_good"]), "static strength (ASTM F2077 style)", "sf_yield"),
        (f"Fatigue safety factor at {cfg['physics']['design_load_N']:g} N (-)", np.linspace(0, 3.5, 400),
         lambda x: d_larger(x, o["sf_fatigue_min"], o["sf_fatigue_good"]), "cyclic walking load", "sf_fatigue"),
        ("Strut / sheet thickness (mm)", np.linspace(0.15, 0.7, 400),
         lambda x: d_larger(x, o["min_strut_mm"], o["good_strut_mm"]), "LPBF Ti-6Al-4V printability", "strut"),
    ]
    for ax, (xl, xs, fn, note, key) in zip(axes.ravel(), specs):
        ys = np.array([fn(float(x)) for x in xs])
        ax.fill_between(xs, 0, ys, color=P.SEQUENTIAL_BLUE[1], alpha=0.5, lw=0)
        ax.plot(xs, ys, color=P.CATEGORICAL[0])
        ax.set_xlabel(xl)
        ax.set_ylabel("desirability d")
        ax.set_ylim(0, 1.08)
        ax.set_title(f"{COMPONENT_LABELS[key]}  (weight {o['weights'][key]:.2f})", fontsize=10)
        ax.text(0.02, 0.9, note, transform=ax.transAxes, fontsize=7.5, color=P.INK_2)
    w = o["weights"]
    fig.text(0.5, 0.005, "Overall D = weighted geometric mean of the components (any hard-limit violation gives D = 0).  "
             + "Weights: " + ", ".join(f"{COMPONENT_LABELS[k]} {v:.2f}" for k, v in w.items()),
             ha="center", fontsize=8, color=P.INK_2)
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    return _finish(fig, out / "fig00_objective_definition.png", cfg)


def fig_run_summary(cr, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9, 4.2))
    names = [vr.variant.name for vr in cr.variants]
    ok_feas = np.array([int((vr.runs["feasible"]).sum()) for vr in cr.variants])
    ok_inf = np.array([int((vr.runs["status"].isin(["ok", "cached"]) & ~vr.runs["feasible"]).sum()) for vr in cr.variants])
    failed = np.array([int((~vr.runs["status"].isin(["ok", "cached"])).sum()) for vr in cr.variants])
    y = np.arange(len(names))
    ax.barh(y, ok_feas, color=P.CATEGORICAL[0], height=0.55, label="successful, all hard limits met")
    ax.barh(y, ok_inf, left=ok_feas, color=P.SEQUENTIAL_BLUE[3], height=0.55, label="successful, outside a hard limit")
    ax.barh(y, failed, left=ok_feas + ok_inf, color=P.STATUS["critical"], height=0.55, label="nTop run failed (x)")
    for i in range(len(names)):
        ax.text(ok_feas[i] + ok_inf[i] + failed[i] + 0.3, y[i], f"{ok_feas[i] + ok_inf[i] + failed[i]} runs",
                va="center", fontsize=8, color=P.INK_2)
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    ax.set_xlabel("number of nTopCL runs")
    ax.set_title("Campaign size per lattice variant")
    ax.set_xlim(0, (ok_feas + ok_inf + failed).max() * 1.18 if len(names) else 1)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=3, fontsize=8)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return _finish(fig, out / "fig01_run_summary.png", cr.cfg)


def fig_ranking(cr, out: Path) -> Path:
    rk = cr.ranking
    comps = list(cr.cfg["objectives"]["weights"])
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.6), gridspec_kw={"width_ratios": [1.1, 1.6]})
    idx = {vr.variant.name: n for n, vr in enumerate(cr.variants)}
    y = np.arange(len(rk))
    vals = rk["D_recommended"].fillna(0).to_numpy(float)
    ax.barh(y, vals, color=[P.variant_style(idx[n])["color"] for n in rk["variant"]], height=0.55)
    for i, (v, src) in enumerate(zip(vals, rk["source"])):
        ax.text(v + 0.01, y[i], f"{v:.2f}  ({src})", va="center", fontsize=8, color=P.INK_2)
    ax.set_yticks(y, [f"#{r}  {n}" for r, n in zip(rk["rank"], rk["variant"])])
    ax.invert_yaxis()
    ax.set_xlim(0, max(1.0, vals.max() * 1.35 if len(vals) else 1))
    ax.set_xlabel("overall desirability D of the recommended design")
    ax.set_title("Ranking of lattice types")
    ax.grid(axis="y", visible=False)
    M = rk[[f"d_{c}" for c in comps]].to_numpy(float)
    im = ax2.imshow(M, cmap=P.cmap_seq, vmin=0, vmax=1, aspect="auto")
    ax2.set_xticks(range(len(comps)), [COMPONENT_LABELS[c] for c in comps], rotation=30, ha="right", fontsize=8)
    ax2.set_yticks(range(len(rk)), rk["variant"])
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            if np.isfinite(M[i, j]):
                ax2.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=8,
                         color=P.SURFACE if M[i, j] > 0.6 else P.INK)
    ax2.set_title("Component desirabilities of each recommended design")
    ax2.grid(False)
    cb = fig.colorbar(im, ax=ax2, fraction=0.03, pad=0.02)
    cb.set_label("desirability", fontsize=8)
    fig.tight_layout()
    return _finish(fig, out / "fig02_ranking.png", cr.cfg)


def fig_compare_metrics(cr, out: Path) -> Path:
    metrics = [("E_app_GPa", "Apparent modulus (GPa)"), ("porosity", "Porosity (-)"),
               ("pore_um", "Pore size (um)"), ("sf_yield", "Yield SF at peak load (-)"),
               ("sf_fatigue", "Fatigue SF (-)"), ("max_stress_MPa", "Max von Mises (MPa)"),
               ("mass_g", "Mass (g)"), ("surface_area_mm2", "Surface area (mm^2)")]
    fig, axes = plt.subplots(2, 4, figsize=(13, 6.2))
    names = [vr.variant.name for vr in cr.variants]
    for ax, (m, lab) in zip(axes.ravel(), metrics):
        vals = np.array([vr.recommended.get(m, np.nan) if vr.recommended else np.nan for vr in cr.variants], float)
        x = np.arange(len(names))
        ax.bar(x, np.nan_to_num(vals), color=[P.variant_style(n)["color"] for n in range(len(names))], width=0.6)
        for xi, v in zip(x, vals):
            if np.isfinite(v):
                ax.text(xi, v, f"{v:.3g}", ha="center", va="bottom", fontsize=8, color=P.INK_2)
        _metric_band(ax, m, cr.cfg)
        _threshold(ax, m, cr.cfg)
        ax.set_xticks(x, names, rotation=20, ha="right", fontsize=8)
        ax.set_title(lab, fontsize=10)
        ax.grid(axis="x", visible=False)
        if np.isfinite(vals).any():
            ax.set_ylim(0, np.nanmax(vals) * 1.25)
    fig.suptitle("Recommended design of each lattice type - clinical metrics (grey = target window, dashed = minimum)",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return _finish(fig, out / "fig03_compare_metrics.png", cr.cfg)


def fig_radar(cr, out: Path) -> Path:
    comps = [c for c in cr.cfg["objectives"]["weights"]]
    n = len(comps)
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ang_c = np.concatenate([ang, ang[:1]])
    fig = plt.figure(figsize=(7.2, 6.4))
    ax = fig.add_subplot(111, polar=True)
    for k, vr in enumerate(cr.variants):
        if not vr.recommended:
            continue
        vals = np.array([vr.recommended.get(f"d_{c}", np.nan) for c in comps], float)
        vals = np.nan_to_num(vals)
        vals_c = np.concatenate([vals, vals[:1]])
        st = P.variant_style(k)
        ax.plot(ang_c, vals_c, color=st["color"], marker=st["marker"], ms=5, label=vr.variant.name, lw=1.8)
        ax.fill(ang_c, vals_c, color=st["color"], alpha=0.06)
    ax.set_xticks(ang, [COMPONENT_LABELS[c] for c in comps], fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0], ["0.25", "0.5", "0.75", "1"], fontsize=7)
    ax.set_title("Desirability profile of each recommended design", pad=18)
    ax.legend(loc="lower right", bbox_to_anchor=(1.25, -0.08))
    return _finish(fig, out / "fig04_radar.png", cr.cfg)


def fig_weight_robustness(cr, out: Path) -> Path | None:
    rb = cr.robustness
    if rb is None:
        return None
    names, freq = list(rb["names"]), rb["rank_freq"]
    n = len(names)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    left = np.zeros(n)
    steps = [P.SEQUENTIAL_BLUE[i] for i in np.linspace(11, 3, n).astype(int)]
    y = np.arange(n)
    for r in range(n):
        ax.barh(y, freq[:, r], left=left, color=steps[r], height=0.55, label=f"rank {r + 1}")
        for i in range(n):
            if freq[i, r] > 0.08:
                ax.text(left[i] + freq[i, r] / 2, y[i], f"{freq[i, r]:.0%}", ha="center", va="center",
                        fontsize=8, color=P.SURFACE if r < n / 2 else P.INK)
        left += freq[:, r]
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("share of 500 random weight perturbations (Dirichlet around the chosen weights)")
    ax.set_title("How stable is the ranking if the weights change?")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=n, fontsize=8)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return _finish(fig, out / "fig05_weight_robustness.png", cr.cfg)


def _pareto_axes_setup(ax, pair: str, cfg: dict):
    o = cfg["objectives"]
    if pair == "stiffness_vs_fatigue":
        ax.set_xlabel(f"|apparent modulus - {o['target_modulus_GPa']:g} GPa|  (GPa)  - lower is better")
        _band_x(ax, 0, o["modulus_band_GPa"][1] - o["target_modulus_GPa"])
    else:
        ax.set_xlabel("porosity (-)  - higher is better within the grey window")
        _band_x(ax, *o["porosity_band"])
    ax.set_ylabel("fatigue safety factor (-)  - higher is better")
    _threshold(ax, "sf_fatigue", cfg)


def fig_pareto_all(cr, out: Path) -> Path:
    from .optimize import PARETO_PAIRS
    o = cr.cfg["objectives"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.4))
    for ax, pair in zip(axes, PARETO_PAIRS):
        mx, _, my, _ = PARETO_PAIRS[pair]
        _pareto_axes_setup(ax, pair, cr.cfg)
        for k, vr in enumerate(cr.variants):
            if not vr.pareto or not vr.cloud_rows:
                continue
            df = _rows_to_frame(vr.cloud_rows)
            st = P.variant_style(k)
            pf = df[vr.pareto[pair]].sort_values(mx)
            ax.plot(pf[mx], pf[my], color=st["color"], marker=st["marker"], ms=4, lw=1.5,
                    label=f"{vr.variant.name} - Pareto front (surrogate)")
            if vr.recommended:
                xv = abs(vr.recommended["E_app_GPa"] - o["target_modulus_GPa"]) if mx == "modulus_dev" else vr.recommended[mx]
                ax.plot(xv, vr.recommended[my], marker="*", ms=16, color=st["color"], mec=P.SURFACE, mew=1.2, ls="")
        ax.plot([], [], marker="*", ms=12, color=P.INK_2, ls="", label="recommended design (verified in nTop)")
    axes[0].set_title("Stiffness matching vs fatigue strength")
    axes[1].set_title("Porosity vs fatigue strength")
    axes[0].legend(fontsize=8)
    fig.suptitle("Trade-off fronts of all lattice types (feasible surrogate designs only)", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return _finish(fig, out / "fig06_pareto_all_variants.png", cr.cfg)


def fig_optimum_settings(cr, out: Path) -> Path:
    factors = cr.cfg["factors"]
    fig, axes = plt.subplots(len(factors), 1, figsize=(9, 1.25 * len(factors) + 1.0), sharex=False)
    axes = np.atleast_1d(axes)
    nv = max(len(cr.variants), 1)
    offsets = np.linspace(-0.25, 0.25, nv) if nv > 1 else [0.0]
    for ax, f in zip(axes, factors):
        ax.hlines(0, f["low"], f["high"], color=P.AXIS, lw=6, alpha=0.6)
        labelled: set[str] = set()
        for k, vr in enumerate(cr.variants):
            if vr.recommended and f["name"] in vr.recommended and np.isfinite(vr.recommended[f["name"]]):
                st = P.variant_style(k)
                val = vr.recommended[f["name"]]
                ax.plot(val, offsets[k], marker=st["marker"], color=st["color"], ms=10,
                        mec=P.SURFACE, mew=1.0, ls="", label=vr.variant.name)
                txt = f"{val:.3g}"
                if txt not in labelled:      # coinciding values get one label
                    ax.text(val, 0.42, txt, ha="center", va="bottom", fontsize=7, color=P.INK_2)
                    labelled.add(txt)
        ax.set_yticks([])
        ax.set_ylim(-0.6, 0.8)
        ax.set_xlim(f["low"] - 0.05 * (f["high"] - f["low"]), f["high"] + 0.05 * (f["high"] - f["low"]))
        ax.set_xlabel(_label(f))
        ax.grid(axis="y", visible=False)
        ax.spines["left"].set_visible(False)
    handles = [Line2D([], [], color=P.variant_style(n)["color"], marker=P.variant_style(n)["marker"], ls="", ms=8,
                      label=vr.variant.name) for n, vr in enumerate(cr.variants)]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.93), ncol=nv, fontsize=8, frameon=False)
    fig.suptitle("Where each lattice's recommended design sits inside the swept ranges", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    return _finish(fig, out / "fig07_optimum_settings.png", cr.cfg)


def fig_predicted_vs_verified(cr, out: Path) -> Path | None:
    pairs = [("E_app_GPa", "Apparent modulus (GPa)"), ("porosity", "Porosity (-)"),
             ("max_stress_MPa", "Max von Mises (MPa)"), ("D", "Desirability D")]
    rows = []
    for k, vr in enumerate(cr.variants):
        for r in vr.verified:
            if r.get("status") in ("ok", "cached"):
                rows.append((k, r))
    if not rows:
        return None
    fig, axes = plt.subplots(2, 2, figsize=(9.5, 8))
    for ax, (m, lab) in zip(axes.ravel(), pairs):
        xs, ys = [], []
        for k, r in rows:
            xp, ya = r.get(f"pred_{m}", np.nan), r.get(m, np.nan)
            if np.isfinite(xp) and np.isfinite(ya):
                st = P.variant_style(k)
                ax.plot(xp, ya, marker=st["marker"], color=st["color"], ms=8, ls="", mec=P.SURFACE, mew=0.8)
                xs.append(xp)
                ys.append(ya)
        if xs:
            lo, hi = min(xs + ys), max(xs + ys)
            pad = 0.08 * (hi - lo if hi > lo else 1)
            ax.plot([lo - pad, hi + pad], [lo - pad, hi + pad], color=P.AXIS, lw=1)
            err = np.mean(np.abs(np.array(ys) - np.array(xs)) / np.maximum(np.abs(np.array(ys)), 1e-9)) * 100
            ax.text(0.03, 0.92, f"mean abs. error {err:.1f}%", transform=ax.transAxes, fontsize=8, color=P.INK_2)
        ax.set_xlabel(f"predicted by surrogate - {lab}")
        ax.set_ylabel("nTop verification run")
        ax.set_title(lab, fontsize=10)
    _variant_legend(axes[0, 0], cr, loc="lower right")
    fig.suptitle("Surrogate prediction vs nTop verification of the optimum candidates", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return _finish(fig, out / "fig08_predicted_vs_verified.png", cr.cfg)


# --------------------------------------------------------------------------- #
# per-variant figures
# --------------------------------------------------------------------------- #
def fig_design_space(vr, cr, out: Path) -> Path:
    k = vr.k
    pairs = [(i, j) for i in range(k) for j in range(i + 1, k)] if k >= 2 else [(0, 0)]
    if k > 3:
        i0, j0 = vr.top_factors
        pairs = [(i0, j0)] + [p for p in pairs if p != (i0, j0)][:2]
    fig, axes = plt.subplots(1, len(pairs), figsize=(4.4 * len(pairs) + 1, 4.4))
    axes = np.atleast_1d(axes)
    df = vr.runs
    for ax, (i, j) in zip(axes, pairs):
        xi, xj = vr.names[i], vr.names[j]
        for ph in PHASE_COLORS:
            sel = df[(df["phase"].map(_phase_key) == ph) & df["status"].isin(["ok", "cached"])]
            if sel.empty:
                continue
            ax.plot(sel[xi], sel[xj], ls="", marker="o", ms=6, color=PHASE_COLORS[ph], mec=P.SURFACE, mew=0.6,
                    label=PHASE_LABELS[ph])
        bad = df[~df["status"].isin(["ok", "cached"])]
        if not bad.empty:
            ax.plot(bad[xi], bad[xj], ls="", marker="x", ms=7, color=P.STATUS["critical"], mew=1.6, label="nTop run failed")
        if vr.recommended:
            ax.plot(vr.recommended[xi], vr.recommended[xj], marker="*", ms=15, color=P.INK, mec=P.SURFACE, mew=1.2,
                    ls="", label="recommended design")
        ax.set_xlabel(_label(vr.factors[i]))
        ax.set_ylabel(_label(vr.factors[j]))
    axes[0].legend(fontsize=7.5, loc="best")
    fig.suptitle(f"{vr.variant.name}: sampled design points by campaign phase", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _finish(fig, out / f"{vr.variant.name}_fig10_design_space.png", cr.cfg)


def fig_main_effects(vr, cr, out: Path) -> Path | None:
    if not vr.main_effects:
        return None
    k = vr.k
    fig, axes = plt.subplots(len(EFFECT_METRICS), k, figsize=(3.3 * k + 1, 1.75 * len(EFFECT_METRICS) + 0.8),
                             sharex="col", sharey="row", squeeze=False)
    for r, (m, lab) in enumerate(EFFECT_METRICS):
        for c in range(k):
            ax = axes[r, c]
            me = vr.main_effects[str(c)]
            x = _real_axis(vr, c, me["grid"])
            ax.plot(x, me[m], color=P.CATEGORICAL[0])
            _metric_band(ax, m, cr.cfg)
            _threshold(ax, m, cr.cfg)
            if c == 0:
                ax.set_ylabel(lab, fontsize=9)
            if r == len(EFFECT_METRICS) - 1:
                ax.set_xlabel(_label(vr.factors[c]), fontsize=9)
            if vr.optimum_coded is not None:
                ax.axvline(_real_axis(vr, c, vr.optimum_coded[c]), color=P.MUTED, lw=0.8)
    fig.suptitle(f"{vr.variant.name}: one-factor-at-a-time effects around the recommended design (thin line = its value)",
                 fontsize=11, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return _finish(fig, out / f"{vr.variant.name}_fig11_main_effects.png", cr.cfg)


def fig_interactions(vr, cr, out: Path) -> Path | None:
    if not vr.interactions:
        return None
    pairs = list(vr.interactions)
    ncol = min(3, len(pairs))
    nrow = int(np.ceil(len(pairs) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.2 * ncol + 0.5, 3.3 * nrow + 0.8), squeeze=False)
    steps = [P.SEQUENTIAL_BLUE[3], P.SEQUENTIAL_BLUE[7], P.SEQUENTIAL_BLUE[11]]
    for ax, (i, j) in zip(axes.ravel(), pairs):
        d = vr.interactions[(i, j)]
        x = _real_axis(vr, i, d["grid"])
        for lvl, curve, col in zip(d["levels"], d["curves"], steps):
            ax.plot(x, curve, color=col, label=f"{vr.names[j]} = {_real_axis(vr, j, lvl):.3g}")
        ax.set_xlabel(_label(vr.factors[i]), fontsize=9)
        ax.set_ylabel("desirability D", fontsize=9)
        ax.legend(fontsize=7, title=None)
    for ax in axes.ravel()[len(pairs):]:
        ax.axis("off")
    fig.suptitle(f"{vr.variant.name}: two-factor interactions on desirability around the recommended design (non-parallel = interaction)",
                 fontsize=11, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return _finish(fig, out / f"{vr.variant.name}_fig12_interactions.png", cr.cfg)


def fig_response_surfaces(vr, cr, out: Path) -> Path | None:
    g = vr.grids
    if not g:
        return None
    i, j = g["i"], g["j"]
    df = _rows_to_frame(g["rows"])
    n = g["gi"].shape[0]
    X = _real_axis(vr, i, g["gi"])
    Y = _real_axis(vr, j, g["gj"])
    feas = df["feasible"].to_numpy(bool).reshape(n, n)
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.6))
    obs = vr.runs[vr.runs["status"].isin(["ok", "cached"])]
    for ax, (m, lab) in zip(axes.ravel(), SURFACE_METRICS):
        Z = df[m].to_numpy(float).reshape(n, n)
        if m == "D_adj":
            Z = np.where(np.isfinite(Z), Z, 0.0)
        cf = ax.contourf(X, Y, Z, levels=14, cmap=P.cmap_seq)
        cb = fig.colorbar(cf, ax=ax, fraction=0.046, pad=0.02)
        cb.ax.tick_params(labelsize=7)
        if feas.any() and not feas.all():
            ax.contour(X, Y, feas.astype(float), levels=[0.5], colors=[P.INK], linewidths=1.2)
        o = cr.cfg["objectives"]
        lines = {"E_app_GPa": o["modulus_band_GPa"], "porosity": o["porosity_band"], "pore_um": o["pore_band_um"],
                 "max_stress_peak_MPa": [cr.cfg["physics"]["yield_MPa"] / o["sf_yield_min"]]}.get(m)
        if lines:
            try:
                cs = ax.contour(X, Y, Z, levels=sorted(lines), colors=[P.CATEGORICAL[1]], linewidths=1.0,
                                linestyles="dashed")
                ax.clabel(cs, fontsize=7, fmt="%g")
            except ValueError:
                pass
        ax.plot(obs[vr.names[i]], obs[vr.names[j]], ls="", marker="o", ms=3.5, color=P.SURFACE, mec=P.INK_2, mew=0.7)
        if vr.recommended:
            ax.plot(vr.recommended[vr.names[i]], vr.recommended[vr.names[j]], marker="*", ms=14, color=P.INK,
                    mec=P.SURFACE, mew=1.2, ls="")
        ax.set_title(lab, fontsize=10)
        ax.set_xlabel(_label(vr.factors[i]), fontsize=9)
        ax.set_ylabel(_label(vr.factors[j]), fontsize=9)
        ax.grid(False)
    others = [f"{vr.names[c]} = {_real_axis(vr, c, vr.optimum_coded[c]):.3g}" for c in range(vr.k) if c not in (i, j)] \
        if vr.optimum_coded is not None else []
    sub = ("; other factors fixed at the optimum: " + ", ".join(others)) if others else ""
    fig.suptitle(f"{vr.variant.name}: surrogate response surfaces over the two most influential factors{sub}\n"
                 "black line = feasible region boundary, orange dashed = target-window limits, dots = nTop runs, star = recommended",
                 fontsize=10.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return _finish(fig, out / f"{vr.variant.name}_fig13_response_surfaces.png", cr.cfg)


def fig_pareto(vr, cr, out: Path) -> Path | None:
    from .optimize import PARETO_PAIRS
    if not vr.pareto or not vr.cloud_rows:
        return None
    df = _rows_to_frame(vr.cloud_rows)
    o = cr.cfg["objectives"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    obs = vr.runs[vr.runs["feasible"]]
    for ax, pair in zip(axes, PARETO_PAIRS):
        mx, _, my, _ = PARETO_PAIRS[pair]
        _pareto_axes_setup(ax, pair, cr.cfg)
        inf = df[~df["feasible"]]
        ax.plot(inf[mx], inf[my], ls="", marker=".", ms=3, color=P.AXIS, alpha=0.5,
                label="surrogate design, violates a hard limit")
        fe = df[df["feasible"]]
        ax.plot(fe[mx], fe[my], ls="", marker=".", ms=3.5, color=P.SEQUENTIAL_BLUE[4], alpha=0.7,
                label="surrogate design, feasible")
        pf = df[vr.pareto[pair]].sort_values(mx)
        ax.plot(pf[mx], pf[my], color=P.CATEGORICAL[0], marker="o", ms=4, lw=1.6, label="Pareto front")
        ax.plot(obs[mx], obs[my], ls="", marker="o", ms=6, color=P.SURFACE, mec=P.INK, mew=1.0, label="feasible nTop run")
        if vr.recommended:
            xv = abs(vr.recommended["E_app_GPa"] - o["target_modulus_GPa"]) if mx == "modulus_dev" else vr.recommended[mx]
            ax.plot(xv, vr.recommended[my], marker="*", ms=16, color=P.CATEGORICAL[1], mec=P.SURFACE, mew=1.2, ls="",
                    label="recommended design")
        ymax = np.nanpercentile(df[my], 99) if df[my].notna().any() else 1
        ax.set_ylim(0, max(ymax * 1.1, 2.5))
    axes[0].set_title("Stiffness matching vs fatigue strength")
    axes[1].set_title("Porosity vs fatigue strength")
    axes[1].legend(fontsize=8, loc="upper right")
    fig.suptitle(f"{vr.variant.name}: trade-offs across the whole design space (3000 surrogate designs)",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return _finish(fig, out / f"{vr.variant.name}_fig14_pareto.png", cr.cfg)


def fig_sensitivity(vr, cr, out: Path) -> Path | None:
    if vr.sobol is None:
        return None
    order = np.argsort(vr.sobol["ST"])
    names = [vr.names[i] for i in order]
    y = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(8, 1.0 * len(names) + 2.0))
    ax.barh(y + 0.18, vr.sobol["ST"][order], height=0.34, color=P.CATEGORICAL[0], label="total-order index (incl. interactions)")
    ax.barh(y - 0.18, vr.sobol["S1"][order], height=0.34, color=P.CATEGORICAL[1], label="first-order index")
    for yi, st, s1 in zip(y, vr.sobol["ST"][order], vr.sobol["S1"][order]):
        ax.text(st + 0.01, yi + 0.18, f"{st:.2f}", va="center", fontsize=8, color=P.INK_2)
        ax.text(s1 + 0.01, yi - 0.18, f"{s1:.2f}", va="center", fontsize=8, color=P.INK_2)
    ax.set_yticks(y, names)
    ax.set_xlim(0, 1.15)
    ax.set_xlabel("Sobol sensitivity index of the desirability D (surrogate, 1024 samples)")
    ax.set_title(f"{vr.variant.name}: which input drives the outcome?")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return _finish(fig, out / f"{vr.variant.name}_fig15_sensitivity.png", cr.cfg)


def fig_convergence(vr, cr, out: Path) -> Path | None:
    h = [x for x in vr.history if np.isfinite(x["best_D"])]
    if len(h) < 2:
        return None
    fig, ax = plt.subplots(figsize=(8, 4))
    xs = [x["n_runs"] for x in h]
    ys = [x["best_D"] for x in h]
    ax.step(xs, ys, where="post", color=P.CATEGORICAL[0], marker="o", ms=5)
    for x in h:
        ax.annotate(x["label"], (x["n_runs"], x["best_D"]), textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=7.5, color=P.INK_2)
    if vr.optimum and np.isfinite(vr.optimum.get("D_adj", np.nan)):
        ax.axhline(vr.optimum["D_adj"], color=P.MUTED, lw=1, ls=(0, (4, 3)))
        ax.text(xs[0], vr.optimum["D_adj"], " surrogate optimum", fontsize=7.5, color=P.MUTED, va="bottom")
    ax.set_xlabel("cumulative nTopCL runs")
    ax.set_ylabel("best observed desirability D")
    ax.set_ylim(0, max(1.0, max(ys) * 1.15))
    ax.set_title(f"{vr.variant.name}: improvement over the campaign")
    fig.tight_layout()
    return _finish(fig, out / f"{vr.variant.name}_fig16_convergence.png", cr.cfg)


def fig_model_fit(vr, cr, out: Path) -> Path | None:
    if not vr.models:
        return None
    keys = list(vr.models)[:6]
    ok = vr.runs[vr.runs["status"].isin(["ok", "cached"])]
    from .design import encode
    Xc = encode(ok[vr.names].to_numpy(float), vr.lows, vr.highs)
    fig, axes = plt.subplots(2, 3, figsize=(11, 6.6), squeeze=False)
    for ax, key in zip(axes.ravel(), keys):
        m = vr.models[key]
        y = ok[f"resp_{key}"].to_numpy(float)
        yh = m.predict(Xc)
        ax.plot(yh, y, ls="", marker="o", ms=5, color=P.CATEGORICAL[0], mec=P.SURFACE, mew=0.6)
        lo, hi = np.nanmin([y, yh]), np.nanmax([y, yh])
        ax.plot([lo, hi], [lo, hi], color=P.AXIS, lw=1)
        d = m.diagnostics
        ax.text(0.03, 0.85, f"{d['chosen'].upper()} ({d['order']}, n={d['n']})\nR2 = {d['rsm_r2']:.3f}\n"
                            f"LOO-RMSE / spread = {d['loo_rmse_rel']:.2f}",
                transform=ax.transAxes, fontsize=7.5, color=P.INK_2, va="top")
        ax.set_title(key.replace("_", " "), fontsize=10)
        ax.set_xlabel("surrogate prediction")
        ax.set_ylabel("nTop output")
    for ax in axes.ravel()[len(keys):]:
        ax.axis("off")
    fig.suptitle(f"{vr.variant.name}: surrogate fit quality per response", fontsize=11, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return _finish(fig, out / f"{vr.variant.name}_fig17_model_fit.png", cr.cfg)


# --------------------------------------------------------------------------- #
def make_all_figures(cr, out: Path | None = None) -> dict[str, Path]:
    out = Path(out or (cr.results_dir / "figures"))
    out.mkdir(parents=True, exist_ok=True)
    produced: dict[str, Path] = {}

    def _try(name, fn, *args):
        try:
            p = fn(*args, out)
            if p is not None:
                produced[name] = p
        except Exception as exc:  # noqa: BLE001 - a plotting error must not lose the campaign
            log.warning("figure %s failed: %s", name, exc, exc_info=True)

    _try("objective_definition", fig_objective_definition, cr)
    _try("run_summary", fig_run_summary, cr)
    _try("ranking", fig_ranking, cr)
    _try("compare_metrics", fig_compare_metrics, cr)
    _try("radar", fig_radar, cr)
    _try("weight_robustness", fig_weight_robustness, cr)
    _try("pareto_all", fig_pareto_all, cr)
    _try("optimum_settings", fig_optimum_settings, cr)
    _try("predicted_vs_verified", fig_predicted_vs_verified, cr)
    for vr in cr.variants:
        n = vr.variant.name
        _try(f"{n}/design_space", fig_design_space, vr, cr)
        _try(f"{n}/main_effects", fig_main_effects, vr, cr)
        _try(f"{n}/interactions", fig_interactions, vr, cr)
        _try(f"{n}/response_surfaces", fig_response_surfaces, vr, cr)
        _try(f"{n}/pareto", fig_pareto, vr, cr)
        _try(f"{n}/sensitivity", fig_sensitivity, vr, cr)
        _try(f"{n}/convergence", fig_convergence, vr, cr)
        _try(f"{n}/model_fit", fig_model_fit, vr, cr)
    return produced
