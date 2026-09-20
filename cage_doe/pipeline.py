"""Campaign orchestration: discovery -> designs -> nTopCL runs -> surrogates ->
optimisation -> verification -> cross-lattice comparison.

Every run is cached on disk (``results/runs/<variant>/<run_id>``) so the
campaign can be stopped and re-launched at any time.
"""
from __future__ import annotations

import json
import logging
import time
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import design, objectives, optimize
from .discover import Variant, discover_variants, discovery_report, variant_summary
from .ntopcl import NTopCLRunner, RunResult
from .surrogate import FailureModel, ResponseModel, fit_response_models

log = logging.getLogger(__name__)

PHASES = ["prior", "screen", "rsm", "lhs", "infill", "verify"]
METRIC_KEYS = ["porosity", "mass_g", "stiffness_N_mm", "E_app_GPa", "max_stress_MPa",
               "max_stress_peak_MPa", "sf_yield", "sf_fatigue", "pore_um", "pore_estimated",
               "strut_mm", "surface_area_mm2", "specific_surface_1_mm", "lattice_volume_mm3",
               "max_displacement_mm", "cell_mm", "relative_density"]
PRED_KEYS = ["E_app_GPa", "porosity", "pore_um", "sf_yield", "sf_fatigue", "mass_g",
             "max_stress_MPa", "D"]


@dataclass
class VariantResult:
    variant: Variant
    factors: list[dict]
    runs: pd.DataFrame
    models: dict[str, ResponseModel] = field(default_factory=dict)
    constants: dict[str, float] = field(default_factory=dict)
    model_diag: pd.DataFrame | None = None
    predictor: optimize.Predictor | None = None
    ranges: dict = field(default_factory=dict)
    optimum: dict | None = None
    optimum_coded: np.ndarray | None = None
    verified: list[dict] = field(default_factory=list)
    best_run: dict | None = None
    recommended: dict | None = None
    cloud_X: np.ndarray | None = None
    cloud_rows: list[dict] = field(default_factory=list)
    pareto: dict | None = None
    sobol: dict | None = None
    top_factors: tuple[int, int] = (0, 1)
    main_effects: dict | None = None
    interactions: dict | None = None
    grids: dict = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    output_mapping: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def k(self) -> int:
        return len(self.factors)

    @property
    def names(self) -> list[str]:
        return [f["name"] for f in self.factors]

    @property
    def lows(self) -> np.ndarray:
        return np.array([f["low"] for f in self.factors], float)

    @property
    def highs(self) -> np.ndarray:
        return np.array([f["high"] for f in self.factors], float)


@dataclass
class CampaignResult:
    cfg: dict
    results_dir: Path
    variants: list[VariantResult]
    runs: pd.DataFrame
    ranking: pd.DataFrame
    robustness: dict | None
    discovery_md: str
    started: str
    finished: str
    mock: bool = False


