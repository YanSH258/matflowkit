"""Plot ABACUS relax/cell-relax energy, force, and stress convergence."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import typer

def parse_series(log: Path) -> dict:
    text = log.read_text(errors="replace")
    number = r"([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)"
    return {
        "energy": [float(x) for x in re.findall(r"final etot is\s+" + number, text, re.I)],
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
    dpi: int = typer.Option(180, min=72, max=600),
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
    fig, axes = plt.subplots(len(panels), 1, figsize=(7, 2.7 * len(panels)))
    if len(panels) == 1:
        axes = [axes]
    for ax, key in zip(axes, panels):
        values = data[key]
        steps = range(1, len(values) + 1)
        shown = [value - values[-1] for value in values] if key == "energy" else values
        if key in {"force", "stress"} and all(value > 0 for value in shown):
            ax.semilogy(steps, shown, "o-", ms=3)
        else:
            ax.plot(steps, shown, "o-", ms=3)
        ax.set_ylabel(
            {"energy": "E - E_last (eV)", "force": "max force (eV/A)", "stress": "max stress"}[key]
        )
        ax.set_xlabel("ionic step")
        ax.grid(alpha=0.3)
    fig.suptitle("ABACUS relaxation" + (" - converged" if data["converged"] else ""))
    fig.tight_layout()
    target = output or (dir / "abacus_relax_convergence.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=dpi)
    plt.close(fig)
    typer.echo(f"日志: {log}")
    typer.echo(f"图片: {target}")
