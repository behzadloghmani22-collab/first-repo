"""Thin, defensive wrapper around ``ntopcl.exe``.

    ntopcl.exe -j <input.json> -o <output.json> <model.ntop>

The input JSON is produced by *mutating the variant's own template*, so the
exact key layout that nTop exported (``values`` vs ``value``, units, types,
descriptions) is preserved and only the swept numbers change.  When no
template exists the documented nTopCL layout is generated from the config.
"""
from __future__ import annotations

import copy
import glob
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .discover import Variant, output_entries, template_entries

log = logging.getLogger(__name__)

CANDIDATE_EXES = [
    r"C:\Program Files\nTopology\nTopology\ntopcl.exe",
    r"C:\Program Files\nTop\nTop\ntopcl.exe",
    r"C:\Program Files\nTopology\nTop\ntopcl.exe",
    r"C:\Program Files\nTop\ntopcl.exe",
    r"C:\Program Files\nTopology\ntopcl.exe",
]


def find_ntopcl(explicit: str | None = None) -> Path | None:
    """Locate the nTopCL executable (explicit path, env var, PATH, common dirs)."""
    for cand in [explicit, os.environ.get("NTOPCL_EXE")]:
        if cand and Path(cand).exists():
            return Path(cand)
    for name in ("ntopcl", "ntopcl.exe", "nTopCL", "nTopCL.exe"):
        w = shutil.which(name)
        if w:
            return Path(w)
    for cand in CANDIDATE_EXES:
        if Path(cand).exists():
            return Path(cand)
    for pattern in (r"C:\Program Files\nTop*\**\ntopcl.exe",
                    r"C:\Program Files (x86)\nTop*\**\ntopcl.exe"):
        hits = glob.glob(pattern, recursive=True)
        if hits:
            return Path(sorted(hits)[-1])
    return None


@dataclass
class RunResult:
    run_id: str
    status: str                      # ok | cached | failed | timeout | missing
    elapsed_s: float
    outputs: dict[str, dict] = field(default_factory=dict)   # name -> {value, units}
    message: str = ""
    input_path: Path | None = None
    output_path: Path | None = None
    log_path: Path | None = None


def assignment_hash(assignments: dict[str, Any], phase: str = "") -> str:
    payload = json.dumps({"phase": phase, "x": {k: round(float(v), 6) for k, v in assignments.items()}},
                         sort_keys=True)
    return hashlib.sha1(payload.encode()).hexdigest()[:8]


def _set_entry_value(entry: dict, value: Any) -> None:
    """Write ``value`` into whatever key the template already uses."""
    for k in ("values", "value", "val", "data"):
        if k in entry:
            cur = entry[k]
            if isinstance(cur, dict):
                for kk in ("val", "value", "magnitude", "values"):
                    if kk in cur:
                        cur[kk] = value
                        return
                cur["val"] = value
                return
            if isinstance(cur, list) and len(cur) == 1:
                entry[k] = [value]
                return
            entry[k] = value
            return
    entry["values"] = value


def build_input_json(variant: Variant, cfg: dict, assignments: dict[str, float],
                     run_dir: Path) -> dict:
    """Return the nTopCL input JSON for one run (template-preserving)."""
    factors = {f["name"]: f for f in cfg["factors"]}
    fixed = cfg.get("fixed_inputs", {})
    per_run_paths = set(cfg.get("per_run_path_inputs", []))
    if variant.template is not None:
        data = copy.deepcopy(variant.template)
        entries = template_entries(data)
        if isinstance(data.get("inputs"), dict):   # dict form -> rewrite as list form
            data["inputs"] = entries
        by_name = {str(e.get("name")): e for e in entries}
        for fname, value in assignments.items():
            iname = variant.factor_map.get(fname)
            if iname is None or iname not in by_name:
                continue
            f = factors.get(fname, {})
            v = int(round(value)) if f.get("type") == "integer" else float(value)
            _set_entry_value(by_name[iname], v)
        for key, value in fixed.items():
            iname = variant.fixed_map.get(key)
            if iname and iname in by_name:
                _set_entry_value(by_name[iname], value)
        for name in per_run_paths:
            if name in by_name:
                old = str(by_name[name].get("value", by_name[name].get("values", "")))
                ext = Path(old).suffix or ".stl"
                _set_entry_value(by_name[name], str(run_dir / f"export{ext}"))
        return data
    # No template: documented nTopCL layout.
    inputs = []
    for fname, value in assignments.items():
        f = factors.get(fname, {"units": "", "type": "scalar"})
        entry = {"name": variant.factor_map.get(fname, fname),
                 "type": "integer" if f.get("type") == "integer" else "scalar",
                 "values": int(round(value)) if f.get("type") == "integer" else float(value)}
        if f.get("units"):
            entry["units"] = f["units"]
        inputs.append(entry)
    for key, value in fixed.items():
        entry = {"name": variant.fixed_map.get(key, key)}
        if isinstance(value, bool):
            entry.update({"type": "boolean", "value": value})
        elif isinstance(value, (int, float)):
            entry.update({"type": "scalar", "values": value})
        else:
            entry.update({"type": "text", "value": str(value)})
        inputs.append(entry)
    return {"description": f"{cfg['project']['name']} - {variant.name} - {run_dir.name}",
            "inputs": inputs}


