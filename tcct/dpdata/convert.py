"""Generic labeled atomistic-data conversion through dpdata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
import typer

from tcct.common.dpdata_utils import (
    finite_labeled,
    normalize,
    parse_type_map,
    require_dpdata,
)


def convert(
    input: Path = typer.Argument(..., help="输入文件或目录"),
    output: Path = typer.Argument(..., help="输出文件或目录"),
    input_format: str = typer.Option(..., "--from", help="dpdata 输入格式"),
    output_format: str = typer.Option(..., "--to", help="dpdata 输出格式"),
    type_map: Optional[str] = typer.Option(None, help="元素顺序"),
    set_size: int = typer.Option(2000, min=1),
    require_virial: bool = typer.Option(False, "--virial/--no-virial"),
):
    """按准确的 dpdata 格式名直接转换带标签数据。"""
    dpdata = require_dpdata()
    if not input.exists():
        typer.secho(f"错误: 输入不存在: {input}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    if output.exists():
        if output.is_dir() and any(output.iterdir()):
            typer.secho(f"错误: 输出目录非空: {output}", err=True, fg=typer.colors.RED)
            raise typer.Exit(1)
        if output.is_file():
            typer.secho(f"错误: 输出文件已存在: {output}", err=True, fg=typer.colors.RED)
            raise typer.Exit(1)
    try:
        data = dpdata.LabeledSystem(str(input), fmt=input_format)
        if len(data) < 1:
            raise ValueError("dpdata 返回零帧")
        finite_labeled(data, require_virial=require_virial)
        if type_map:
            names = parse_type_map(type_map, set(data.data["atom_names"]))
            data = normalize(data, names)
        kwargs = {}
        if output_format in {"deepmd/npy", "deepmd/npy/mixed"}:
            kwargs.update({"set_size": set_size, "prec": np.float64})
        data.to(output_format, str(output), **kwargs)
    except Exception as exc:
        typer.secho(f"错误: {type(exc).__name__}: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc
    typer.echo(
        json.dumps(
            {
                "input": str(input.resolve()),
                "output": str(output.resolve()),
                "input_format": input_format,
                "output_format": output_format,
                "frames": len(data),
                "natoms": data.get_natoms(),
                "atom_names": list(data.data["atom_names"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
