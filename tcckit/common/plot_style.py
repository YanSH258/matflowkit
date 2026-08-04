"""Shared Matplotlib style for TCCKit figures."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Union

MM_PER_INCH = 25.4
SINGLE_COLUMN_MM = 89.0
DOUBLE_COLUMN_MM = 183.0

# Okabe-Ito colorblind-safe palette.
COLORS = {
    "blue": "#0072B2",
    "orange": "#E69F00",
    "green": "#009E73",
    "red": "#D55E00",
    "sky": "#56B4E9",
    "purple": "#CC79A7",
    "yellow": "#F0E442",
    "black": "#000000",
    "gray": "#767676",
    "light_gray": "#D9D9D9",
}
COLOR_CYCLE = [
    COLORS["blue"], COLORS["orange"], COLORS["green"], COLORS["red"],
    COLORS["sky"], COLORS["purple"], COLORS["black"],
]
LINE_STYLES = ("-", "--", "-.", ":")
MARKERS = ("o", "s", "^", "D", "v", "P", "X")


def figure_size(width: str = "double", aspect: float = 0.7) -> tuple[float, float]:
    """Return figure dimensions in inches."""
    widths = {"single": SINGLE_COLUMN_MM, "double": DOUBLE_COLUMN_MM}
    if width not in widths:
        raise ValueError("width must be 'single' or 'double'")
    if aspect <= 0:
        raise ValueError("aspect must be positive")
    width_in = widths[width] / MM_PER_INCH
    return width_in, width_in * aspect


def apply_plot_style() -> None:
    """Apply the TCCKit plotting standard."""
    import matplotlib as mpl

    mpl.rcParams.update({
        "font.family": "serif",
        "font.serif": [
            "Times New Roman",
            "Times",
            "Liberation Serif",
            "DejaVu Serif",
        ],
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 9,
        "axes.titleweight": "normal",
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.prop_cycle": mpl.cycler(color=COLOR_CYCLE),
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        "legend.fontsize": 7,
        "legend.frameon": False,
        "lines.linewidth": 1.3,
        "lines.markersize": 4,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "mathtext.fontset": "stix",
    })


def add_panel_labels(axes: Iterable, labels: Optional[Iterable[str]] = None) -> None:
    """Add lowercase panel labels at the upper left."""
    axes = list(axes)
    labels = list(labels) if labels is not None else [chr(97 + i) for i in range(len(axes))]
    for ax, label in zip(axes, labels):
        ax.text(-0.12, 1.03, label, transform=ax.transAxes, fontsize=9,
                fontweight="bold", ha="left", va="bottom")


def save_figure(fig, output: Union[Path, str], dpi: int = 300) -> Path:
    """Save and close a figure; use PNG when no suffix is given."""
    import matplotlib.pyplot as plt

    target = Path(output)
    if not target.suffix:
        target = target.with_suffix(".png")
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return target
