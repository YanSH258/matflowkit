"""Read and plot GPUMD thermo.out."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import typer

from matflowkit.common.plot_style import (
    COLORS,
    add_panel_labels,
    apply_plot_style,
    figure_size,
    save_figure,
)


def read_time_interval(run_in: Path) -> float:
    """Return the interval between thermo rows in ps."""
    time_step_fs = 1.0
    dump_thermo = 10
    if not run_in.is_file():
        return time_step_fs * dump_thermo / 1000.0
    for raw_line in run_in.read_text(errors="replace").splitlines():
        fields = raw_line.split("#", 1)[0].split()
        if len(fields) < 2:
            continue
        if fields[0] == "time_step":
            time_step_fs = float(fields[1])
        elif fields[0] == "dump_thermo":
            dump_thermo = int(fields[1])
    return time_step_fs * dump_thermo / 1000.0


def cell_series(data: np.ndarray) -> dict[str, np.ndarray]:
    """Read orthogonal or triclinic cell data from thermo.out."""
    if data.shape[1] == 12:
        lengths = data[:, 9:12]
        return {
            "lengths": lengths,
            "volume": np.prod(lengths, axis=1),
        }
    if data.shape[1] != 18:
        raise ValueError("画图只支持 12 列或 18 列 thermo.out")

    cells = data[:, 9:18].reshape(-1, 3, 3)
    lengths = np.linalg.norm(cells, axis=2)
    angles = np.empty((len(cells), 3), dtype=float)
    vector_pairs = ((1, 2), (2, 0), (0, 1))
    for column, (left, right) in enumerate(vector_pairs):
        cosine = np.einsum("ij,ij->i", cells[:, left], cells[:, right])
        cosine /= lengths[:, left] * lengths[:, right]
        angles[:, column] = np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))
    return {
        "lengths": lengths,
        "angles": angles,
        "volume": np.abs(np.linalg.det(cells)),
    }


def write_averages(
    output: Path,
    data: np.ndarray,
    cell: dict[str, np.ndarray],
    start_fraction: float,
) -> None:
    """Write averages over the selected final part of the trajectory."""
    start = int(len(data) * start_fraction)
    lines = [
        f"Averaging range: {start_fraction:.0%} to 100%",
        f"Temperature: {np.mean(data[start:, 0]):.6g} K",
        f"Pressure X: {np.mean(data[start:, 3]):.6g} GPa",
        f"Pressure Y: {np.mean(data[start:, 4]):.6g} GPa",
        f"Pressure Z: {np.mean(data[start:, 5]):.6g} GPa",
        f"Lattice length X: {np.mean(cell['lengths'][start:, 0]):.6g} Angstrom",
        f"Lattice length Y: {np.mean(cell['lengths'][start:, 1]):.6g} Angstrom",
        f"Lattice length Z: {np.mean(cell['lengths'][start:, 2]):.6g} Angstrom",
        f"Volume: {np.mean(cell['volume'][start:]):.6g} Angstrom^3",
    ]
    if "angles" in cell:
        for name, values in zip(("Alpha", "Beta", "Gamma"), cell["angles"].T):
            lines.append(f"Angle {name}: {np.mean(values[start:]):.6g} degree")
    output.write_text("\n".join(lines) + "\n")


def plot_thermo(
    data: np.ndarray,
    time: np.ndarray,
    cell: dict[str, np.ndarray],
    output: Path,
) -> None:
    """Plot the six GPUMDkit-style thermo panels."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    apply_plot_style()
    fig, axes = plt.subplots(2, 3, figsize=figure_size("double", 0.62))

    axes[0, 0].plot(time, data[:, 0], color=COLORS["blue"])
    axes[0, 0].set_title("Temperature")
    axes[0, 0].set_ylabel("Temperature (K)")

    for column, label, color in zip(
        range(3, 6),
        (r"$P_{xx}$", r"$P_{yy}$", r"$P_{zz}$"),
        (COLORS["blue"], COLORS["orange"], COLORS["green"]),
    ):
        axes[0, 1].plot(time, data[:, column], label=label, color=color)
    axes[0, 1].set_title("Pressure")
    axes[0, 1].set_ylabel("Pressure (GPa)")
    axes[0, 1].legend(ncol=3)

    axes[0, 2].plot(time, data[:, 2], color=COLORS["blue"])
    axes[0, 2].set_title("Energy")
    axes[0, 2].set_ylabel("Potential energy (eV)", color=COLORS["blue"])
    axes[0, 2].tick_params(axis="y", labelcolor=COLORS["blue"])
    kinetic_ax = axes[0, 2].twinx()
    kinetic_ax.plot(time, data[:, 1], color=COLORS["orange"])
    kinetic_ax.set_ylabel("Kinetic energy (eV)", color=COLORS["orange"])
    kinetic_ax.tick_params(axis="y", labelcolor=COLORS["orange"])
    kinetic_ax.spines["right"].set_visible(True)
    kinetic_ax.spines["right"].set_color(COLORS["orange"])

    for column, label, color in zip(
        range(3),
        (r"$L_x$", r"$L_y$", r"$L_z$"),
        (COLORS["blue"], COLORS["orange"], COLORS["green"]),
    ):
        axes[1, 0].plot(time, cell["lengths"][:, column], label=label, color=color)
    axes[1, 0].set_title("Lattice lengths")
    axes[1, 0].set_ylabel(r"Length ($\mathrm{\AA}$)")
    axes[1, 0].legend(ncol=3)

    axes[1, 1].plot(time, cell["volume"], color=COLORS["purple"])
    axes[1, 1].set_title("Volume")
    axes[1, 1].set_ylabel(r"Volume ($\mathrm{\AA}^3$)")

    if "angles" in cell:
        for column, label, color in zip(
            range(3),
            (r"$\alpha$", r"$\beta$", r"$\gamma$"),
            (COLORS["blue"], COLORS["orange"], COLORS["green"]),
        ):
            axes[1, 2].plot(time, cell["angles"][:, column], label=label, color=color)
        axes[1, 2].set_title("Lattice angles")
        axes[1, 2].set_ylabel("Angle (degree)")
        axes[1, 2].legend(ncol=3)
    else:
        total_energy = data[:, 1] + data[:, 2]
        axes[1, 2].plot(time, total_energy, color=COLORS["red"])
        axes[1, 2].set_title("Total energy")
        axes[1, 2].set_ylabel("Energy (eV)")

    for ax in axes.flat:
        ax.set_xlabel("Time (ps)")
        ax.grid(axis="y", color=COLORS["light_gray"], linewidth=0.6)
    add_panel_labels(axes.flat)
    fig.tight_layout()
    save_figure(fig, output)


