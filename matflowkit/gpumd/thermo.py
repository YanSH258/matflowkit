"""mfk gpumd thermo：分析 GPUMD thermo.out 热力学输出。"""

from pathlib import Path

import numpy as np
import typer

from matflowkit.common.plot_style import COLORS, apply_plot_style, figure_size, save_figure


def thermo(
    file: Path = typer.Argument(Path("thermo.out"), help="thermo.out 路径"),
    plot: bool = typer.Option(False, "--plot", help="画第 1 列"),
):
    """统计 thermo.out，可选画第 1 列。"""
    if not file.is_file():
        typer.secho(f"错误: 文件不存在: {file}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    try:
        data = np.loadtxt(file)
    except ValueError as e:
        typer.secho(f"错误: 无法解析数值文件 {file}: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    data = np.atleast_2d(data)
    nrows, ncols = data.shape

    typer.echo(f"文件: {file}")
    typer.echo(f"行数: {nrows}    列数: {ncols}")
    typer.echo("（列数随 GPUMD 版本 / run.in 设置变化；第 1 列通常为温度 T，典型 12 列含动能、压力、势能等）\n")
    typer.echo(f"{'列':>4} {'mean':>14} {'min':>14} {'max':>14} {'末值':>14}   备注")
    for i in range(ncols):
        col = data[:, i]
        note = "通常为温度 T (K)" if i == 0 else ""
        typer.echo(
            f"{i + 1:>4} {col.mean():>14.6g} {col.min():>14.6g} {col.max():>14.6g} {col[-1]:>14.6g}   {note}"
        )

    if plot:
        steps = np.arange(nrows)
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            # 未安装 matplotlib：提示并把数据存为 csv 后跳过画图，不崩溃
            csv_path = Path("thermo_col1.csv")
            np.savetxt(csv_path, np.column_stack([steps, data[:, 0]]), delimiter=",",
                       header="step,col1", comments="")
            typer.secho(
                f"\n未安装 matplotlib，跳过画图；已将第 1 列数据保存为 {csv_path}（可安装后重试: pip install matplotlib）",
                fg=typer.colors.YELLOW,
            )
            return
        apply_plot_style()
        fig, ax = plt.subplots(figsize=figure_size("single", 0.72))
        ax.plot(steps, data[:, 0], color=COLORS["blue"])
        ax.set_xlabel("Output step")
        ax.set_ylabel("Column 1 (usually T / K)")
        fig.tight_layout()
        out = Path("thermo_col1.png")
        save_figure(fig, out)
        typer.echo(f"\n已保存图片: {out}")
