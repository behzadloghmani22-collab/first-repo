"""Colour and style tokens for every figure (validated data-viz palette).

Categorical slots are assigned in a fixed order to the lattice variants and
never cycled; marker shapes are the secondary encoding so identity never
relies on colour alone.  Sequential maps use one hue (blue, light -> dark);
diverging maps use blue <-> red around a neutral grey midpoint.
"""
from __future__ import annotations

import matplotlib
from matplotlib.colors import LinearSegmentedColormap

SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
               "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*"]

SEQUENTIAL_BLUE = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
                   "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab",
                   "#184f95", "#104281", "#0d366b"]
SEQUENTIAL_ORANGE = ["#fbe3d6", "#f7c6ad", "#f3a985", "#ef8c5c", "#eb6834",
                     "#d05224", "#a8401b"]
DIVERGING = ["#2a78d6", "#f0efec", "#e34948"]

STATUS = {"good": "#0ca30c", "warning": "#fab219",
          "serious": "#ec835a", "critical": "#d03b3b"}

cmap_seq = LinearSegmentedColormap.from_list("seq_blue", SEQUENTIAL_BLUE)
cmap_seq_orange = LinearSegmentedColormap.from_list("seq_orange", SEQUENTIAL_ORANGE)
cmap_div = LinearSegmentedColormap.from_list("div_blue_red", DIVERGING)


def variant_style(index: int) -> dict:
    """Colour + marker for the i-th variant (fixed order, never cycled)."""
    i = index % len(CATEGORICAL)
    return {"color": CATEGORICAL[i], "marker": MARKERS[i]}


def apply_style() -> None:
    """Global matplotlib rc settings: thin marks, hairline grid, recessive axes."""
    matplotlib.use("Agg")
    matplotlib.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "grid.linestyle": "-",
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titlecolor": INK,
        "axes.labelcolor": INK_2,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "lines.linewidth": 2.0,
        "lines.markersize": 6,
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Segoe UI", "Arial", "sans-serif"],
        "text.color": INK,
        "figure.dpi": 100,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.15,
    })