# --------------------------------------------------------------------------- #
class Dataset:
    """Rows of one variant's runs, in real factor units + canonical responses."""

    def __init__(self, variant: Variant, factors: list[dict], cfg: dict):
        self.variant, self.factors, self.cfg = variant, factors, cfg
        self.rows: list[dict] = []
        self.mapping: dict[str, str] = {}
        self.new_runs = 0

    @property
    def names(self) -> list[str]:
        return [f["name"] for f in self.factors]

    def add(self, assignments: dict[str, float], result: RunResult, phase: str,
            kind: str = "", pred: dict | None = None) -> dict:
        values, mapping, extra = objectives.map_outputs(result.outputs, self.cfg) if result.outputs else ({}, {}, {})
        if mapping and not self.mapping:
            self.mapping = mapping
        met = objectives.derive_metrics(values, assignments, self.variant.lattice, self.cfg) \
            if result.status in ("ok", "cached") else {k: np.nan for k in METRIC_KEYS}
        row = {"variant": self.variant.name, "lattice": self.variant.lattice, "run_id": result.run_id,
               "phase": phase, "kind": kind, "status": result.status, "elapsed_s": result.elapsed_s,
               "message": result.message}
        row.update({n: float(assignments.get(n, np.nan)) for n in self.names})
        row.update({f"resp_{k}": v for k, v in values.items()})
        row.update({f"out_{k}": v for k, v in extra.items()})
        row.update({k: met.get(k, np.nan) for k in METRIC_KEYS})
        if pred:
            row.update({f"pred_{k}": pred.get(k, np.nan) for k in PRED_KEYS})
        row["_outputs"] = result.outputs
        self.rows.append(row)
        if phase != "prior":
            self.new_runs += 1
        return row

    def find_identical(self, assignments: dict[str, float], tol: float = 1e-9) -> dict | None:
        for r in self.rows:
            if r["status"] in ("ok", "cached") and all(abs(r.get(n, np.nan) - v) <= tol for n, v in assignments.items()):
                return {"run_id": r["run_id"], "outputs": r["_outputs"]}
        return None

    def frame(self) -> pd.DataFrame:
        if not self.rows:
            return pd.DataFrame(columns=["variant", "phase", "status", *self.names])
        return pd.DataFrame([{k: v for k, v in r.items() if k != "_outputs"} for r in self.rows])

    def ok_frame(self) -> pd.DataFrame:
        df = self.frame()
        return df[df["status"].isin(["ok", "cached"])].copy()

    def X_coded(self, df: pd.DataFrame | None = None) -> np.ndarray:
        df = self.frame() if df is None else df
        if df.empty:
            return np.zeros((0, len(self.names)))
        lows = np.array([f["low"] for f in self.factors], float)
        highs = np.array([f["high"] for f in self.factors], float)
        return design.encode(df[self.names].to_numpy(float), lows, highs)


def campaign_ranges(df: pd.DataFrame) -> dict[str, tuple[float, float]]:
    out = {}
    for key in ("mass_g", "surface_area_mm2"):
        if key in df and df[key].notna().any():
            out[key] = (float(np.nanmin(df[key])), float(np.nanmax(df[key])))
    return out


def score_frame(df: pd.DataFrame, cfg: dict, ranges: dict) -> pd.DataFrame:
    df = df.copy()
    comps = {k: [] for k in cfg["objectives"]["weights"]}
    Ds, feas = [], []
    for _, r in df.iterrows():
        if r.get("status") in ("ok", "cached"):
            des = objectives.desirability(r.to_dict(), cfg, ranges)
            for k in comps:
                comps[k].append(des["components"].get(k, np.nan))
            Ds.append(des["D"])
            feas.append(des["feasible"])
        else:
            for k in comps:
                comps[k].append(np.nan)
            Ds.append(np.nan)
            feas.append(False)
    for k, v in comps.items():
        df[f"d_{k}"] = v
    df["D"] = Ds
    df["feasible"] = feas
    df["modulus_dev"] = (df["E_app_GPa"] - cfg["objectives"]["target_modulus_GPa"]).abs()
    return df


