"""Plot held-out NEP predictions, with optional training-set comparison."""

from __future__ import annotations

import json
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
from matflowkit.gpumd.plot_nep_training import (
    _axis_limits,
    _load_table,
    _metrics,
    _sample_pair,
)


def _read_split(directory: Path, split: str, required: bool) -> Optional[dict]:
    energy_path = directory / f"energy_{split}.out"
    force_path = directory / f"force_{split}.out"
    present = (energy_path.is_file(), force_path.is_file())
    if not any(present) and not required:
        return None
    if not all(present):
        missing = energy_path if not present[0] else force_path
        raise FileNotFoundError(f"{split} 数据不完整，缺少: {missing}")

    tensor = None
    tensor_name = None
    tensor_unit = None
    tensor_scale = None
    for name, unit, scale in (("stress", "GPa", 1.0), ("virial", "eV/atom", 1000.0)):
        path = directory / f"{name}_{split}.out"
        if path.is_file():
            tensor = _load_table(path, 12)
            valid = ~np.any(np.abs(tensor[:, :12]) >= 1.0e6, axis=1)
            tensor = tensor[valid]
            if len(tensor) == 0:
                tensor = None
            else:
                tensor_name = name
                tensor_unit = unit
                tensor_scale = scale
            break

    return {
        "energy": _load_table(energy_path, 2),
        "force": _load_table(force_path, 6),
        "tensor": tensor,
        "tensor_name": tensor_name,
        "tensor_unit": tensor_unit,
        "tensor_scale": tensor_scale,
    }


def _metric_record(predicted: np.ndarray, reference: np.ndarray, unit: str) -> dict:
    return {
        "values": int(np.asarray(reference).size),
        "unit": unit,
        **_metrics(predicted, reference),
    }


def _plot_panel(
    ax,
    reference: np.ndarray,
    predicted: np.ndarray,
    xlabel: str,
    ylabel: str,
    metric: dict,
    metric_scale: float,
    metric_unit: str,
    max_points: int,
    density_threshold: int,
) -> str:
    reference = np.asarray(reference).reshape(-1)
    predicted = np.asarray(predicted).reshape(-1)
    combined = np.concatenate((reference, predicted))
    lower, upper = _axis_limits(combined)
    mode = "density" if reference.size >= density_threshold else "scatter"
    if mode == "density":
        from matplotlib.colors import LogNorm

        ax.hist2d(
            reference,
            predicted,
            bins=120,
            range=((lower, upper), (lower, upper)),
            cmin=1,
            cmap="Blues",
            norm=LogNorm(),
        )
    else:
        reference_plot, predicted_plot = _sample_pair(reference, predicted, max_points)
        ax.scatter(
            reference_plot,
            predicted_plot,
            s=5,
            alpha=0.35,
            linewidths=0,
            rasterized=True,
            color=COLORS["blue"],
        )
    ax.plot([lower, upper], [lower, upper], color=COLORS["gray"], ls="--", lw=0.9)
    ax.set_xlim(lower, upper)
    ax.set_ylim(lower, upper)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.text(
        0.04,
        0.96,
        f"RMSE = {float(metric['rmse']) * metric_scale:.3g} {metric_unit}\n"
        f"MAE = {float(metric['mae']) * metric_scale:.3g} {metric_unit}\n"
        f"$R^2$ = {float(metric['r2']):.4f}",
        transform=ax.transAxes,
        ha="left",
        va="top",
    )
    return mode


