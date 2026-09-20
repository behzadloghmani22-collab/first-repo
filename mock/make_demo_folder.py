#!/usr/bin/env python3
"""Create a folder that mimics the user's working folder for a dry run.

Four ``.ntop`` placeholders (octet, gyroid, diamond, kelvin), an nTopCL input
template next to each, and one prior run for the octet variant.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOCK = HERE / "mock_ntopcl.py"


def template(name: str) -> dict:
    return {
        "description": f"Lumbar fusion cage - {name} lattice",
        "inputs": [
            {"name": "Cell Size", "type": "scalar", "values": 3.0, "units": "mm",
             "description": "Lattice unit-cell size"},
            {"name": "Strut Thickness", "type": "scalar", "values": 0.6, "units": "mm"},
            {"name": "Shell Thickness", "type": "scalar", "values": 1.0, "units": "mm"},
            {"name": "Compressive Load", "type": "scalar", "values": 1200.0, "units": "N"},
            {"name": "Export STL", "type": "text", "value": "cage_export.stl"},
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    args = ap.parse_args()
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    for lat in ("octet", "gyroid", "diamond", "kelvin"):
        folder = root / f"cage_{lat}"
        folder.mkdir(exist_ok=True)
        ntop = folder / f"fusion_cage_{lat}.ntop"
        ntop.write_text(f"placeholder for the {lat} nTop notebook (binary in reality)\n")
        tpl = folder / f"fusion_cage_{lat}_input.json"
        tpl.write_text(json.dumps(template(lat), indent=2))
        if lat == "octet":   # a run has already been made on the octet version
            out = folder / "fusion_cage_octet_output.json"
            subprocess.run([sys.executable, str(MOCK), "-j", str(tpl), "-o", str(out), str(ntop)],
                           check=True, capture_output=True)
    print("demo folder ready:", root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
