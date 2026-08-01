"""Convert all DeepMD NPY systems below a directory to one GPUMD extxyz file."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
import typer

from matflowkit.common.dpdata_utils import (
    find_deepmd_systems,
    finite_labeled,
    normalize,
    parse_type_map,
    require_dpdata,
)


def _composition_key(system) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(
        (name, int(count))
        for name, count in zip(system.data["atom_names"], system.data["atom_numbs"])
        if count
    ))


def _atom_symbols(system) -> list[str]:
    names = system.data["atom_names"]
    return [names[int(index)] for index in system.data["atom_types"]]


def from_deepmd(
    dataset: Path = typer.Argument(..., help="DeepMD NPY 单个 system 或数据集根目录"),
    output: Path = typer.Argument(Path("train.xyz"), help="GPUMD Extended XYZ 输出文件"),
    type_map: Optional[str] = typer.Option(None, help="统一元素顺序，逗号或空格分隔"),
    require_virial: bool = typer.Option(False, "--virial/--no-virial", help="是否要求所有帧含 virial"),
) -> None:
    """遍历 DeepMD NPY systems，合并写为一个 GPUMD train.xyz。"""
    dataset = dataset.expanduser().resolve()
    output = output.expanduser().resolve()
    if not dataset.is_dir():
        typer.secho(f"错误: 数据集目录不存在: {dataset}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    if output.exists():
        typer.secho(f"错误: 输出文件已存在: {output}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)

    dpdata = require_dpdata()
    temporary: Path | None = None
    try:
        paths = find_deepmd_systems(dataset)
        if not paths:
            raise ValueError("未找到 DeepMD NPY system（需要 type.raw + set.*/）")

        loaded = []
        discovered: set[str] = set()
        input_frames = 0
        for path in paths:
            system = dpdata.LabeledSystem(str(path), fmt="deepmd/npy")
            if len(system) < 1:
                raise ValueError(f"system 为零帧: {path}")
            valid = finite_labeled(system, require_virial=require_virial)
            if int(valid.sum()) != len(system):
                raise ValueError(f"system 含 NaN/Inf 或不完整标签帧: {path}")
            discovered.update(system.data["atom_names"])
            input_frames += len(system)
            loaded.append(system)

        global_map = parse_type_map(type_map, discovered)
        normalized = [normalize(system, global_map) for system in loaded]
        systems = dpdata.MultiSystems(*normalized, type_map=global_map)

        output.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        systems.to("gpumd/xyz", str(temporary))

        checked = dpdata.MultiSystems.from_file(str(temporary), fmt="gpumd/xyz")
        output_frames = sum(len(system) for system in checked)
        if len(checked) != len(systems) or output_frames != input_frames:
            raise ValueError(
                "GPUMD XYZ 回读不一致: "
                f"systems {len(checked)}/{len(systems)}, frames {output_frames}/{input_frames}"
            )
        for system in checked:
            valid = finite_labeled(system, require_virial=require_virial)
            if int(valid.sum()) != len(system):
                raise ValueError("GPUMD XYZ 回读后存在不完整或非有限标签")
        source_by_composition = {_composition_key(system): system for system in systems}
        restored_by_composition = {_composition_key(system): system for system in checked}
        if set(restored_by_composition) != set(source_by_composition):
            raise ValueError("GPUMD XYZ 回读后的组成集合不一致")
        for composition, source in source_by_composition.items():
            restored = restored_by_composition[composition]
            label = "".join(f"{name}{count}" for name, count in composition)
            if _atom_symbols(source) != _atom_symbols(restored):
                raise ValueError(f"GPUMD XYZ 回读后的逐原子元素顺序不一致: {label}")
            keys = ["cells", "coords", "energies", "forces"]
            if "virials" in source.data:
                keys.append("virials")
            for key in keys:
                if key not in restored.data or not np.allclose(
                    source.data[key], restored.data[key], rtol=1e-10, atol=1e-8
                ):
                    raise ValueError(f"GPUMD XYZ 回读后的 {key} 数值不一致: {label}")
        temporary.replace(output)
        temporary = None
    except Exception as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        typer.secho(f"错误: {type(exc).__name__}: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc

    typer.echo(json.dumps({
        "dataset": str(dataset), "output": str(output),
        "input_format": "deepmd/npy", "output_format": "gpumd/xyz",
        "systems": len(systems), "frames": input_frames,
        "type_map": global_map, "require_virial": require_virial,
        "roundtrip_validation": "PASS",
    }, ensure_ascii=False, indent=2))
