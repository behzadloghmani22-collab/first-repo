"""Find the ``.ntop`` variants, their nTopCL input templates and prior runs.

Nothing here talks to nTop.  It only inspects the folder so that the campaign
can be checked (``report/discovery.md``) before a single licence-minute is
spent.
"""
from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import normalise_name

log = logging.getLogger(__name__)

LATTICE_KEYWORDS = [
    "octet", "gyroid", "diamond", "kelvin", "bcc", "fcc", "schwarz",
    "primitive", "neovius", "lidinoid", "voronoi", "cubic", "honeycomb",
    "kagome", "tetra", "iwp", "tpms", "stochastic", "rhombic", "dodecahedron",
    "split-p", "splitp",
]


@dataclass
class PriorRun:
    input_path: Path | None
    output_path: Path
    inputs: dict[str, Any]
    outputs: dict[str, Any]


@dataclass
class Variant:
    name: str
    lattice: str
    ntop: Path
    template_path: Path | None
    template: dict | None
    factor_map: dict[str, str] = field(default_factory=dict)   # factor -> input name
    fixed_map: dict[str, str] = field(default_factory=dict)    # fixed key -> input name
    unmatched_inputs: list[str] = field(default_factory=list)
    path_like_inputs: list[str] = field(default_factory=list)
    prior_runs: list[PriorRun] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def factor_names(self) -> list[str]:
        return list(self.factor_map)