def parse_output_json(path: Path) -> dict[str, dict]:
    with open(path, "r", encoding="utf-8-sig") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        data = {"outputs": data}
    return output_entries(data)


class NTopCLRunner:
    """Executes one nTopCL run per call, with caching/resume and logging."""

    def __init__(self, cfg: dict, results_dir: Path, exe: str | Path | None = None,
                 dry_run: bool = False, cache_only: bool = False):
        self.cfg = cfg
        self.results_dir = Path(results_dir)
        self.runs_dir = self.results_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = float(cfg["project"].get("timeout_s", 3600))
        self.extra_args = list(cfg["project"].get("extra_ntopcl_args", []))
        self.resume = bool(cfg["project"].get("resume", True))
        self.retry_failed = bool(cfg["project"].get("retry_failed", False))
        self.dry_run = dry_run
        self.cache_only = cache_only
        self.exe = Path(exe) if exe else find_ntopcl(cfg["project"].get("ntopcl_exe"))
        if self.exe is None and self.cache_only:
            self.exe = Path("ntopcl.exe")   # never executed in analyse-only mode
        if self.exe is None:
            raise FileNotFoundError(
                "ntopcl.exe not found. Set project.ntopcl_exe in doe_config.json, the NTOPCL_EXE "
                "environment variable, or pass --ntopcl. For a dry run use --mock.")
        log.info("nTopCL executable: %s", self.exe)

    # ------------------------------------------------------------------ #
    def command(self, input_json: Path, output_json: Path, ntop: Path) -> list[str]:
        exe = str(self.exe)
        cmd: list[str]
        if exe.lower().endswith(".py"):
            cmd = [sys.executable, exe]
        else:
            cmd = [exe]
        cmd += ["-j", str(input_json), "-o", str(output_json)] + self.extra_args + [str(ntop)]
        return cmd

    def run_dir(self, variant: Variant, run_id: str) -> Path:
        return self.runs_dir / variant.name / run_id

    def run(self, variant: Variant, assignments: dict[str, float], phase: str,
            run_id: str | None = None) -> RunResult:
        run_id = run_id or f"{phase}_{assignment_hash(assignments)}"
        rdir = self.run_dir(variant, run_id)
        rdir.mkdir(parents=True, exist_ok=True)
        in_path, out_path, log_path = rdir / "input.json", rdir / "output.json", rdir / "ntopcl.log"
        meta_path = rdir / "run_meta.json"
        payload = build_input_json(variant, self.cfg, assignments, rdir)
        if self.resume and meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                same = all(abs(float(meta["assignments"].get(k, float("nan"))) - float(v)) < 1e-9
                           for k, v in assignments.items())
                if same and meta.get("status") == "ok" and out_path.exists():
                    return RunResult(run_id, "cached", 0.0, parse_output_json(out_path),
                                     "reused existing output", in_path, out_path, log_path)
                if same and meta.get("status") in ("failed", "timeout", "missing") and \
                        (self.cache_only or not self.retry_failed):
                    # a lattice that failed to build will fail again: do not spend licence time on it
                    return RunResult(run_id, meta["status"], 0.0, {}, "cached: " + str(meta.get("message", "")),
                                     in_path, out_path, log_path)
            except (ValueError, KeyError, OSError):
                pass
        if self.cache_only:
            return RunResult(run_id, "skip", 0.0, {}, "not run (analyse-only mode)", in_path, out_path, log_path)
        with open(in_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        if out_path.exists():
            out_path.unlink()
        cmd = self.command(in_path, out_path, variant.ntop)
        t0 = time.time()
        status, message = "ok", ""
        try:
            proc = subprocess.run(cmd, cwd=str(variant.ntop.parent), capture_output=True,
                                  timeout=self.timeout, text=True, errors="replace")
            with open(log_path, "w", encoding="utf-8") as fh:
                fh.write("$ " + " ".join(cmd) + "\n\n")
                fh.write(proc.stdout or "")
                if proc.stderr:
                    fh.write("\n--- stderr ---\n" + proc.stderr)
            if proc.returncode != 0:
                status = "failed"
                message = f"ntopcl exit code {proc.returncode}; see {log_path.name}"
        except subprocess.TimeoutExpired:
            status, message = "timeout", f"exceeded {self.timeout:.0f} s"
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(f"\n--- TIMEOUT after {self.timeout:.0f} s ---\n")
        except OSError as exc:
            status, message = "failed", f"could not start ntopcl: {exc}"
        elapsed = time.time() - t0
        outputs: dict[str, dict] = {}
        if status == "ok":
            if out_path.exists():
                try:
                    outputs = parse_output_json(out_path)
                except ValueError as exc:
                    status, message = "failed", f"output JSON unreadable: {exc}"
            else:
                status, message = "missing", "ntopcl returned 0 but wrote no output JSON"
        meta = {"run_id": run_id, "variant": variant.name, "phase": phase, "assignments": assignments,
                "status": status, "message": message, "elapsed_s": elapsed, "cmd": cmd,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)
        if status != "ok":
            log.warning("run %s/%s %s: %s", variant.name, run_id, status, message)
        return RunResult(run_id, status, elapsed, outputs, message, in_path, out_path, log_path)
