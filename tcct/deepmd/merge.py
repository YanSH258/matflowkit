"""Merge multiple DeepMD NPY datasets by exact chemical composition."""

from __future__ import annotations

import hashlib
import json
import platform
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import numpy as np
import typer

from tcct.common.dpdata_utils import (
    append_system,
    exact_formula,
    find_deepmd_systems,
    finite_labeled,
    normalize,
    parse_type_map,
    require_dpdata,
)
from tcct.common.io import (
    ensure_empty_output,
    write_csv,
    write_json,
    write_sha256_manifest,
)


def _frame_hash(data, index: int) -> str:
    digest = hashlib.sha256()
    for key in ["cells", "coords"]:
        values = np.round(np.asarray(data.data[key][index], dtype=np.float64), 10)
        digest.update(values.tobytes())
    digest.update(np.asarray(data.data["atom_types"], dtype=np.int64).tobytes())
    return digest.hexdigest()


def merge(
    inputs: list[Path] = typer.Argument(..., help="NPY 数据集目录"),
    output: Path = typer.Option(..., "-o", "--output", help="输出目录"),
    type_map: Optional[str] = typer.Option(
        None, help="元素顺序"
    ),
    set_size: int = typer.Option(2000, min=1),
    allow_duplicates: bool = typer.Option(False, help="允许完全相同的 cell+coord 帧"),
    require_virial: bool = typer.Option(True, "--virial/--no-virial"),
):
    """合并 DeepMD NPY 数据集。"""
    if len(inputs) < 2:
        typer.secho("错误: 至少需要两个输入数据集", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    dpdata = require_dpdata()
    loaded_sources = []
    elements: set[str] = set()
    for source_index, root in enumerate(inputs):
        if not root.is_dir():
            typer.secho(f"错误: 目录不存在: {root}", err=True, fg=typer.colors.RED)
            raise typer.Exit(1)
        systems = find_deepmd_systems(root)
        if not systems:
            typer.secho(f"错误: 未发现 NPY system: {root}", err=True, fg=typer.colors.RED)
            raise typer.Exit(1)
        for path in systems:
            data = dpdata.LabeledSystem(str(path), fmt="deepmd/npy")
            finite_labeled(data, require_virial=require_virial)
            elements.update(data.data["atom_names"])
            loaded_sources.append((source_index, root, path, data))
    try:
        global_map = parse_type_map(type_map, elements)
        ensure_empty_output(output)
    except (ValueError, FileExistsError) as exc:
        typer.secho(f"错误: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from exc

    grouped = defaultdict(lambda: None)
    offsets: Counter[str] = Counter()
    hashes: set[str] = set()
    duplicate_rows = []
    frame_rows = []
    for source_index, root, path, data in loaded_sources:
        normalized = normalize(data, global_map)
        system_id = exact_formula(normalized, global_map)
        for index in range(len(normalized)):
            signature = _frame_hash(normalized, index)
            if signature in hashes:
                duplicate_rows.append(
                    {
                        "source_index": source_index,
                        "source_root": str(root.resolve()),
                        "source_system": str(path),
                        "source_frame_index": index,
                        "frame_hash": signature,
                    }
                )
            hashes.add(signature)
            frame_rows.append(
                {
                    "system_id": system_id,
                    "output_frame_index": offsets[system_id] + index,
                    "source_index": source_index,
                    "source_root": str(root.resolve()),
                    "source_system": str(path),
                    "source_frame_index": index,
                    "energy_eV": float(normalized.data["energies"][index]),
                    "frame_hash": signature,
                }
            )
        grouped[system_id] = append_system(grouped[system_id], normalized)
        offsets[system_id] += len(normalized)
    if duplicate_rows and not allow_duplicates:
        write_csv(output / "duplicate_frames.csv", duplicate_rows)
        typer.secho(
            f"错误: 发现 {len(duplicate_rows)} 个重复帧；报告已写入 {output}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(2)

    system_rows = []
    for system_id, data in sorted(grouped.items()):
        path = output / "deepmd_npy" / system_id
        data.to("deepmd/npy", str(path), set_size=set_size, prec=np.float64)
        check = dpdata.LabeledSystem(str(path), fmt="deepmd/npy")
        valid = finite_labeled(check, require_virial=require_virial)
        passed = (
            len(check) == len(data)
            and int(valid.sum()) == len(data)
            and list(check.data["atom_names"]) == global_map
        )
        system_rows.append(
            {
                "system_id": system_id,
                "frames": len(data),
                "natoms": data.get_natoms(),
                "validation": "PASS" if passed else "FAIL",
            }
        )
    write_csv(output / "frame_manifest.csv", frame_rows)
    write_csv(output / "duplicate_frames.csv", duplicate_rows)
    write_csv(output / "system_summary.csv", system_rows)
    summary = {
        "inputs": [str(path.resolve()) for path in inputs],
        "output": str(output.resolve()),
        "dpdata_version": getattr(dpdata, "__version__", "unknown"),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "type_map": global_map,
        "systems": len(system_rows),
        "frames": len(frame_rows),
        "unique_frame_hashes": len(hashes),
        "duplicate_frames": len(duplicate_rows),
        "allow_duplicates": allow_duplicates,
        "all_systems_validated": all(
            row["validation"] == "PASS" for row in system_rows
        ),
    }
    write_json(output / "reports" / "summary.json", summary)
    write_sha256_manifest(output)
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["all_systems_validated"]:
        raise typer.Exit(2)
