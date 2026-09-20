"""Command-line entry point: ``python -m cage_doe <command>``."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import __version__
from .config import load_config, write_default_config
from .discover import discover_variants, discovery_report


def _setup_logging(verbose: bool):
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S", stream=sys.stdout)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)


def _cfg_from_args(args) -> dict:
    overrides: dict = {"project": {}, "doe": {}}
    if getattr(args, "root", None):
        overrides["project"]["root"] = args.root
    if getattr(args, "results_dirname", None):
        overrides["project"]["results_dirname"] = args.results_dirname
    if getattr(args, "ntopcl", None):
        overrides["project"]["ntopcl_exe"] = args.ntopcl
    if getattr(args, "seed", None) is not None:
        overrides["project"]["random_seed"] = args.seed
    if getattr(args, "profile", None):
        overrides["doe"]["profile"] = args.profile
    if getattr(args, "budget", None) is not None:
        overrides["doe"]["budget_per_variant"] = args.budget
    if getattr(args, "timeout", None) is not None:
        overrides["project"]["timeout_s"] = args.timeout
    cfg_path = getattr(args, "config", None)
    if cfg_path is None:
        root = Path(overrides["project"].get("root", "."))
        cand = root / "doe_config.json"
        cfg_path = cand if cand.exists() else None
    return load_config(cfg_path, overrides)


def cmd_init(args) -> int:
    root = Path(args.root).expanduser()
    p = write_default_config(root / "doe_config.json", root=str(root.resolve()))
    print(f"wrote {p}\nEdit factor ranges / objectives if needed, then run:\n"
          f'  python -m cage_doe discover --root "{root}"\n  python -m cage_doe run --root "{root}"')
    return 0


def cmd_discover(args) -> int:
    cfg = _cfg_from_args(args)
    variants = discover_variants(cfg)
    print(discovery_report(variants, cfg))
    return 0


def cmd_run(args) -> int:
    from .pipeline import run_campaign
    from .plots import make_all_figures
    from .report import write_report
    cfg = _cfg_from_args(args)
    phases = args.phases.split(",") if args.phases else None
    cr = run_campaign(cfg, exe=args.ntopcl, mock=args.mock, phases=phases, analyze_only=args.analyze_only)
    figures = {} if args.no_figures else make_all_figures(cr)
    md, htm = write_report(cr, figures)
    deck = None
    if not args.no_pptx and figures:
        from .pptx_export import build_deck
        deck = build_deck(cr, figures)
    print("\n" + "=" * 78)
    if cr.mock:
        print("SURROGATE DEMO - results below come from mock_ntopcl.py, not from nTop")
    print(f"results folder : {cr.results_dir}")
    print(f"report         : {htm}")
    if deck:
        print(f"presentation   : {deck}")
    print(f"figures        : {len(figures)} PNG files in {cr.results_dir / 'figures'}")
    if not cr.ranking.empty:
        cols = ["rank", "variant", "D_recommended", "source", "E_app_GPa", "porosity", "pore_um", "sf_yield", "mass_g"]
        print(cr.ranking[[c for c in cols if c in cr.ranking]].to_string(index=False, float_format=lambda v: f"{v:.3g}"))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cage_doe", description="DOE + optimisation of nTop lattice fusion cages via nTopCL")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="write a default doe_config.json into the project folder")
    p.add_argument("--root", required=True, help="folder that contains the .ntop variants")
    p.set_defaults(fn=cmd_init)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", help="path to doe_config.json (default: <root>/doe_config.json if present)")
    common.add_argument("--root", help="folder that contains the .ntop variants")
    common.add_argument("--results-dirname", help="name of the results folder created inside root")
    common.add_argument("-v", "--verbose", action="store_true")

    p = sub.add_parser("discover", parents=[common], help="list variants, templates and matched inputs (no nTop runs)")
    p.set_defaults(fn=cmd_discover)

    p = sub.add_parser("run", parents=[common], help="run the campaign, then figures, report and deck")
    p.add_argument("--ntopcl", help="path to ntopcl.exe (default: auto-detect or NTOPCL_EXE)")
    p.add_argument("--mock", action="store_true", help="use mock/mock_ntopcl.py instead of nTop (dry run)")
    p.add_argument("--profile", choices=["quick", "standard", "thorough"])
    p.add_argument("--budget", type=int, help="maximum new nTop runs per variant")
    p.add_argument("--timeout", type=float, help="seconds allowed per nTop run")
    p.add_argument("--seed", type=int)
    p.add_argument("--phases", help="comma-separated subset of prior,screen,rsm,lhs,infill,verify")
    p.add_argument("--analyze-only", action="store_true", help="no new nTop runs; re-analyse cached runs only")
    p.add_argument("--no-figures", action="store_true")
    p.add_argument("--no-pptx", action="store_true")
    p.set_defaults(fn=cmd_run)

    args = ap.parse_args(argv)
    _setup_logging(getattr(args, "verbose", False))
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
