"""Plot whichever standard NEP train/test prediction files are available."""

from __future__ import annotations

import json
from pathlib import Path
from math import ceil

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


PROPERTY_SPECS = (
    ("energy", 2, slice(0, 1), slice(1, 2), "eV/atom", 1000.0, "meV/atom"),
    (
        "force",
        6,
        slice(0, 3),
        slice(3, 6),
        "eV/angstrom",
        1000.0,
        "meV/Å",
    ),
    ("stress", 12, slice(0, 6), slice(6, 12), "GPa", 1.0, "GPa"),
    ("virial", 12, slice(0, 6), slice(6, 12), "eV/atom", 1000.0, "meV/atom"),
)


def _discover_panels(directory: Path) -> list[dict]:
    panels = []
    for split in ("train", "test"):
        for name, columns, predicted, reference, unit, scale, metric_unit in PROPERTY_SPECS:
            path = directory / f"{name}_{split}.out"
            if not path.is_file():
                continue
            data = _load_table(path, columns)
            if name in ("stress", "virial"):
                valid = ~np.any(np.abs(data[:, :12]) >= 1.0e6, axis=1)
                data = data[valid]
                if len(data) == 0:
                    raise ValueError(f"{path} 没有可绘制的有限 tensor 行")
            panels.append(
                {
                    "split": split,
                    "property": name,
                    "path": path,
                    "predicted": data[:, predicted],
                    "reference": data[:, reference],
                    "unit": unit,
                    "metric_scale": scale,
                    "metric_unit": metric_unit,
                }
            )
    if not panels:
        names = ", ".join(f"{name}_{{train,test}}.out" for name, *_ in PROPERTY_SPECS)
        raise FileNotFoundError(f"未找到可绘制的 NEP 输出；支持: {names}")
    return panels


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
    """扫描目录并绘制已有的 NEP energy/force/stress/virial 预测文件。"""
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
        panels = _discover_panels(directory)
    except (FileNotFoundError, OSError, ValueError) as exc:
        typer.secho(f"错误: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc

    has_test = any(panel["split"] == "test" for panel in panels)
    metrics: dict[str, object] = {
        "directory": str(directory),
        "primary_evidence": (
            "held-out test set"
            if has_test
            else "training set only; no held-out test files found"
        ),
        "files_used": [str(panel["path"]) for panel in panels],
        "splits": {},
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

    apply_plot_style()
    columns = 2 if len(panels) == 4 else min(3, len(panels))
    rows = ceil(len(panels) / columns)
    size_kind = "single" if columns == 1 else "double"
    height_ratio = 0.9 if columns == 1 else 0.40 * rows
    fig, axes = plt.subplots(
        rows,
        columns,
        squeeze=False,
        figsize=figure_size(size_kind, height_ratio),
    )
    flat_axes = list(axes.flat)
    used_axes = []
    for ax, panel in zip(flat_axes, panels):
        used_axes.append(ax)
        split_name = panel["split"]
        property_name = panel["property"]
        key = property_name if property_name == "energy" else f"{property_name}_components"
        split_metrics = metrics["splits"].setdefault(split_name, {})
        metric = _metric_record(
            panel["predicted"], panel["reference"], panel["unit"]
        )
        split_metrics[key] = metric
        axis_unit = (
            r"eV/$\mathrm{\AA}$" if property_name == "force" else panel["unit"]
        )
        metric["plot_mode"] = _plot_panel(
            ax,
            panel["reference"],
            panel["predicted"],
            f"DFT {property_name} ({split_name}, {axis_unit})",
            f"NEP {property_name} ({split_name}, {axis_unit})",
            metric,
            panel["metric_scale"],
            panel["metric_unit"],
            max_points,
            density_threshold,
        )
    for ax in flat_axes[len(panels):]:
        ax.axis("off")
    add_panel_labels(used_axes)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    save_figure(fig, output)
    metrics_output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n")

    typer.echo(f"已保存图片: {output}")
    typer.echo(f"已保存误差指标: {metrics_output}")
    if not has_test:
        typer.echo("提示: 未找到 test 输出；当前结果只有训练集误差。")
    reported_split = "test" if has_test else "train"
    for panel in panels:
        if panel["split"] != reported_split:
            continue
        key = (
            panel["property"]
            if panel["property"] == "energy"
            else f"{panel['property']}_components"
        )
        value = metrics["splits"][panel["split"]][key]["rmse"]
        typer.echo(
            f"{panel['split'].capitalize()} {panel['property']} RMSE: "
            f"{value * panel['metric_scale']:.3g} {panel['metric_unit']}"
        )
