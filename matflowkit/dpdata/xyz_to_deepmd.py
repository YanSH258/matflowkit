"""Convert a labeled GPUMD/extxyz trajectory to DeepMD raw and NPY datasets."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from matflowkit.common.dpdata_utils import require_dpdata


def xyz_to_deepmd(
    input: Path = typer.Argument(
        Path("train.xyz"),
        help="GPUMD/extxyz 文件",
    ),
    output: Path = typer.Argument(
        Path("deepmd"),
        help="输出目录",
    ),
    set_size: int = typer.Option(
        2000,
        min=1,
        help="每个 set 的最大帧数",
    ),
) -> None:
    """XYZ 转 DeepMD raw 和 NPY。"""
    if not input.is_file():
        typer.secho(f"错误: 输入文件不存在: {input}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    if output.exists():
        if output.is_file() or any(output.iterdir()):
            typer.secho(f"错误: 输出路径已存在且非空: {output}", err=True, fg=typer.colors.RED)
            raise typer.Exit(1)

    dpdata = require_dpdata()
    try:
        systems = dpdata.MultiSystems.from_file(str(input), fmt="gpumd/xyz")
        if len(systems) < 1:
            raise ValueError("dpdata 返回零个 system")
        frame_count = sum(len(system) for system in systems)
        if frame_count < 1:
            raise ValueError("dpdata 返回零帧")
        systems.to_deepmd_npy(str(output), set_size=set_size)
        systems.to_deepmd_raw(str(output))
    except Exception as exc:
        typer.secho(f"错误: {type(exc).__name__}: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc

    typer.echo(
        json.dumps(
            {
                "input": str(input.resolve()),
                "output": str(output.resolve()),
                "systems": len(systems),
                "frames": frame_count,
                "formats": ["deepmd/raw", "deepmd/npy"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
