"""Markdown + HTML summary of the campaign (tables, figures, notes)."""
from __future__ import annotations

import html
from pathlib import Path

import numpy as np
import pandas as pd

from .objectives import COMPONENT_LABELS


class Doc:
    """Accumulates the same content as Markdown and as a stand-alone HTML page."""

    def __init__(self, title: str):
        self.md: list[str] = [f"# {title}", ""]
        self.html: list[str] = [f"<h1>{html.escape(title)}</h1>"]

    def h2(self, t):
        self.md += [f"## {t}", ""]
        self.html.append(f"<h2>{html.escape(t)}</h2>")

    def h3(self, t):
        self.md += [f"### {t}", ""]
        self.html.append(f"<h3>{html.escape(t)}</h3>")

    def p(self, t):
        self.md += [t, ""]
        self.html.append(f"<p>{_inline_html(t)}</p>")

    def warn(self, t):
        self.md += [f"> **{t}**", ""]
        self.html.append(f"<div class='warn'>{_inline_html(t)}</div>")

    def ul(self, items):
        self.md += [f"- {i}" for i in items] + [""]
        self.html.append("<ul>" + "".join(f"<li>{_inline_html(i)}</li>" for i in items) + "</ul>")

    def table(self, df: pd.DataFrame, floatfmt: str = "{:.4g}"):
        if df is None or df.empty:
            self.p("_no data_")
            return
        cols = list(df.columns)
        fmt = lambda v: (floatfmt.format(v) if isinstance(v, (float, np.floating)) and np.isfinite(v)  # noqa: E731
                         else ("" if isinstance(v, (float, np.floating)) else str(v)))
        self.md.append("| " + " | ".join(str(c) for c in cols) + " |")
        self.md.append("|" + "---|" * len(cols))
        for _, r in df.iterrows():
            self.md.append("| " + " | ".join(fmt(r[c]) for c in cols) + " |")
        self.md.append("")
        rows = "".join("<tr>" + "".join(f"<td>{html.escape(fmt(r[c]))}</td>" for c in cols) + "</tr>"
                       for _, r in df.iterrows())
        head = "".join(f"<th>{html.escape(str(c))}</th>" for c in cols)
        self.html.append(f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")

    def img(self, path: Path, caption: str, base: Path):
        rel = Path(path).relative_to(base).as_posix() if Path(path).is_relative_to(base) else str(path)
        self.md += [f"![{caption}]({rel})", "", f"*{caption}*", ""]
        self.html.append(f"<figure><img src='{html.escape(rel)}' alt='{html.escape(caption)}'>"
                         f"<figcaption>{html.escape(caption)}</figcaption></figure>")

    def write(self, md_path: Path, html_path: Path, title: str):
        md_path.write_text("\n".join(self.md), encoding="utf-8")
        css = """
        body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#0b0b0b;background:#fcfcfb;line-height:1.45}
        table{border-collapse:collapse;font-size:0.85rem;margin:0.5rem 0 1rem;display:block;overflow-x:auto}
        th,td{border-bottom:1px solid #e1e0d9;padding:0.3rem 0.55rem;text-align:left;white-space:nowrap}
        th{color:#52514e;font-weight:600}figure{margin:1rem 0}img{max-width:100%;border:1px solid #e1e0d9}
        figcaption{font-size:0.85rem;color:#52514e}.warn{background:#fff4e0;border-left:4px solid #eb6834;padding:0.6rem 0.9rem;margin:0.8rem 0}
        code{background:#f0efec;padding:0 0.25rem;border-radius:3px}h2{margin-top:2rem;border-bottom:1px solid #e1e0d9}
        """
        html_path.write_text("<!doctype html><html><head><meta charset='utf-8'>"
                             f"<title>{html.escape(title)}</title><style>{css}</style></head><body>"
                             + "\n".join(self.html) + "</body></html>", encoding="utf-8")


def _inline_html(t: str) -> str:
    import re
    s = html.escape(t)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def write_report(cr, figures: dict[str, Path]) -> tuple[Path, Path]:
    cfg, o, ph = cr.cfg, cr.cfg["objectives"], cr.cfg["physics"]
    base = cr.results_dir / "report"
    base.mkdir(parents=True, exist_ok=True)
    title = f"{cfg['project']['name']} - DOE and optimisation summary"
    d = Doc(title)
    d.p(f"Campaign ran {cr.started} to {cr.finished}. Results folder: `{cr.results_dir}`.")
    if cr.mock:
        d.warn("These results come from the surrogate stand-in (mock_ntopcl.py), NOT from nTop. "
               "Re-run with the real ntopcl.exe on the .ntop files to obtain presentable numbers.")
    # ---- 1 objective
    d.h2("1. What 'optimal' means here")
    d.p("Each nTop run is scored with a Derringer-Suich desirability: every criterion is mapped to 0-1 "
        "(1 inside its clinical target window, 0 beyond a hard limit) and the criteria are combined with a "
        "weighted geometric mean, so a design that violates any hard limit scores 0.")
    crit = pd.DataFrame([
        ["Apparent modulus E_app = (F/delta) x H / A", f"{o['modulus_band_GPa'][0]}-{o['modulus_band_GPa'][1]} GPa (target {o['target_modulus_GPa']} GPa)",
         f"{o['modulus_hard_GPa'][0]}-{o['modulus_hard_GPa'][1]} GPa", o["weights"]["modulus"],
         "PEEK/bone-like stiffness: limits stress shielding and subsidence while supporting fusion"],
        ["Porosity", f"{o['porosity_band'][0]:.0%}-{o['porosity_band'][1]:.0%}", f"{o['porosity_hard'][0]:.0%}-{o['porosity_hard'][1]:.0%}",
         o["weights"]["porosity"], "open volume for bone in-growth and graft"],
        ["Pore size", f"{o['pore_band_um'][0]:.0f}-{o['pore_band_um'][1]:.0f} um", f"{o['pore_hard_um'][0]:.0f}-{o['pore_hard_um'][1]:.0f} um",
         o["weights"]["pore_size"], "vascularised osteogenesis window"],
        [f"Yield safety factor at {ph['peak_load_N']:.0f} N", f">= {o['sf_yield_good']}", f">= {o['sf_yield_min']}",
         o["weights"]["sf_yield"], f"static strength, sigma_y = {ph['yield_MPa']:.0f} MPa"],
        [f"Fatigue safety factor at {ph['design_load_N']:.0f} N", f">= {o['sf_fatigue_good']}", f">= {o['sf_fatigue_min']}",
         o["weights"]["sf_fatigue"], f"endurance limit {ph['fatigue_MPa']:.0f} MPa"],
        ["Strut / sheet thickness", f">= {o['good_strut_mm']} mm", f">= {o['min_strut_mm']} mm", o["weights"]["strut"],
         "LPBF Ti-6Al-4V printability"],
        ["Mass", "lowest in campaign", "-", o["weights"]["mass"], "tie-breaker"],
        ["Surface area", "highest in campaign", "-", o["weights"]["surface_area"], "tie-breaker (osteo-conduction)"],
    ], columns=["criterion", "full desirability", "hard limit", "weight", "rationale"])
    d.table(crit)
    if "objective_definition" in figures:
        d.img(figures["objective_definition"], "Desirability functions that define 'optimal'", base.parent)
    # ---- 2 campaign design
    d.h2("2. Campaign design")
    doe = cfg["doe"]
    d.ul([f"Factors: " + ", ".join(f"{f['name']} {f['low']}-{f['high']} {f['units']}" for f in cfg["factors"]),
          f"Phases per variant: prior runs imported -> screening ({doe.get('screening')}, {doe.get('center_points')} centre points) "
          f"-> response surface ({doe.get('rsm')}) -> {doe.get('lhs_runs')} Latin-hypercube runs -> "
          f"{doe.get('infill_iterations')} x {doe.get('infill_per_iteration')} adaptive infill runs (exploit / explore / diversify) "
          f"-> verification of the top {doe.get('verify_top_n')} predicted designs in nTop.",
          "Surrogates: quadratic response surface and thin-plate RBF per response; the one with the lower leave-one-out "
          "error is used, their disagreement drives exploration.",
          "Optimiser: differential evolution + Nelder-Mead polish on the surrogate desirability, penalised by the "
          "estimated probability that nTop fails (self-intersecting / solid lattice).",
          f"Loads and material: design load {ph['design_load_N']:.0f} N, peak {ph['peak_load_N']:.0f} N, "
          f"E = {ph['E_solid_GPa']} GPa, yield {ph['yield_MPa']} MPa, endurance {ph['fatigue_MPa']} MPa, "
          f"density {ph['density_g_cm3']} g/cm^3; footprint {cfg['geometry']['footprint_area_mm2']} mm^2, "
          f"height {cfg['geometry']['height_mm']} mm."])
    runs = cr.runs
    if not runs.empty:
        summ = runs.groupby("variant").agg(runs_total=("run_id", "count"),
                                            successful=("status", lambda s: int(s.isin(["ok", "cached"]).sum())),
                                            failed=("status", lambda s: int((~s.isin(["ok", "cached"])).sum())),
                                            feasible=("feasible", "sum")).reset_index()
        d.table(summ)
    if "run_summary" in figures:
        d.img(figures["run_summary"], "Runs per variant", base.parent)
    # ---- 3 ranking
    d.h2("3. Ranking of the lattice types")
    rk = cr.ranking.copy()
    if not rk.empty:
        cols = ["rank", "variant", "lattice", "D_recommended", "source"] + [f["name"] for f in cfg["factors"] if f["name"] in rk] + \
               ["E_app_GPa", "porosity", "pore_um", "sf_yield", "sf_fatigue", "mass_g", "max_stress_MPa"]
        d.table(rk[[c for c in cols if c in rk]])
        best = rk.iloc[0]
        d.p(f"**Recommendation: {best['variant']} ({best['lattice']})** with D = {best['D_recommended']:.3f} "
            f"({best['source']}). Settings: " + ", ".join(f"{f['name']} = {best[f['name']]:.3g} {f['units']}"
                                                          for f in cfg["factors"] if f["name"] in rk and np.isfinite(best[f["name"]])) + ".")
    for key, cap in [("ranking", "Overall desirability and component scores"),
                     ("compare_metrics", "Clinical metrics of each recommended design"),
                     ("radar", "Desirability profile"), ("weight_robustness", "Ranking stability under weight perturbation"),
                     ("pareto_all", "Stiffness-matching vs porosity trade-off across lattice types"),
                     ("optimum_settings", "Recommended factor settings")]:
        if key in figures:
            d.img(figures[key], cap, base.parent)
    # ---- 4 verification
    d.h2("4. Surrogate accuracy at the verified optima")
    rows = []
    for vr in cr.variants:
        for r in vr.verified:
            if r.get("status") in ("ok", "cached"):
                rows.append({"variant": vr.variant.name, "candidate": r.get("kind", ""),
                             "D predicted": r.get("pred_D"), "D nTop": r.get("D"),
                             "E_app pred (GPa)": r.get("pred_E_app_GPa"), "E_app nTop": r.get("E_app_GPa"),
                             "porosity pred": r.get("pred_porosity"), "porosity nTop": r.get("porosity"),
                             "stress pred (MPa)": r.get("pred_max_stress_MPa"), "stress nTop": r.get("max_stress_MPa")})
    d.table(pd.DataFrame(rows))
    if "predicted_vs_verified" in figures:
        d.img(figures["predicted_vs_verified"], "Predicted vs verified", base.parent)
    # ---- 5 per-variant
    d.h2("5. Per-variant results")
    for vr in cr.variants:
        d.h3(f"{vr.variant.name} ({vr.variant.lattice})")
        if vr.recommended:
            rec = vr.recommended
            d.p("Recommended design (" + rec.get("source", "") + "): " +
                ", ".join(f"{n} = {rec[n]:.3g}" for n in vr.names if np.isfinite(rec.get(n, np.nan))) +
                f"; D = {rec['D']:.3f}; E_app = {rec['E_app_GPa']:.2f} GPa, porosity = {rec['porosity']:.2f}, "
                f"pore = {rec['pore_um']:.0f} um{' (estimated from cell/strut size)' if rec.get('pore_estimated') else ''}, "
                f"SF yield = {rec['sf_yield']:.2f}, SF fatigue = {rec['sf_fatigue']:.2f}, mass = {rec['mass_g']:.2f} g.")
            comp = pd.DataFrame([{COMPONENT_LABELS[c]: rec.get(f"d_{c}") for c in o["weights"]}])
            d.table(comp)
        if vr.sobol is not None:
            d.table(pd.DataFrame({"factor": vr.names, "Sobol first-order": vr.sobol["S1"], "Sobol total": vr.sobol["ST"]}))
        if vr.model_diag is not None and not vr.model_diag.empty:
            d.table(vr.model_diag[["response", "n", "chosen", "order", "rsm_r2", "rsm_adj_r2", "loo_rmse_rel", "log"]])
        for key, cap in [("response_surfaces", "Response surfaces"), ("main_effects", "Main effects"),
                         ("interactions", "Interactions"), ("pareto", "Pareto front"), ("sensitivity", "Sensitivity"),
                         ("design_space", "Sampled designs"), ("convergence", "Convergence"), ("model_fit", "Surrogate fit")]:
            fk = f"{vr.variant.name}/{key}"
            if fk in figures:
                d.img(figures[fk], f"{vr.variant.name}: {cap}", base.parent)
        notes = vr.notes + vr.variant.notes
        if notes:
            d.ul([f"Note: {n}" for n in notes])
        if vr.output_mapping:
            d.p("nTop outputs used: " + ", ".join(f"`{v}` -> {k}" for k, v in vr.output_mapping.items()))
    # ---- 6 files
    d.h2("6. Files")
    d.ul(["`data/runs_all.csv` - every run with inputs, nTop outputs, derived metrics and desirabilities",
          "`data/ranking.csv`, `data/optima.csv` - recommended designs", "`data/model_diagnostics.csv`, `data/sensitivity_sobol.csv`",
          "`data/<variant>_surrogate_cloud.csv` - 3000 surrogate evaluations per variant (Pareto clouds)",
          "`runs/<variant>/<run_id>/` - input.json, output.json and ntopcl.log of each nTop run",
          "`figures/` - all PNG figures at 200 dpi", "`presentation/` - PowerPoint deck of the figures",
          "`report/discovery.md` - what was found in the folder and how names were matched"])
    md, htm = base / "summary.md", base / "summary.html"
    d.write(md, htm, title)
    return md, htm