# --------------------------------------------------------------------------- #
# JSON helpers
# --------------------------------------------------------------------------- #
def _load_json(p: Path) -> dict | None:
    try:
        with open(p, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def template_entries(template: dict) -> list[dict]:
    """Return the input entries of an nTopCL JSON as a list of dicts.

    Supports both ``{"inputs": [{"name": ...}, ...]}`` and
    ``{"inputs": {"Name": {...}}}`` shapes.
    """
    inputs = template.get("inputs", [])
    if isinstance(inputs, dict):
        out = []
        for name, entry in inputs.items():
            e = dict(entry) if isinstance(entry, dict) else {"value": entry}
            e["name"] = name
            out.append(e)
        return out
    return [e for e in inputs if isinstance(e, dict)]


def entry_value(entry: dict) -> Any:
    for k in ("values", "value", "val", "data"):
        if k in entry:
            v = entry[k]
            if isinstance(v, dict):
                for kk in ("val", "value", "magnitude", "values"):
                    if kk in v:
                        return v[kk]
            if isinstance(v, list) and len(v) == 1:
                return v[0]
            return v
    return None


def _is_numeric_entry(entry: dict) -> bool:
    t = str(entry.get("type", "")).lower()
    if t in ("scalar", "real", "integer", "int", "number", "float", "double"):
        return True
    v = entry_value(entry)
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_path_like(entry: dict) -> bool:
    t = str(entry.get("type", "")).lower()
    v = entry_value(entry)
    if t in ("file", "path", "directory"):
        return True
    if isinstance(v, str):
        low = v.lower()
        return any(low.endswith(ext) for ext in
                   (".stl", ".step", ".stp", ".obj", ".3mf", ".ntop", ".csv",
                    ".txt", ".json", ".x_t", ".iges", ".igs", ".ply")) or \
            ("\\" in v or "/" in v)
    return False


def output_entries(data: dict) -> dict[str, dict]:
    """Normalise an nTopCL output JSON into ``{name: {"value":..., "units":...}}``."""
    outputs = data.get("outputs", data.get("output", data))
    result: dict[str, dict] = {}
    if isinstance(outputs, list):
        for e in outputs:
            if not isinstance(e, dict):
                continue
            name = e.get("name") or e.get("title")
            if name is None:
                continue
            result[str(name)] = {"value": entry_value(e),
                                 "units": e.get("units", e.get("unit", "")),
                                 "type": e.get("type", "")}
    elif isinstance(outputs, dict):
        for name, e in outputs.items():
            if isinstance(e, dict):
                result[str(name)] = {"value": entry_value(e) if any(
                    k in e for k in ("values", "value", "val", "data")) else e,
                    "units": e.get("units", e.get("unit", "")),
                    "type": e.get("type", "")}
            else:
                result[str(name)] = {"value": e, "units": "", "type": ""}
    return result


# --------------------------------------------------------------------------- #
# Name matching
# --------------------------------------------------------------------------- #
def match_name(candidates: list[str], target: str, aliases: list[str]) -> str | None:
    """Best candidate for ``target`` using exact, alias, then containment matches."""
    if not candidates:
        return None
    norm = {c: normalise_name(c) for c in candidates}
    keys = [normalise_name(target)] + [normalise_name(a) for a in aliases]
    keys = [k for k in keys if k]
    # 1) exact normalised match, in priority order of the keys
    for k in keys:
        for c, n in norm.items():
            if n == k:
                return c
    # 2) containment: prefer the longest key that is contained in the candidate
    best, best_len = None, 0
    for k in keys:
        for c, n in norm.items():
            if (f" {k} " in f" {n} " or n in k) and len(k) > best_len:
                best, best_len = c, len(k)
    return best


def detect_lattice(name: str) -> str:
    n = normalise_name(name)
    for kw in LATTICE_KEYWORDS:
        if kw in n:
            return kw
    return n.replace(" ", "_") or "variant"


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #
def _excluded(p: Path, patterns: list[str]) -> bool:
    """True when any path component contains one of the patterns (case-insensitive)."""
    parts = [part.lower() for part in p.parts]
    return any(pat.lower() in part for pat in patterns for part in parts if pat)


def exclusions(cfg: dict) -> list[str]:
    return list(cfg.get("exclude_patterns", [])) + [cfg["project"].get("results_dirname", "DOE_results")]


def find_ntop_files(root: Path, exclude_patterns: list[str]) -> list[Path]:
    files = sorted(p for p in root.rglob("*.ntop") if not _excluded(p, exclude_patterns))
    return files


def _sibling_jsons(ntop: Path, exclude_patterns: list[str]) -> list[Path]:
    folder = ntop.parent
    files = [p for p in folder.glob("*.json") if not _excluded(p, exclude_patterns)]
    for sub in folder.iterdir():
        if sub.is_dir() and not _excluded(sub, exclude_patterns):
            files.extend(p for p in sub.glob("*.json") if not _excluded(p, exclude_patterns))
    return sorted(set(files))


def _template_rank(p: Path, ntop: Path) -> tuple:
    stem = p.stem.lower()
    return (0 if ntop.stem.lower() in stem else 1,
            0 if "input" in stem else 1,
            0 if "template" in stem else 1,
            -p.stat().st_mtime)


def find_templates_and_priors(ntop: Path, exclude_patterns: list[str]
                              ) -> tuple[list[Path], list[PriorRun]]:
    templates: list[Path] = []
    outputs: list[tuple[Path, dict]] = []
    inputs_by_path: dict[Path, dict] = {}
    for p in _sibling_jsons(ntop, exclude_patterns):
        data = _load_json(p)
        if not data:
            continue
        if "inputs" in data and "outputs" not in data:
            templates.append(p)
            inputs_by_path[p] = data
        elif "outputs" in data:
            outputs.append((p, data))
    templates.sort(key=lambda p: _template_rank(p, ntop))
    priors: list[PriorRun] = []
    for op, odata in outputs:
        paired: Path | None = None
        stem = op.stem.lower().replace("output", "input").replace("out", "in")
        for tp in templates:
            if tp.stem.lower() == stem or (tp.parent == op.parent and len(templates) == 1):
                paired = tp
                break
        in_vals = {}
        if paired is not None:
            in_vals = {e.get("name"): entry_value(e) for e in template_entries(inputs_by_path[paired])}
        priors.append(PriorRun(paired, op, in_vals, output_entries(odata)))
    return templates, priors


def build_variant(cfg: dict, ntop: Path, name: str | None = None,
                  template_path: Path | None = None, lattice: str | None = None) -> Variant:
    excl = exclusions(cfg)
    templates, priors = find_templates_and_priors(ntop, excl)
    if template_path is None and templates:
        template_path = templates[0]
    template = _load_json(template_path) if template_path else None
    v = Variant(name=name or ntop.stem, lattice=lattice or detect_lattice(ntop.stem),
                ntop=ntop, template_path=template_path, template=template,
                prior_runs=priors)
    if len(templates) > 1:
        v.notes.append(f"{len(templates)} input JSON files found; using '{template_path.name}'. "
                       "Set 'variants' explicitly in doe_config.json to pick another.")
    if template is None:
        v.notes.append("No nTopCL input JSON found next to the .ntop file. Inputs will be "
                       "generated from doe_config.json factor names - verify they match the "
                       "Input blocks of the nTop notebook exactly (export the template from "
                       "nTop's Automate panel to be safe).")
        for f in cfg["factors"]:
            v.factor_map[f["name"]] = f["name"]
        for k in cfg.get("fixed_inputs", {}):
            v.fixed_map[k] = k
        return v
    entries = template_entries(template)
    names = [str(e.get("name")) for e in entries if e.get("name") is not None]
    numeric = [str(e.get("name")) for e in entries if e.get("name") is not None and _is_numeric_entry(e)]
    used: set[str] = set()
    for f in cfg["factors"]:
        m = match_name([n for n in numeric if n not in used], f["name"], f.get("aliases", []))
        if m is None:
            v.notes.append(f"factor '{f['name']}' has no matching numeric input in the template "
                           f"(available: {numeric}); it will not be swept for this variant.")
            continue
        v.factor_map[f["name"]] = m
        used.add(m)
    for key in cfg.get("fixed_inputs", {}):
        m = match_name([n for n in names if n not in used], key, [])
        if m is None:
            v.notes.append(f"fixed input '{key}' not found in template; ignored.")
        else:
            v.fixed_map[key] = m
            used.add(m)
    v.unmatched_inputs = [n for n in names if n not in used]
    v.path_like_inputs = [str(e.get("name")) for e in entries if _is_path_like(e)]
    return v


def discover_variants(cfg: dict) -> list[Variant]:
    root = Path(cfg["project"]["root"]).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"project.root does not exist: {root}")
    spec = cfg.get("variants", "auto")
    variants: list[Variant] = []
    if isinstance(spec, list):
        for item in spec:
            ntop = (root / item["ntop"]).resolve() if not Path(item["ntop"]).is_absolute() else Path(item["ntop"])
            if not ntop.exists():
                raise FileNotFoundError(f"variant '{item.get('name')}' .ntop not found: {ntop}")
            tpl = item.get("template")
            tpl_path = None
            if tpl:
                tpl_path = (root / tpl).resolve() if not Path(tpl).is_absolute() else Path(tpl)
            variants.append(build_variant(cfg, ntop, item.get("name"), tpl_path, item.get("lattice")))
    else:
        for ntop in find_ntop_files(root, exclusions(cfg)):
            variants.append(build_variant(cfg, ntop))
    if not variants:
        raise FileNotFoundError(f"no .ntop files found under {root}")
    # Unique, readable names
    seen: dict[str, int] = {}
    for v in variants:
        base = v.name
        if base in seen:
            seen[base] += 1
            v.name = f"{base}_{seen[base]}"
        else:
            seen[base] = 1
    return variants


