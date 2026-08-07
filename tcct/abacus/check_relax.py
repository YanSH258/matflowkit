"""Inspect one ABACUS relaxation and optionally plot its convergence."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import typer

from tcct.common.plot_style import (
    COLORS,
    add_panel_labels,
    apply_plot_style,
    figure_size,
    save_figure,
)


_CONV_RE = re.compile(
    r"convergence has been achieved|relax.{0,10}is converged|is converged!",
    re.IGNORECASE,
)
_STEP_RE = re.compile(r"STEP OF RELAXATION\s*:?\s*(\d+)", re.IGNORECASE)
_ETOT_RE = re.compile(r"final\s+etot|!FINAL", re.IGNORECASE)
_FORCE_RE = re.compile(r"largest\s+grad|max(imum)?[\s_-]*force", re.IGNORECASE)
_FORCE_NUM_RE = re.compile(r"([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)")


def find_relax_logs(directory: Path) -> list[Path]:
    """Find relax and cell-relax logs below one ABACUS task directory."""
    logs = []
    for name in ("running_relax.log", "running_cell-relax.log"):
        logs.extend(sorted(directory.glob(f"OUT.*/{name}")))
        direct = directory / name
        if direct.is_file():
            logs.append(direct)
    return sorted(set(logs))


def parse_series(log: Path) -> dict:
    """Parse relaxation energy, maximum force, and maximum stress series."""
    text = log.read_text(errors="replace")
    number = r"([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)"
    return {
        "energy": [
            float(value)
            for value in re.findall(
                r"(?:final etot is|!FINAL_ETOT_IS)\s+" + number, text, re.I
            )
        ],
        "force": [
            float(value)
            for value in re.findall(
                r"Largest gradient in force is\s+" + number, text, re.I
            )
        ],
        "stress": [
            float(value)
            for value in re.findall(
                r"Largest gradient in stress is\s+" + number, text, re.I
            )
        ],
        "converged": bool(_CONV_RE.search(text)),
    }


def _plot_convergence(log: Path, target: Path, dpi: int) -> Path:
    data = parse_series(log)
    panels = [key for key in ("energy", "force", "stress") if data[key]]
    if not panels:
        raise ValueError("日志中没有可绘制的能量、最大力或最大应力数据")
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "绘图需要 matplotlib；请安装 `pip install -e '.[plot]'`"
        ) from exc

    apply_plot_style()
    fig, axes = plt.subplots(
        len(panels),
        1,
        figsize=figure_size("single", 0.4 * len(panels) + 0.1),
        sharex=True,
    )
    if len(panels) == 1:
        axes = [axes]
    colors = {
        "energy": COLORS["blue"],
        "force": COLORS["orange"],
        "stress": COLORS["green"],
    }
    for ax, key in zip(axes, panels):
        values = data[key]
        steps = list(range(1, len(values) + 1))
        shown = [value - values[-1] for value in values] if key == "energy" else values
        markevery = max(1, len(values) // 8)
        plot_kwargs = {
            "color": colors[key],
            "markerfacecolor": "white",
            "markeredgewidth": 0.8,
            "markevery": markevery,
        }
        if key in {"force", "stress"} and all(value > 0 for value in shown):
            ax.semilogy(steps, shown, "o-", **plot_kwargs)
        else:
            ax.plot(steps, shown, "o-", **plot_kwargs)
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
    target.parent.mkdir(parents=True, exist_ok=True)
    save_figure(fig, target, dpi=dpi)
    return target


def check_relax(
    dir: Path = typer.Argument(Path("."), help="ABACUS relax/cell-relax 目录"),
    plot: bool = typer.Option(False, help="同时生成收敛曲线 PNG"),
    output: Optional[Path] = typer.Option(
        None, "-o", "--output", help="图片路径；默认写入计算目录"
    ),
    dpi: int = typer.Option(300, min=72, max=600),
) -> None:
    """检查一个 ABACUS relax/cell-relax，并可同时绘制收敛曲线。"""
    if not dir.is_dir():
        typer.secho(f"错误: 目录不存在: {dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    logs = find_relax_logs(dir)
    if not logs:
        typer.secho(
            f"错误: 在 {dir} 下未找到 running_relax.log 或 running_cell-relax.log",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    log = logs[-1]
    typer.echo(f"日志文件: {log}")
    lines = log.read_text(errors="replace").splitlines()
    conv_lines = [line.strip() for line in lines if _CONV_RE.search(line)]
    if conv_lines:
        typer.secho("收敛状态: 发现收敛标记", fg=typer.colors.GREEN)
        typer.echo(f"  最终匹配行: {conv_lines[-1]}")
        if len(conv_lines) > 1:
            typer.echo(f"  共 {len(conv_lines)} 条收敛记录")
    else:
        typer.secho(
            "收敛状态: 未发现收敛标记（计算可能未收敛或仍在运行）",
            fg=typer.colors.YELLOW,
        )

    steps = [
        int(match.group(1))
        for line in lines
        for match in [_STEP_RE.search(line)]
        if match
    ]
    if steps:
        typer.echo(f"离子步数: 最后一步为第 {max(steps)} 步（共 {len(steps)} 条步进记录）")
    else:
        typer.echo("离子步数: 未找到 'STEP OF RELAXATION' 行")

    etot_lines = [line.strip() for line in lines if _ETOT_RE.search(line)]
    typer.echo(
        f"总能: {etot_lines[-1]}"
        if etot_lines
        else "总能: 未找到总能行（无 'final etot' / '!FINAL' 标记）"
    )
    force_lines = [line.strip() for line in lines if _FORCE_RE.search(line)]
    if force_lines:
        last = force_lines[-1]
        typer.echo(f"最大力: {last}")
        numbers = _FORCE_NUM_RE.findall(last)
        if numbers:
            typer.echo(f"  提取数值: {numbers[-1]} (eV/A)")
    else:
        typer.echo("最大力: 未找到力信息行（无 'LARGEST GRAD' / 'max force' 标记）")

    if plot:
        target = output.expanduser() if output is not None else dir / "abacus_relax_convergence.png"
        try:
            _plot_convergence(log, target, dpi)
        except (OSError, RuntimeError, ValueError) as exc:
            typer.secho(f"错误: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(2) from exc
        typer.echo(f"收敛曲线: {target}")
