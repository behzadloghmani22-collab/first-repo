#!/usr/bin/env python3
"""Stand-in for ``ntopcl.exe`` so the campaign can be exercised without nTop.

Same command line as nTopCL::

    python mock_ntopcl.py -j input.json -o output.json model.ntop

It reads the swept inputs (cell size, strut/sheet thickness, shell thickness,
load), decides the lattice type from the ``.ntop`` file name and returns
outputs computed from textbook lattice mechanics (Gibson-Ashby scaling,
parallel load sharing between rim and lattice, node/contact stress
concentration).  The numbers are *plausible*, not nTop results: every figure
produced from this mock is watermarked "SURROGATE DEMO".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

E_S = 110_000.0        # MPa, Ti-6Al-4V
RHO = 4.43e-3          # g/mm^3
FOOTPRINT = 500.0      # mm^2
PERIMETER = 85.0       # mm
HEIGHT = 12.0          # mm
SHELL_EFF = 0.30       # windowed rim carries only part of a solid rim's load

# lattice: (C_rho, n_rho, C1, n1, K, beta, pore_kappa, sheet?)
LATTICES = {
    "octet":   (6.66, 2, 0.15, 1.10, 5.0, 0.12, 0.55, False),
    "gyroid":  (3.09, 1, 0.30, 1.40, 4.5, 0.10, 0.55, True),
    "diamond": (5.44, 2, 0.25, 1.80, 6.0, 0.25, 0.65, False),
    "kelvin":  (6.66, 2, 0.35, 2.00, 6.5, 0.30, 0.60, False),
    "bcc":     (2.72, 2, 0.20, 2.10, 7.0, 0.35, 0.65, False),
    "fcc":     (6.66, 2, 0.28, 1.60, 5.5, 0.15, 0.55, False),
    "schwarz": (2.35, 1, 0.28, 1.50, 4.8, 0.10, 0.55, True),
    "default": (5.00, 2, 0.30, 1.80, 6.0, 0.25, 0.58, False),
}


def norm(s: str) -> str:
    s = re.sub(r"[\(\[].*?[\)\]]", " ", str(s)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def read_inputs(path: Path) -> dict[str, float]:
    with open(path, "r", encoding="utf-8-sig") as fh:
        data = json.load(fh)
    entries = data.get("inputs", [])
    if isinstance(entries, dict):
        entries = [{"name": k, **(v if isinstance(v, dict) else {"value": v})} for k, v in entries.items()]
    out: dict[str, float] = {}
    for e in entries:
        name = norm(e.get("name", ""))
        val = None
        for k in ("values", "value", "val"):
            if k in e:
                val = e[k]
                break
        if isinstance(val, list) and len(val) == 1:
            val = val[0]
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            out[name] = float(val)
    return out


def pick(inputs: dict[str, float], *keys: str) -> float | None:
    for k in keys:
        for name, v in inputs.items():
            if k == name or k in name:
                return v
    return None


def lattice_of(ntop: Path) -> str:
    n = norm(ntop.stem)
    for key in LATTICES:
        if key != "default" and key in n:
            return key
    return "default"


def noise(seed_src: str, amp: float) -> float:
    h = int(hashlib.sha1(seed_src.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return 1.0 + amp * (2.0 * h - 1.0)


def simulate(inputs: dict[str, float], lattice: str, tag: str) -> dict:
    a = pick(inputs, "cell size", "unit cell", "cell")
    t = pick(inputs, "strut thickness", "sheet thickness", "beam thickness", "thickness", "strut")
    ts = pick(inputs, "shell thickness", "rim thickness", "wall thickness", "shell")
    F = pick(inputs, "load", "force") or 1200.0
    if a is None or t is None:
        raise ValueError("Input 'Cell Size' or 'Strut Thickness' not found in input JSON")
    ts = 1.0 if ts is None else ts
    C_rho, n_rho, C1, n1, K, beta, kappa, sheet = LATTICES[lattice]
    rho = C_rho * (t / a) ** n_rho
    rho *= (1.0 - 0.35 * min(rho, 0.9))            # node / sheet overlap correction
    rho *= noise(tag + "rho", 0.02)
    if rho >= 0.90 or t >= 0.48 * a:
        raise RuntimeError("Error: lattice thickening produced a solid body (self-intersecting struts)")
    if rho < 0.02:
        raise RuntimeError("Error: lattice is disconnected (relative density below 2%)")
    A_sh = min(PERIMETER * ts, FOOTPRINT * 0.6)
    A_lat = FOOTPRINT - A_sh
    V_env = FOOTPRINT * HEIGHT
    V_lat = A_lat * HEIGHT * rho + A_sh * HEIGHT
    E_lat = E_S * C1 * rho ** n1 * noise(tag + "E", 0.03)
    k_sh = E_S * A_sh * SHELL_EFF / HEIGHT
    k_lat = E_lat * A_lat / HEIGHT
    k = k_sh + k_lat
    delta = F / k
    F_lat = F * k_lat / k
    sig_nom = F_lat / A_lat
    sig_strut = sig_nom * K * (1.0 / rho) * (1.0 + beta * (a / t)) * noise(tag + "s", 0.04)
    sig_shell = E_S * delta / HEIGHT * 1.2
    sig_max = max(sig_strut, sig_shell)
    # surface area: struts as cylinders (or two faces of a TPMS sheet) + rim
    if sheet:
        surf = 2.0 * C_rho * (A_lat * HEIGHT) / a
    else:
        n_eff = C_rho * 4.0 / math.pi  # effective strut count x length factor per cell
        surf = n_eff * math.pi * t * (A_lat * HEIGHT) / a ** 2
    surf += 2.0 * PERIMETER * HEIGHT
    surf *= noise(tag + "A", 0.02)
    pore_mm = max(kappa * a - t, 0.0)
    outputs = [
        {"name": "Lattice Volume", "type": "scalar", "value": round(V_lat, 4), "units": "mm^3"},
        {"name": "Envelope Volume", "type": "scalar", "value": round(V_env, 4), "units": "mm^3"},
        {"name": "Mass", "type": "scalar", "value": round(V_lat * RHO / 1000.0, 6), "units": "kg"},
        {"name": "Surface Area", "type": "scalar", "value": round(surf, 3), "units": "mm^2"},
        {"name": "Max von Mises Stress", "type": "scalar", "value": round(sig_max, 4), "units": "MPa"},
        {"name": "Max Displacement", "type": "scalar", "value": round(delta, 7), "units": "mm"},
        {"name": "Minimum Thickness", "type": "scalar", "value": round(t, 4), "units": "mm"},
        {"name": "Solve Time", "type": "scalar", "value": round(30 + 400 * rho, 1), "units": "s"},
    ]
    if sheet:
        outputs.append({"name": "Pore Diameter", "type": "scalar", "value": round(pore_mm, 4), "units": "mm"})
    return {"description": f"mock nTopCL result for {lattice} lattice", "outputs": outputs}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mock_ntopcl")
    p.add_argument("-j", "--json", required=True)
    p.add_argument("-o", "--output", required=True)
    p.add_argument("-v", "--verbose", default=None)
    p.add_argument("-e", "--exit", action="store_true")
    p.add_argument("-l", "--log", default=None)
    p.add_argument("ntop")
    args = p.parse_args(argv)
    ntop = Path(args.ntop)
    if not ntop.exists():
        print(f"Error: file not found: {ntop}")
        return 1
    print(f"mock nTopCL - loading {ntop.name}")
    try:
        inputs = read_inputs(Path(args.json))
        lattice = lattice_of(ntop)
        tag = f"{lattice}|{json.dumps(inputs, sort_keys=True)}"
        result = simulate(inputs, lattice, tag)
    except (RuntimeError, ValueError) as exc:
        print(str(exc))
        return 2
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print("Outputs written to", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