def discovery_report(variants: list[Variant], cfg: dict) -> str:
    lines = ["# Discovery report", "",
             f"Root: `{Path(cfg['project']['root']).resolve()}`", "",
             f"{len(variants)} variant(s) found.", ""]
    for v in variants:
        lines += [f"## {v.name}  (lattice: {v.lattice})", "",
                  f"- nTop file: `{v.ntop}`",
                  f"- input template: `{v.template_path}`" if v.template_path else "- input template: **none**",
                  f"- prior runs with outputs: {len(v.prior_runs)}", "",
                  "| factor | nTop input | range |", "|---|---|---|"]
        for f in cfg["factors"]:
            if f["name"] in v.factor_map:
                lines.append(f"| {f['name']} | {v.factor_map[f['name']]} | {f['low']} - {f['high']} {f['units']} |")
            else:
                lines.append(f"| {f['name']} | *not matched* | - |")
        if v.fixed_map:
            lines += ["", "Fixed inputs: " + ", ".join(f"`{k}` -> `{m}`" for k, m in v.fixed_map.items())]
        if v.unmatched_inputs:
            lines += ["", "Template inputs kept at their template values: " +
                      ", ".join(f"`{n}`" for n in v.unmatched_inputs)]
        if v.path_like_inputs:
            lines += ["", "Path-like inputs (add to `per_run_path_inputs` if each run must export "
                      "to its own file): " + ", ".join(f"`{n}`" for n in v.path_like_inputs)]
        for n in v.notes:
            lines.append(f"- **Note:** {n}")
        lines.append("")
    return "\n".join(lines)


def variant_summary(v: Variant) -> dict:
    return {"name": v.name, "lattice": v.lattice, "ntop": str(v.ntop),
            "template": str(v.template_path) if v.template_path else None,
            "factor_map": v.factor_map, "fixed_map": v.fixed_map,
            "prior_runs": len(v.prior_runs), "notes": v.notes}


def clone_template(v: Variant) -> dict | None:
    return copy.deepcopy(v.template) if v.template else None