def thermo(
    file: Path = typer.Argument(Path("thermo.out"), help="thermo.out 路径"),
    plot: bool = typer.Option(False, "--plot", help="生成 thermo.png"),
    run_in: Optional[Path] = typer.Option(None, help="run.in 路径"),
    output: Optional[Path] = typer.Option(
        None,
        "-o",
        "--output",
        help="PNG 输出；默认写到 thermo.out 所在目录",
    ),
    averages: Optional[Path] = typer.Option(
        None,
        help="后半段平均值；默认写到 thermo.out 所在目录",
    ),
    start_fraction: float = typer.Option(
        0.5, min=0.0, max=0.999999, help="平均值起始比例"
    ),
) -> None:
    """统计 GPUMD thermo.out，并可画出热力学量。"""
    if not file.is_file():
        typer.secho(f"错误: 文件不存在: {file}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    try:
        data = np.atleast_2d(np.loadtxt(file))
    except (OSError, ValueError) as exc:
        typer.secho(f"错误: 无法读取 {file}: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc
    if data.shape[1] < 1 or not np.all(np.isfinite(data)):
        typer.secho("错误: thermo.out 没有有效数值", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    typer.echo(f"文件: {file}")
    typer.echo(f"行数: {len(data)}    列数: {data.shape[1]}")
    typer.echo(f"{'列':>4} {'mean':>14} {'min':>14} {'max':>14} {'末值':>14}")
    for index, values in enumerate(data.T, 1):
        typer.echo(
            f"{index:>4} {values.mean():>14.6g} {values.min():>14.6g} "
            f"{values.max():>14.6g} {values[-1]:>14.6g}"
        )

    if not plot:
        return
    output = output or file.parent / "thermo.png"
    averages = averages or file.parent / "thermo_averages.txt"
    if output.exists() or averages.exists():
        typer.secho("错误: thermo 图或平均值文件已存在", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    try:
        cell = cell_series(data)
        interval = read_time_interval(run_in or file.with_name("run.in"))
        time = np.arange(len(data), dtype=float) * interval
        plot_thermo(data, time, cell, output)
        write_averages(averages, data, cell, start_fraction)
    except (ImportError, OSError, ValueError, ZeroDivisionError) as exc:
        typer.secho(f"错误: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2) from exc
    typer.echo(f"图片: {output}")
    typer.echo(f"平均值: {averages}")