def plot_nep_evaluation(
    directory: Path = typer.Argument(Path("."), help="NEP train/test 输出目录"),
    output: Path = typer.Option(
        Path("nep_evaluation.png"), "--output", "-o", help="输出图片"
    ),
    metrics_output: Path = typer.Option(
        Path("nep_evaluation_metrics.json"), "--metrics", help="误差指标 JSON"
    ),
    max_points: int = typer.Option(200_000, min=1000, help="散点模式每个面板最多绘制的点数"),
    density_threshold: int = typer.Option(
        100_000, min=1000, help="达到该数据量时改用二维密度图"
    ),
) -> None:
    """比较 NEP 训练集和测试集预测，测试集文件为必需输入。"""
    directory = directory.expanduser().resolve()
    output = output.expanduser().resolve()
    metrics_output = metrics_output.expanduser().resolve()
    if not directory.is_dir():
        typer.secho(f"错误: 目录不存在: {directory}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    for path in (output, metrics_output):
        if path.exists():
            typer.secho(f"错误: 输出文件已存在: {path}", err=True, fg=typer.colors.RED)
            raise typer.Exit(1)

    try:
        test = _read_split(directory, "test", required=True)
        train = _read_split(directory, "train", required=False)
    except (FileNotFoundError, OSError, ValueError) as exc:
        typer.secho(f"错误: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc

    splits = [("test", test)]
    if train is not None:
        splits.insert(0, ("train", train))
    metrics: dict[str, object] = {
        "directory": str(directory),
        "primary_evidence": "held-out test set",
        "splits": {},
    }
    tensor_names = {
        data["tensor_name"] for _, data in splits if data["tensor_name"] is not None
    }
    show_tensor = bool(tensor_names)
    columns = 3 if show_tensor else 2

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

    apply_plot_style()
    fig, axes = plt.subplots(
        len(splits),
        columns,
        squeeze=False,
        figsize=figure_size("double", 0.42 * len(splits)),
    )
    for row, (split_name, data) in enumerate(splits):
        energy = data["energy"]
        force = data["force"]
        split_metrics = {
            "energy": _metric_record(energy[:, 0], energy[:, 1], "eV/atom"),
            "force_components": _metric_record(
                force[:, :3], force[:, 3:6], "eV/angstrom"
            ),
        }
        metrics["splits"][split_name] = split_metrics
        split_metrics["energy"]["plot_mode"] = _plot_panel(
            axes[row, 0],
            energy[:, 1],
            energy[:, 0],
            f"DFT energy ({split_name}, eV/atom)",
            f"NEP energy ({split_name}, eV/atom)",
            split_metrics["energy"],
            1000.0,
            "meV/atom",
            max_points,
            density_threshold,
        )
        split_metrics["force_components"]["plot_mode"] = _plot_panel(
            axes[row, 1],
            force[:, 3:6],
            force[:, :3],
            rf"DFT force ({split_name}, eV/$\mathrm{{\AA}}$)",
            rf"NEP force ({split_name}, eV/$\mathrm{{\AA}}$)",
            split_metrics["force_components"],
            1000.0,
            r"meV/$\mathrm{\AA}$",
            max_points,
            density_threshold,
        )

        if show_tensor:
            tensor = data["tensor"]
            if tensor is None:
                axes[row, 2].axis("off")
                axes[row, 2].text(
                    0.5,
                    0.5,
                    f"No stress/virial {split_name} data",
                    ha="center",
                    va="center",
                    color=COLORS["gray"],
                )
            else:
                tensor_name = data["tensor_name"]
                tensor_unit = data["tensor_unit"]
                tensor_metric = _metric_record(
                    tensor[:, :6], tensor[:, 6:12], tensor_unit
                )
                split_metrics[f"{tensor_name}_components"] = tensor_metric
                metric_scale = float(data["tensor_scale"])
                metric_unit = "meV/atom" if tensor_name == "virial" else tensor_unit
                tensor_metric["plot_mode"] = _plot_panel(
                    axes[row, 2],
                    tensor[:, 6:12],
                    tensor[:, :6],
                    f"DFT {tensor_name} ({split_name}, {tensor_unit})",
                    f"NEP {tensor_name} ({split_name}, {tensor_unit})",
                    tensor_metric,
                    metric_scale,
                    metric_unit,
                    max_points,
                    density_threshold,
                )

    add_panel_labels(axes.flat)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    save_figure(fig, output)
    metrics_output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n")

    test_metrics = metrics["splits"]["test"]
    typer.echo(f"已保存图片: {output}")
    typer.echo(f"已保存误差指标: {metrics_output}")
    typer.echo(
        f"Test energy RMSE: {test_metrics['energy']['rmse'] * 1000:.3g} meV/atom"
    )
    typer.echo(
        "Test force RMSE: "
        f"{test_metrics['force_components']['rmse'] * 1000:.3g} meV/angstrom"
    )
