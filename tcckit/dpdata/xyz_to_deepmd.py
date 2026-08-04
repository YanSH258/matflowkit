"""Convert a labeled GPUMD/extxyz trajectory to DeepMD raw and NPY datasets."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import typer

from tcckit.common.dpdata_utils import require_dpdata


class InconsistentVirialError(ValueError):
    """Raised when one composition mixes frames with and without virial."""


def _properties_species_column(metadata: str, frame: int) -> int:
    match = re.search(
        r"\bProperties\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|(\S+))",
        metadata,
        flags=re.IGNORECASE,
    )
    if not match:
        raise ValueError(f"第 {frame} 帧第二行缺少 Properties")
    value = next(item for item in match.groups() if item is not None)
    fields = value.split(":")
    if len(fields) % 3:
        raise ValueError(f"第 {frame} 帧 Properties 格式错误: {value}")
    offset = 0
    for index in range(0, len(fields), 3):
        name, _, width_text = fields[index:index + 3]
        try:
            width = int(width_text)
        except ValueError as exc:
            raise ValueError(f"第 {frame} 帧 Properties 列数错误: {width_text}") from exc
        if name.lower() == "species":
            if width != 1:
                raise ValueError(f"第 {frame} 帧 species 列数必须为 1")
            return offset
        offset += width
    raise ValueError(f"第 {frame} 帧 Properties 缺少 species")


def inspect_xyz_virials(path: Path) -> dict:
    """Inspect per-composition virial presence without changing the data."""
    groups = defaultdict(lambda: {"frames": [], "with": [], "without": []})
    frame = 0
    with path.open() as handle:
        while True:
            first = handle.readline()
            while first and not first.strip():
                first = handle.readline()
            if not first:
                break
            frame += 1
            try:
                natoms = int(first.strip())
            except ValueError as exc:
                raise ValueError(f"第 {frame} 帧的原子数不是整数: {first.strip()}") from exc
            metadata = handle.readline()
            if not metadata:
                raise ValueError(f"第 {frame} 帧缺少第二行")
            species_column = _properties_species_column(metadata, frame)
            counts = Counter()
            for atom_index in range(1, natoms + 1):
                line = handle.readline()
                if not line:
                    raise ValueError(f"第 {frame} 帧缺少第 {atom_index} 个原子行")
                columns = line.split()
                if species_column >= len(columns):
                    raise ValueError(f"第 {frame} 帧第 {atom_index} 个原子行缺少 species")
                counts[columns[species_column]] += 1
            composition = tuple(sorted(counts.items()))
            group = groups[composition]
            group["frames"].append(frame)
            target = "with" if re.search(r"(?:^|\s)virial\s*=", metadata, re.IGNORECASE) else "without"
            group[target].append(frame)

    if frame == 0:
        raise ValueError("XYZ 中没有结构帧")
    inconsistent = [
        (composition, values)
        for composition, values in groups.items()
        if values["with"] and values["without"]
    ]
    if inconsistent:
        lines = ["XYZ 中的 virial 标签不一致；同一组成的帧必须全部有或全部没有 virial。"]
        for composition, values in inconsistent:
            formula = "".join(f"{name}{count}" for name, count in composition)
            missing = values["without"]
            shown = ", ".join(map(str, missing[:20]))
            if len(missing) > 20:
                shown += f", ...（另有 {len(missing) - 20} 帧）"
            lines.append(
                f"组成 {formula}: 总帧 {len(values['frames'])}，有 virial {len(values['with'])}，"
                f"缺少 virial {len(missing)}；缺失帧（从 1 开始）: {shown}"
            )
        raise InconsistentVirialError("\n".join(lines))
    return {
        "frames": frame,
        "compositions": len(groups),
        "frames_with_virial": sum(len(values["with"]) for values in groups.values()),
        "frames_without_virial": sum(len(values["without"]) for values in groups.values()),
    }


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
    raw: bool = typer.Option(
        False,
        "--raw",
        help="额外生成 DeepMD raw；默认只生成 NPY",
    ),
) -> None:
    """XYZ 转 DeepMD NPY，可选额外生成 raw。"""
    if not input.is_file():
        typer.secho(f"错误: 输入文件不存在: {input}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    if output.exists():
        if output.is_file() or any(output.iterdir()):
            typer.secho(f"错误: 输出路径已存在且非空: {output}", err=True, fg=typer.colors.RED)
            raise typer.Exit(1)

    dpdata = require_dpdata()
    try:
        virial_summary = inspect_xyz_virials(input)
        systems = dpdata.MultiSystems.from_file(str(input), fmt="gpumd/xyz")
        if len(systems) < 1:
            raise ValueError("dpdata 返回零个 system")
        frame_count = sum(len(system) for system in systems)
        if frame_count < 1:
            raise ValueError("dpdata 返回零帧")
        systems.to_deepmd_npy(str(output), set_size=set_size)
        formats = ["deepmd/npy"]
        if raw:
            systems.to_deepmd_raw(str(output))
            formats.append("deepmd/raw")
    except InconsistentVirialError as exc:
        typer.secho(f"错误: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc
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
                "virial": virial_summary,
                "formats": formats,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
