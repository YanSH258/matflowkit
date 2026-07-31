"""mfk gpumd plot-nep-training: plot NEP losses and prediction errors."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import typer


def _load_table(path: Path, minimum_columns: int) -> np.ndarray:
    if not path.is_file():
        raise FileNotFoundError(f"文件不存在: {path}")
    try:
        data = np.loadtxt(path)
    except ValueError as exc:
        raise ValueError(f"无法解析数值文件 {path}: {exc}") from exc
    data = np.atleast_2d(data)
    if data.shape[1] < minimum_columns:
        raise ValueError(
            f"{path} 至少需要 {minimum_columns} 列，实际为 {data.shape[1]} 列"
        )
    if not np.all(np.isfinite(data)):
        raise ValueError(f"{path} 包含 NaN 或无穷值")
    return data


def _metrics(predicted: np.ndarray, reference: np.ndarray) -> dict[str, float]:
    predicted = np.asarray(predicted, dtype=float).reshape(-1)
    reference = np.asarray(reference, dtype=float).reshape(-1)
    residual = predicted - reference
    ss_res = float(np.sum(residual**2))
    ss_tot = float(np.sum((reference - np.mean(reference)) ** 2))
    return {
        "rmse": float(np.sqrt(np.mean(residual**2))),
        "mae": float(np.mean(np.abs(residual))),
        "r2": float(1.0 - ss_res / ss_tot) if ss_tot > 0.0 else 1.0,
    }


def _sample_pair(
    reference: np.ndarray,
    predicted: np.ndarray,
    max_points: int,
) -> tuple[np.ndarray, np.ndarray]:
    reference = np.asarray(reference).reshape(-1)
    predicted = np.asarray(predicted).reshape(-1)
    if len(reference) <= max_points:
        return reference, predicted
    indices = np.linspace(0, len(reference) - 1, max_points, dtype=int)
    return reference[indices], predicted[indices]


def _axis_limits(values: np.ndarray, padding: float = 0.06) -> tuple[float, float]:
    low = float(np.min(values))
    high = float(np.max(values))
    span = high - low
    if span == 0.0:
        span = max(abs(low), 1.0)
    return low - padding * span, high + padding * span


def _loss_series(loss: np.ndarray) -> tuple[list[str], np.ndarray]:
    available = loss.shape[1] - 1
    if available >= 6:
        labels = ["Total", "L1", "L2", "Energy", "Force", "Virial"]
    elif available >= 4:
        labels = ["Total", "Energy", "Force", "Virial"]
    else:
        labels = [f"Loss {index}" for index in range(1, available + 1)]
    return labels, loss[:, 1 : 1 + len(labels)]


def plot_nep_training(
    directory: Path = typer.Argument(
        Path("."),
        help="包含 loss.out 和 *_train.out 的 NEP 训练或预测目录",
    ),
    output: Path = typer.Option(
        Path("nep_training.png"),
        "--output",
        "-o",
        help="输出图片",
    ),
    metrics_output: Path = typer.Option(
        Path("nep_training_metrics.json"),
        "--metrics",
        help="误差指标 JSON",
    ),
    max_points: int = typer.Option(
        200_000,
        min=1000,
        help="每个散点面板最多绘制的点数，不影响误差计算",
    ),
) -> None:
    """绘制 NEP loss 和能量、力、应力预测误差。

    默认读取 ``loss.out``、``energy_train.out`` 和 ``force_train.out``。
    如果目录中存在 ``stress_train.out``，则自动绘制应力面板。RMSE、MAE
    和 R2 使用完整数据计算并写入 ``nep_training_metrics.json``；大数据集
    仅在绘图时等距抽样。示例：``mfk gpumd plot-nep-training ./train``。
    """
    if not directory.is_dir():
        typer.secho(f"错误: 目录不存在: {directory}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    for path in (output, metrics_output):
        if path.exists():
            typer.secho(
                f"错误: 输出文件已存在: {path}",
                err=True,
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)

    try:
        loss = _load_table(directory / "loss.out", 2)
        energy = _load_table(directory / "energy_train.out", 2)
        force = _load_table(directory / "force_train.out", 6)
        stress_path = directory / "stress_train.out"
        stress = _load_table(stress_path, 12) if stress_path.is_file() else None
        if stress is not None:
            valid = ~np.any(np.abs(stress[:, :12]) >= 1.0e6, axis=1)
            stress = stress[valid]
            if len(stress) == 0:
                stress = None
    except (FileNotFoundError, OSError, ValueError) as exc:
        typer.secho(f"错误: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc

    results: dict[str, object] = {
        "directory": str(directory.resolve()),
        "energy": {
            "rows": int(len(energy)),
            "units": "eV/atom",
            **_metrics(energy[:, 0], energy[:, 1]),
        },
        "force_components": {
            "rows": int(len(force)),
            "values": int(force[:, :3].size),
            "units": "eV/angstrom",
            **_metrics(force[:, :3], force[:, 3:6]),
        },
    }
    if stress is not None:
        results["stress_components"] = {
            "rows": int(len(stress)),
            "values": int(stress[:, :6].size),
            "units": "GPa",
            **_metrics(stress[:, :6], stress[:, 6:12]),
        }

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        typer.secho(
            "错误: 该命令需要 matplotlib，请运行 pip install -e '.[plot]'",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(3) from exc

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "font.size": 9,
            "mathtext.fontset": "stix",
            "axes.linewidth": 0.8,
            "xtick.direction": "in",
            "ytick.direction": "in",
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 6.2), dpi=160)

    labels, series = _loss_series(loss)
    for column, label in enumerate(labels):
        axes[0, 0].loglog(loss[:, 0], series[:, column], lw=1.2, label=label)
    axes[0, 0].set_xlabel("Generation or epoch")
    axes[0, 0].set_ylabel("Loss")
    axes[0, 0].legend(frameon=False, fontsize=7, ncol=2)

    panels = [
        (
            axes[0, 1],
            energy[:, 1],
            energy[:, 0],
            "DFT energy (eV/atom)",
            "NEP energy (eV/atom)",
            results["energy"],
            1000.0,
            "meV/atom",
        ),
        (
            axes[1, 0],
            force[:, 3:6],
            force[:, 0:3],
            r"DFT force (eV/$\mathrm{\AA}$)",
            r"NEP force (eV/$\mathrm{\AA}$)",
            results["force_components"],
            1000.0,
            r"meV/$\mathrm{\AA}$",
        ),
    ]
    if stress is not None:
        panels.append(
            (
                axes[1, 1],
                stress[:, 6:12],
                stress[:, 0:6],
                "DFT stress (GPa)",
                "NEP stress (GPa)",
                results["stress_components"],
                1.0,
                "GPa",
            )
        )
    else:
        axes[1, 1].axis("off")
        axes[1, 1].text(
            0.5,
            0.5,
            "stress_train.out not found",
            ha="center",
            va="center",
            color="0.45",
        )

    for ax, reference, predicted, xlabel, ylabel, metric, scale, unit in panels:
        reference_plot, predicted_plot = _sample_pair(
            reference, predicted, max_points
        )
        combined = np.concatenate(
            [reference_plot.reshape(-1), predicted_plot.reshape(-1)]
        )
        lower, upper = _axis_limits(combined)
        ax.scatter(
            reference_plot,
            predicted_plot,
            s=5,
            alpha=0.35,
            linewidths=0,
            rasterized=True,
        )
        ax.plot([lower, upper], [lower, upper], color="0.35", ls="--", lw=0.9)
        ax.set_xlim(lower, upper)
        ax.set_ylim(lower, upper)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.text(
            0.04,
            0.96,
            f"RMSE = {float(metric['rmse']) * scale:.3g} {unit}\n"
            f"$R^2$ = {float(metric['r2']):.4f}",
            transform=ax.transAxes,
            ha="left",
            va="top",
        )

    for ax, label in zip(axes.flat, ["a.", "b.", "c.", "d."]):
        ax.text(
            -0.13,
            1.04,
            label,
            transform=ax.transAxes,
            fontweight="bold",
            fontsize=11,
            ha="left",
            va="bottom",
        )

    fig.tight_layout()
    fig.savefig(output, dpi=300)
    plt.close(fig)
    metrics_output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n"
    )

    typer.echo(f"已保存图片: {output}")
    typer.echo(f"已保存误差指标: {metrics_output}")
    typer.echo(
        f"Energy RMSE: {float(results['energy']['rmse']) * 1000:.3g} meV/atom"
    )
    typer.echo(
        "Force RMSE: "
        f"{float(results['force_components']['rmse']) * 1000:.3g} meV/angstrom"
    )
    if "stress_components" in results:
        typer.echo(
            "Stress RMSE: "
            f"{float(results['stress_components']['rmse']):.3g} GPa"
        )
