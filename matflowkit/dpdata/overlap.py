"""mfk dpdata overlap: detect duplicate frames across structure datasets."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import typer


def require_ase():
    """Import ASE lazily with an actionable dependency message."""
    try:
        from ase.io import iread
    except ImportError as exc:
        raise RuntimeError(
            "此命令需要 ASE；请运行 `pip install -e '.[structure]'`"
        ) from exc
    return iread


def frame_hash(
    atoms,
    decimals: int = 6,
    order_independent: bool = False,
    wrap: bool = False,
) -> str:
    """Hash one frame after explicit coordinate rounding and normalization."""
    if wrap:
        positions = atoms.get_scaled_positions(wrap=True) @ atoms.cell.array
    else:
        positions = np.asarray(atoms.positions)
    return normalized_frame_hash(
        atoms.get_chemical_symbols(), atoms.cell.array, positions, atoms.pbc,
        decimals=decimals, order_independent=order_independent,
    )


def normalized_frame_hash(
    symbols,
    cell,
    positions,
    pbc,
    decimals: int = 6,
    order_independent: bool = False,
) -> str:
    """Hash normalized frame arrays; shared by ASE overlap and DeepMD report."""
    symbols = np.asarray(symbols)
    positions = np.asarray(positions, dtype=float)
    positions = np.round(positions, decimals)
    if positions.shape != (len(symbols), 3):
        raise ValueError("coordinates must have shape (natoms, 3)")
    if order_independent:
        order = sorted(
            range(len(symbols)),
            key=lambda index: (
                symbols[index],
                positions[index, 0],
                positions[index, 1],
                positions[index, 2],
            ),
        )
        symbols = symbols[order]
        positions = positions[order]

    digest = hashlib.sha256()
    digest.update("\0".join(symbols).encode())
    digest.update(np.asarray(pbc, dtype=np.uint8).reshape(3).tobytes())
    digest.update(np.round(np.asarray(cell).reshape(3, 3), decimals).astype("<f8").tobytes())
    digest.update(positions.astype("<f8").tobytes())
    return digest.hexdigest()


def collect_hashes(
    path: Path,
    decimals: int,
    order_independent: bool,
    wrap: bool,
) -> tuple[dict[str, list[int]], int]:
    """Return canonical hash to frame-index mapping and total frame count."""
    iread = require_ase()
    hashes: dict[str, list[int]] = {}
    count = 0
    for frame_index, atoms in enumerate(iread(path, index=":")):
        value = frame_hash(atoms, decimals, order_independent, wrap)
        hashes.setdefault(value, []).append(frame_index)
        count += 1
    if count == 0:
        raise ValueError(f"未读取到结构帧: {path}")
    return hashes, count


def overlap(
    reference: Path = typer.Argument(..., help="参考结构数据集"),
    candidate: Path = typer.Argument(..., help="待检查结构数据集"),
    decimals: int = typer.Option(
        6,
        min=0,
        max=12,
        help="取整小数位",
    ),
    order_independent: bool = typer.Option(
        False,
        "--order-independent",
        help="忽略原子顺序",
    ),
    wrap: bool = typer.Option(
        False,
        "--wrap",
        help="比较前 wrap",
    ),
    output: Path = typer.Option(
        Path("frame_overlap.json"),
        "--output",
        "-o",
        help="JSON 汇总路径",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="发现跨数据集重叠帧时返回退出码 2",
    ),
) -> None:
    """检查两个数据集的重复帧。"""
    reference = reference.expanduser().resolve()
    candidate = candidate.expanduser().resolve()
    output = output.expanduser().resolve()
    matches_path = output.with_name(f"{output.stem}_matches.csv")
    if not reference.is_file() or not candidate.is_file():
        missing = [str(path) for path in (reference, candidate) if not path.is_file()]
        typer.secho(
            "错误: 输入不存在: " + ", ".join(missing),
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    existing = [path for path in (output, matches_path) if path.exists()]
    if existing:
        typer.secho(
            "错误: 以下输出已存在: " + ", ".join(str(path) for path in existing),
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    try:
        reference_hashes, reference_count = collect_hashes(
            reference, decimals, order_independent, wrap
        )
        candidate_hashes, candidate_count = collect_hashes(
            candidate, decimals, order_independent, wrap
        )
        common = sorted(set(reference_hashes) & set(candidate_hashes))
        rows = []
        for value in common:
            for reference_index in reference_hashes[value]:
                for candidate_index in candidate_hashes[value]:
                    rows.append(
                        {
                            "hash": value,
                            "reference_frame": reference_index,
                            "candidate_frame": candidate_index,
                        }
                    )
        result = {
            "reference": str(reference),
            "reference_frames": reference_count,
            "reference_unique_frames": len(reference_hashes),
            "reference_internal_duplicates": reference_count - len(reference_hashes),
            "candidate": str(candidate),
            "candidate_frames": candidate_count,
            "candidate_unique_frames": len(candidate_hashes),
            "candidate_internal_duplicates": candidate_count - len(candidate_hashes),
            "rounding_decimals_A": decimals,
            "order_independent": order_independent,
            "wrapped_into_cell": wrap,
            "overlapping_unique_frames": len(common),
            "overlapping_frame_pairs": len(rows),
            "scope": "canonical duplicate detection, not structural similarity",
            "matches": str(matches_path),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        with matches_path.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=("hash", "reference_frame", "candidate_frame"),
            )
            writer.writeheader()
            writer.writerows(rows)
    except Exception as exc:
        output.unlink(missing_ok=True)
        matches_path.unlink(missing_ok=True)
        typer.secho(
            f"错误: {type(exc).__name__}: {exc}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(2) from exc

    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    if strict and common:
        raise typer.Exit(2)
