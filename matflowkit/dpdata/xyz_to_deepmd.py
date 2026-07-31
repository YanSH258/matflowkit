"""Convert a labeled GPUMD/extxyz trajectory to DeepMD raw and NPY datasets."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from matflowkit.common.dpdata_utils import require_dpdata


def xyz_to_deepmd(
    input: Path = typer.Argument(
        Path("train.xyz"),
        help="带 energy/force/virial 标注的 GPUMD/extxyz 文件",
    ),
    output: Path = typer.Argument(
        Path("deepmd"),
        help="DeepMD 输出目录（按化学组成分 system）",
    ),
    set_size: int = typer.Option(
        2000,
        min=1,
        help="每个 set.* NPY 分片最多包含的帧数",
    ),
) -> None:
    """将 GPUMD ``train.xyz`` 转为 DeepMD raw + NPY。

    输入必须是带有晶胞、能量和原子力标注的 GPUMD/extxyz。输出目录按精确
    化学组成拆分为多个 DeepMD system；每个 system 同时包含 ``type.raw``、
    ``type_map.raw``、raw 标签文件及 ``set.*/*.npy``。示例：
    ``mfk dpdata xyz-to-deepmd train.xyz deepmd``。
    """
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