# --------------------------------------------------------------------------- #
class Campaign:
    def __init__(self, cfg: dict, runner: NTopCLRunner, results_dir: Path, mock: bool = False,
                 phases: list[str] | None = None):
        self.cfg = cfg
        self.runner = runner
        self.results_dir = Path(results_dir)
        self.mock = mock
        self.phases = phases or PHASES
        self.seed = int(cfg["project"].get("random_seed", 42))
        self.log_keys = list(cfg["doe"].get("log_transform_responses", []))
        self.all_rows: list[pd.DataFrame] = []
        for sub in ("runs", "figures", "data", "report", "presentation"):
            (self.results_dir / sub).mkdir(parents=True, exist_ok=True)

    # ---- helpers -------------------------------------------------------- #
    def _current_ranges(self, ds: Dataset) -> dict:
        frames = [f for f in self.all_rows] + [ds.ok_frame()]
        frames = [f for f in frames if not f.empty]
        return campaign_ranges(pd.concat(frames)) if frames else {}

    def _run_points(self, ds: Dataset, Xc: np.ndarray, phase: str, kinds: list[str] | None = None,
                    preds: list[dict] | None = None, budget: int | None = None) -> int:
        n_done = 0
        for i, xc in enumerate(Xc):
            if budget is not None and ds.new_runs >= budget:
                ds_note = f"budget of {budget} runs reached; skipped remaining {len(Xc) - i} {phase} points"
                log.warning("%s: %s", ds.variant.name, ds_note)
                self._notes.append(ds_note)
                break
            assign = design.coded_to_assignments(xc, ds.factors)
            t0 = time.time()
            twin = ds.find_identical(assign)
            if twin is not None:      # never spend a licence run on a design already computed
                res = RunResult(f"{phase}_{twin['run_id']}", "cached", 0.0, twin["outputs"],
                                f"same design as {twin['run_id']}")
            else:
                res = self.runner.run(ds.variant, assign, phase)
            if res.status == "skip":
                continue
            kind = kinds[i] if kinds else ""
            pred = preds[i] if preds else None
            row = ds.add(assign, res, phase, kind, pred)
            n_done += 1
            log.info("%-10s %-8s %-18s %-7s %6.1fs  %s", ds.variant.name, phase, res.run_id, res.status,
                     time.time() - t0, "  ".join(f"{n}={assign[n]:g}" for n in ds.names))
            if res.status in ("ok", "cached"):
                log.info("%s", "  ".join(f"{k}={row.get(k):.4g}" for k in
                                         ("porosity", "E_app_GPa", "max_stress_MPa", "mass_g")
                                         if isinstance(row.get(k), float) and np.isfinite(row.get(k))))
        return n_done

    def _fit(self, ds: Dataset) -> tuple[dict[str, ResponseModel], dict[str, float], FailureModel, pd.DataFrame]:
        ok = ds.ok_frame()
        X = ds.X_coded(ok)
        Y, constants = {}, {}
        for col in ok.columns:
            if not col.startswith("resp_"):
                continue
            y = ok[col].to_numpy(float)
            key = col[len("resp_"):]
            if np.sum(np.isfinite(y)) == 0:
                continue
            if np.nanstd(y) <= 1e-12 * max(1.0, abs(np.nanmean(y))):
                constants[key] = float(np.nanmean(y))
            else:
                Y[key] = y
        models = fit_response_models(X, Y, ds.frame().shape[1] and len(ds.names), self.log_keys)
        allf = ds.frame()
        failed = (~allf["status"].isin(["ok", "cached"])).to_numpy(float)
        fm = FailureModel(ds.X_coded(allf), failed)
        diag = pd.DataFrame([{"response": k, **m.diagnostics} for k, m in models.items()])
        return models, constants, fm, diag

    def _predictor(self, ds: Dataset, models, constants, fm, ranges) -> optimize.Predictor:
        return optimize.Predictor(models, ds.factors, ds.variant.lattice, self.cfg, ranges, fm,
                                  constants=constants)

    # ---- per-variant campaign ------------------------------------------- #
    def run_variant(self, variant: Variant) -> VariantResult | None:
        cfg, doe = self.cfg, self.cfg["doe"]
        factors = [f for f in cfg["factors"] if f["name"] in variant.factor_map]
        self._notes = []
        if not factors:
            log.error("%s: no factors matched; skipping", variant.name)
            return None
        k = len(factors)
        ds = Dataset(variant, factors, cfg)
        budget = int(doe.get("budget_per_variant", 10 ** 6))
        verify_n = int(doe.get("verify_top_n", 0)) if "verify" in self.phases else 0
        design_budget = max(budget - verify_n, 0)
        history: list[dict] = []

        def snapshot(label: str):
            ok = ds.ok_frame()
            if ok.empty:
                history.append({"label": label, "n_runs": len(ds.frame()), "best_D": np.nan})
                return
            sc = score_frame(ok, cfg, self._current_ranges(ds))
            history.append({"label": label, "n_runs": len(ds.frame()),
                            "best_D": float(np.nanmax(sc["D"])) if sc["D"].notna().any() else np.nan})

        # prior runs (e.g. the octet run that already exists)
        if "prior" in self.phases:
            for pr in variant.prior_runs:
                names = [variant.factor_map[f["name"]] for f in factors]
                if not all(n in pr.inputs and isinstance(pr.inputs[n], (int, float)) for n in names):
                    self._notes.append(f"prior output {pr.output_path.name} could not be paired with "
                                       "factor values; imported for reference only")
                    continue
                assign = {f["name"]: float(pr.inputs[variant.factor_map[f["name"]]]) for f in factors}
                res = RunResult(f"prior_{pr.output_path.stem}", "ok", 0.0, pr.outputs, "imported", pr.input_path,
                                pr.output_path, None)
                ds.add(assign, res, "prior")
                log.info("%s: imported prior run %s", variant.name, pr.output_path.name)
            snapshot("prior")

        # screening
        if "screen" in self.phases and doe.get("screening", "none") != "none":
            X = design.full_factorial(k) if doe["screening"] == "full_factorial" else design.fractional_factorial(k)
            X = np.vstack([X, design.center_points(k, int(doe.get("center_points", 1)))])
            X = design.dedupe(X, ds.X_coded())
            self._run_points(ds, X, "screen", budget=design_budget)
            snapshot("screen")

        # response-surface design
        if "rsm" in self.phases and doe.get("rsm", "none") != "none":
            X = design.ccd_face(k) if doe["rsm"] == "ccd_face" else design.box_behnken(k)
            if doe.get("screening", "none") == "none":
                X = np.vstack([X, design.center_points(k, int(doe.get("center_points", 1)))])
            X = design.dedupe(X, ds.X_coded())
            self._run_points(ds, X, "rsm", budget=design_budget)
            snapshot("rsm")

        # space filling
        if "lhs" in self.phases and int(doe.get("lhs_runs", 0)) > 0:
            X = design.lhs(int(doe["lhs_runs"]), k, seed=self.seed + zlib.crc32(variant.name.encode()) % 1000)
            X = design.dedupe(X, ds.X_coded())
            self._run_points(ds, X, "lhs", budget=design_budget)
            snapshot("lhs")

        # adaptive infill
        if "infill" in self.phases:
            for it in range(int(doe.get("infill_iterations", 0))):
                if ds.ok_frame().shape[0] < k + 2:
                    self._notes.append("too few successful runs for infill")
                    break
                models, constants, fm, _ = self._fit(ds)
                pred = self._predictor(ds, models, constants, fm, self._current_ranges(ds))
                Xn, kinds = optimize.infill_points(pred, ds.X_coded(), k, int(doe.get("infill_per_iteration", 1)),
                                                   seed=self.seed + it)
                Xn_d = design.dedupe(Xn, ds.X_coded(), tol=1e-3)
                kinds = kinds[: len(Xn_d)]
                if len(Xn_d) == 0:
                    break
                preds = [{kk: r.get(kk, np.nan) for kk in PRED_KEYS[:-1]} | {"D": r["D_adj"]}
                         for r in pred.rows(Xn_d)]
                self._run_points(ds, Xn_d, f"infill{it + 1}", kinds, preds, budget=design_budget)
                snapshot(f"infill{it + 1}")

        # final fit, optimisation, verification
        ok = ds.ok_frame()
        if ok.shape[0] < k + 2:
            self._notes.append("not enough successful runs to fit a surrogate")
            vr = VariantResult(variant, factors, score_frame(ds.frame(), cfg, self._current_ranges(ds)),
                               history=history, notes=self._notes, output_mapping=ds.mapping)
            self.all_rows.append(vr.runs[vr.runs["status"].isin(["ok", "cached"])])
            return vr
        models, constants, fm, diag = self._fit(ds)
        ranges = self._current_ranges(ds)
        pred = self._predictor(ds, models, constants, fm, ranges)
        candidates = self._verification_candidates(pred, ds, k, max(verify_n, 1))
        opt_x = candidates[0]
        opt_row = pred.rows(opt_x[None, :])[0]
        if "verify" in self.phases and verify_n > 0:
            preds = [{kk: r.get(kk, np.nan) for kk in PRED_KEYS[:-1]} | {"D": r["D_adj"]}
                     for r in pred.rows(candidates[:verify_n])]
            self._run_points(ds, candidates[:verify_n], "verify",
                             ["optimum"] + [f"alt{i}" for i in range(1, verify_n)], preds, budget=budget)
            snapshot("verify")
            # refit including the verification runs so the reported model uses all evidence
            models, constants, fm, diag = self._fit(ds)
            ranges = self._current_ranges(ds)
            pred = self._predictor(ds, models, constants, fm, ranges)
        runs = score_frame(ds.frame(), cfg, ranges)
        vr = VariantResult(variant, factors, runs, models, constants, diag, pred, ranges,
                           optimum=opt_row, optimum_coded=opt_x, history=history,
                           notes=self._notes, output_mapping=ds.mapping)
        self._analyse(vr)
        self.all_rows.append(vr.runs[vr.runs["status"].isin(["ok", "cached"])])
        return vr

    def _verification_candidates(self, pred: optimize.Predictor, ds: Dataset, k: int, n: int) -> np.ndarray:
        cands: list[np.ndarray] = []
        for s in range(max(2 * n, 3)):
            x, _ = optimize.optimise(pred, k, seed=self.seed + 100 * s)
            if all(np.linalg.norm(x - c) > 0.25 for c in cands):
                cands.append(x)
            if len(cands) >= n:
                break
        if len(cands) < n:
            Xc, rows = optimize.candidate_cloud(pred, k, seed=self.seed)
            D = np.array([r["D_adj"] if np.isfinite(r["D_adj"]) else -1 for r in rows])
            order = np.argsort(-D)
            for i in order:
                if D[i] <= 0:
                    break
                if all(np.linalg.norm(Xc[i] - c) > 0.25 for c in cands):
                    cands.append(Xc[i])
                if len(cands) >= n:
                    break
        # rank candidates by predicted desirability
        scored = sorted(cands, key=lambda c: -pred.rows(c[None, :])[0]["D_adj"])
        return np.array(scored)

    def _analyse(self, vr: VariantResult) -> None:
        pred, k = vr.predictor, vr.k
        runs = vr.runs
        okr = runs[runs["status"].isin(["ok", "cached"]) & runs["D"].notna()]
        if not okr.empty and okr["feasible"].any():
            best = okr[okr["feasible"]].sort_values("D", ascending=False).iloc[0]
            vr.best_run = best.to_dict()
        ver = runs[runs["phase"] == "verify"]
        vr.verified = [r.to_dict() for _, r in ver.iterrows()]
        # the recommended design: verified optimum if feasible, else best observed feasible run
        rec = None
        vok = ver[ver["status"].isin(["ok", "cached"]) & ver["feasible"]]
        if not vok.empty:
            rec = vok.sort_values("D", ascending=False).iloc[0].to_dict()
            rec["source"] = "verified"
        elif vr.best_run is not None:
            rec = dict(vr.best_run)
            rec["source"] = "best observed run"
        vr.recommended = rec
        # sensitivity + effects
        try:
            vr.sobol = optimize.sobol_indices(pred, k, n=512 if k <= 3 else 256, seed=self.seed)
            order = np.argsort(-vr.sobol["ST"])
            vr.top_factors = (int(order[0]), int(order[1])) if k >= 2 else (0, 0)
        except Exception as exc:  # noqa: BLE001 - analysis must never kill the campaign
            log.warning("%s: sensitivity failed: %s", vr.variant.name, exc)
            vr.top_factors = (0, 1 if k > 1 else 0)
        fixed = vr.optimum_coded if vr.optimum_coded is not None else np.zeros(k)
        vr.main_effects = optimize.main_effects(pred, k, base=fixed)
        vr.interactions = optimize.interaction_effects(pred, k, n_grid=25, base=fixed) if k >= 2 else {}
        i, j = vr.top_factors
        if k >= 2:
            gi, gj, rows = optimize.response_grid(pred, k, i, j, fixed, n=61)
            vr.grids = {"i": i, "j": j, "gi": gi, "gj": gj, "rows": rows}
        vr.cloud_X, vr.cloud_rows = optimize.candidate_cloud(pred, k, n=3000, seed=self.seed + 7)
        vr.pareto = optimize.pareto_masks(vr.cloud_rows)

    # ---- whole campaign ------------------------------------------------- #
    def run(self, variants: list[Variant]) -> CampaignResult:
        started = time.strftime("%Y-%m-%d %H:%M:%S")
        disc = discovery_report(variants, self.cfg)
        (self.results_dir / "report" / "discovery.md").write_text(disc, encoding="utf-8")
        results: list[VariantResult] = []
        for v in variants:
            log.info("=" * 78)
            log.info("VARIANT %s (%s)  factors: %s", v.name, v.lattice, list(v.factor_map))
            vr = self.run_variant(v)
            if vr is not None:
                results.append(vr)
        # consistent campaign-wide scoring
        frames = [vr.runs for vr in results if not vr.runs.empty]
        all_runs = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        ranges = campaign_ranges(all_runs[all_runs["status"].isin(["ok", "cached"])]) if not all_runs.empty else {}
        for vr in results:
            vr.ranges = ranges
            vr.runs = score_frame(vr.runs, self.cfg, ranges)
            if vr.predictor is not None:
                vr.predictor.ranges = ranges
                if vr.optimum_coded is not None:
                    vr.optimum = vr.predictor.rows(vr.optimum_coded[None, :])[0]
                self._analyse(vr)
        frames = [vr.runs for vr in results if not vr.runs.empty]
        all_runs = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        ranking = self.rank(results)
        robustness = None
        comps = {vr.variant.name: {c: vr.recommended.get(f"d_{c}", np.nan)
                                   for c in self.cfg["objectives"]["weights"]}
                 for vr in results if vr.recommended}
        if len(comps) >= 2:
            robustness = optimize.weight_robustness(comps, self.cfg["objectives"]["weights"],
                                                    seed=self.seed)
        finished = time.strftime("%Y-%m-%d %H:%M:%S")
        cr = CampaignResult(self.cfg, self.results_dir, results, all_runs, ranking, robustness,
                            disc, started, finished, self.mock)
        self.save(cr)
        return cr

    def rank(self, results: list[VariantResult]) -> pd.DataFrame:
        rows = []
        for vr in results:
            rec = vr.recommended or {}
            opt = vr.optimum or {}
            row = {"variant": vr.variant.name, "lattice": vr.variant.lattice,
                   "D_recommended": rec.get("D", np.nan), "source": rec.get("source", "none"),
                   "D_predicted_optimum": opt.get("D_adj", np.nan),
                   "n_runs": int(len(vr.runs)), "n_ok": int(vr.runs["status"].isin(["ok", "cached"]).sum()),
                   "n_feasible": int(vr.runs["feasible"].sum()) if "feasible" in vr.runs else 0}
            for n in vr.names:
                row[n] = rec.get(n, np.nan)
            for m in ("E_app_GPa", "porosity", "pore_um", "sf_yield", "sf_fatigue", "mass_g",
                      "max_stress_MPa", "surface_area_mm2", "strut_mm"):
                row[m] = rec.get(m, np.nan)
            for c in self.cfg["objectives"]["weights"]:
                row[f"d_{c}"] = rec.get(f"d_{c}", np.nan)
            rows.append(row)
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("D_recommended", ascending=False, na_position="last").reset_index(drop=True)
            df.insert(0, "rank", np.arange(1, len(df) + 1))
        return df

    def save(self, cr: CampaignResult) -> None:
        d = self.results_dir / "data"
        cr.runs.to_csv(d / "runs_all.csv", index=False)
        cr.ranking.to_csv(d / "ranking.csv", index=False)
        diags, sob, opt = [], [], []
        for vr in cr.variants:
            if vr.model_diag is not None and not vr.model_diag.empty:
                diags.append(vr.model_diag.assign(variant=vr.variant.name))
            if vr.sobol is not None:
                for i, n in enumerate(vr.names):
                    sob.append({"variant": vr.variant.name, "factor": n,
                                "S1": float(vr.sobol["S1"][i]), "ST": float(vr.sobol["ST"][i])})
            if vr.optimum:
                opt.append({"variant": vr.variant.name, "kind": "predicted optimum", **{
                    k: v for k, v in vr.optimum.items() if isinstance(v, (int, float, np.floating, bool))}})
            if vr.recommended:
                opt.append({"variant": vr.variant.name, "kind": "recommended (" + vr.recommended.get("source", "") + ")",
                            **{k: v for k, v in vr.recommended.items() if isinstance(v, (int, float, np.floating, bool))}})
            pd.DataFrame(vr.cloud_rows).to_csv(d / f"{vr.variant.name}_surrogate_cloud.csv", index=False) \
                if vr.cloud_rows else None
        if diags:
            pd.concat(diags).to_csv(d / "model_diagnostics.csv", index=False)
        if sob:
            pd.DataFrame(sob).to_csv(d / "sensitivity_sobol.csv", index=False)
        if opt:
            pd.DataFrame(opt).to_csv(d / "optima.csv", index=False)
        summary = {"project": cr.cfg["project"]["name"], "started": cr.started, "finished": cr.finished,
                   "mock": cr.mock, "results_dir": str(cr.results_dir),
                   "variants": [{**variant_summary(vr.variant), "output_mapping": vr.output_mapping,
                                 "notes": vr.notes + vr.variant.notes, "history": vr.history,
                                 "recommended": {k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                                                 for k, v in (vr.recommended or {}).items()
                                                 if not isinstance(v, (list, dict))}}
                                for vr in cr.variants],
                   "objectives": cr.cfg["objectives"], "physics": cr.cfg["physics"], "doe": cr.cfg["doe"]}
        (d / "campaign_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")


def run_campaign(cfg: dict, exe: str | None = None, mock: bool = False,
                 phases: list[str] | None = None, analyze_only: bool = False) -> CampaignResult:
    root = Path(cfg["project"]["root"]).expanduser().resolve()
    results_dir = root / cfg["project"]["results_dirname"]
    results_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(results_dir / "campaign.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(fh)
    try:
        if mock:
            exe = exe or str(Path(__file__).resolve().parent.parent / "mock" / "mock_ntopcl.py")
            cfg["figures"]["watermark"] = cfg["figures"].get("watermark") or "SURROGATE DEMO - not nTop data"
        variants = discover_variants(cfg)
        runner = NTopCLRunner(cfg, results_dir, exe=exe, dry_run=mock, cache_only=analyze_only)
        campaign = Campaign(cfg, runner, results_dir, mock=mock, phases=phases)
        return campaign.run(variants)
    finally:
        logging.getLogger().removeHandler(fh)
        fh.close()
