"""Plot ABACUS relax/cell-relax energy, force, and stress convergence."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import typer

from matflowkit.common.plot_style import (
    COLORS,
    add_panel_labels,
    apply_plot_style,
    figure_size,
    save_figure,
)

def parse_series(log: Path) -> dict:
    text = log.read_text(errors="replace")
    number = r"([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)"
    return {
        "energy": [
            float(x)
            for x in re.findall(
                r"(?:final etot is|!FINAL_ETOT_IS)\s+" + number, text, re.I
            )
        ],
        "force": [
            float(x)
            for x in re.findall(r"Largest gradient in force is\s+" + number, text, re.I)
        ],
        "stress": [
            float(x)
            for x in re.findall(r"Largest gradient in stress is\s+" + number, text, re.I)
        ],
        "converged": "Relaxation is converged" in text,
    }


def find_logs(directory: Path) -> list[Path]:
    logs = sorted(directory.glob("OUT.*/running_relax.log"))
    logs.extend(sorted(directory.glob("OUT.*/running_cell-relax.log")))
    for name in ["running_relax.log", "running_cell-relax.log"]:
        direct = directory / name
        if direct.is_file():
            logs.append(direct)
    return sorted(set(logs))


def plot_convergence(
    dir: Path = typer.Argument(Path("."), help="ABACUS relax/cell-relax 任务目录"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="PNG 输出路径"),
    dpi: int = typer.Option(300, min=72, max=600),
):
    """画 ABACUS relax 收敛曲线。"""
    logs = find_logs(dir)
    if not logs:
        typer.secho(
            "错误: 未找到 running_relax.log 或 running_cell-relax.log",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    log = logs[-1]
    data = parse_series(log)
    panels = [key for key in ["energy", "force", "stress"] if data[key]]
    if not panels:
        typer.secho("错误: 日志中没有可绘制数据", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        typer.secho(
            "错误: 需要 matplotlib；请安装 `pip install -e '.[plot]'`",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1) from exc
    apply_plot_style()
    fig, axes = plt.subplots(
        len(panels),
        1,
        figsize=figure_size("single", 0.4 * len(panels) + 0.1),
        sharex=True,
    )
    if len(panels) == 1:
        axes = [axes]
    colors = {"energy": COLORS["blue"], "force": COLORS["orange"], "stress": COLORS["green"]}
    for ax, key in zip(axes, panels):
        values = data[key]
        steps = list(range(1, len(values) + 1))
        shown = [value - values[-1] for value in values] if key == "energy" else values
        markevery = max(1, len(values) // 8)
        if key in {"force", "stress"} and all(value > 0 for value in shown):
            ax.semilogy(
                steps,
                shown,
                "o-",
                color=colors[key],
                markerfacecolor="white",
                markeredgewidth=0.8,
                markevery=markevery,
            )
        else:
            ax.plot(
                steps,
                shown,
                "o-",
                color=colors[key],
                markerfacecolor="white",
                markeredgewidth=0.8,
                markevery=markevery,
            )
        ax.scatter(steps[-1], shown[-1], s=18, color=colors[key], zorder=3)
        if key == "energy":
            ax.axhline(0, color=COLORS["gray"], linewidth=0.7, linestyle="--")
        ax.set_ylabel(
            {
                "energy": r"$E-E_{\mathrm{last}}$ (eV)",
                "force": r"Max force (eV/$\mathrm{\AA}$)",
                "stress": "Max stress (kbar)",
            }[key]
        )
        ax.grid(axis="y", color=COLORS["light_gray"], linewidth=0.6)
    axes[-1].set_xlabel("Ionic step")
    axes[-1].set_xlim(left=1)
    if len(axes) > 1:
        add_panel_labels(axes)
    status = "converged" if data["converged"] else "not converged"
    axes[0].set_title(f"ABACUS relaxation ({status})", pad=8)
    fig.tight_layout()
    target = output or (dir / "abacus_relax_convergence.png")
    save_figure(fig, target, dpi=dpi)
    typer.echo(f"日志: {log}")
    typer.echo(f"图片: {target}")
