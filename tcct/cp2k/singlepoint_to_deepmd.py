"""Collect completed CP2K single points as DeepMD NPY."""

from __future__ import annotations

import json
import platform
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import numpy as np
import typer

from tcct.common.dpdata_utils import (
    append_system,
    exact_formula,
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
from tcct.cp2k.audit import discover_outputs, public_row
from tcct.cp2k.parser import parse_cp2k_output


def require_ase_read():
    try:
        from ase.io import read
    except ImportError as exc:
        raise RuntimeError(
            "此命令需要 ASE；请运行 `pip install -e '.[structure]'`"
        ) from exc
    return read


def one_frame_system(dpdata, atoms, parsed: dict, type_map: list[str]):
    """Build one normalized dpdata LabeledSystem from a structure and labels."""
    symbols = atoms.get_chemical_symbols()
    counts = Counter(symbols)
    atom_types = np.asarray([type_map.index(symbol) for symbol in symbols])
    data = {
        "atom_names": list(type_map),
        "atom_numbs": [counts.get(element, 0) for element in type_map],
        "atom_types": atom_types,
        "orig": np.zeros(3, dtype=float),
        "cells": np.asarray([parsed["_cell"]], dtype=float),
        "coords": np.asarray([atoms.positions], dtype=float),
        "energies": np.asarray([parsed["final_energy_eV"]], dtype=float),
        "forces": np.asarray([parsed["_forces"]], dtype=float),
    }
    return normalize(dpdata.LabeledSystem(data=data), type_map)


def singlepoint_to_deepmd(
    root: Path = typer.Argument(Path("."), help="CP2K 单点任务根目录"),
    output: Path = typer.Argument(
        Path("cp2k_dataset"),
        help="输出目录",
    ),
    pattern: str = typer.Option(
        "**/output.log",
        help="相对于任务根目录的 CP2K 输出搜索模式",
    ),
    structure_name: str = typer.Option(
        "structure.xyz",
        "--structure-name",
        help="每个输出目录中的单点输入结构文件名",
    ),
    type_map: Optional[str] = typer.Option(
        None,
        "--type-map",
        help="元素顺序，逗号或空格分隔",
    ),
    set_size: int = typer.Option(
        2000,
        min=1,
        help="每个 DeepMD set.* 的最大帧数",
    ),
    expected: Optional[int] = typer.Option(None, help="预期任务数"),
    skip_incomplete: bool = typer.Option(
        False,
        "--skip-incomplete",
        help="跳过未通过审计或无法读取的任务",
    ),
) -> None:
    """收集通过审计的 CP2K 单点结果并生成 DeepMD NPY。"""
    root = root.expanduser().resolve()
    output = output.expanduser().resolve()
    if not root.exists():
        typer.secho(f"错误: 根目录不存在: {root}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    if output.exists():
        typer.secho(
            f"错误: 输出路径已存在，请使用新的目录: {output}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    paths = discover_outputs(root, pattern)
    if not paths:
        typer.secho("错误: 未发现 CP2K 输出", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    if expected is not None and expected != len(paths):
        typer.secho(
            f"错误: 发现 {len(paths)} 个任务，预期 {expected}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(2)

    try:
        dpdata = require_dpdata()
        read = require_ase_read()
        parsed_tasks = []
        audit_rows = []
        discovered_elements: set[str] = set()
        for output_path in paths:
            parsed = parse_cp2k_output(output_path)
            structure_path = output_path.parent / structure_name
            row = {
                **public_row(parsed),
                "structure": str(structure_path),
                "collect_status": "PENDING",
                "error": "",
            }
            try:
                if parsed["status"] != "PASS":
                    raise ValueError("CP2K 输出未通过审计")
                if not structure_path.is_file():
                    raise FileNotFoundError(f"缺少结构文件: {structure_path}")
                atoms = read(structure_path, index=-1)
                if len(atoms) != parsed["final_force_atoms"]:
                    raise ValueError(
                        f"结构含 {len(atoms)} 个原子，最终力块含 "
                        f"{parsed['final_force_atoms']} 个原子"
                    )
                if not np.isfinite(atoms.positions).all():
                    raise ValueError("结构包含非有限坐标")
                discovered_elements.update(atoms.get_chemical_symbols())
                parsed_tasks.append((output_path, structure_path, atoms, parsed))
                row["collect_status"] = "PASS"
                row["formula"] = atoms.get_chemical_formula()
                row["atoms"] = len(atoms)
            except Exception as exc:
                row["collect_status"] = "SKIP" if skip_incomplete else "FAIL"
                row["error"] = f"{type(exc).__name__}: {exc}"
            audit_rows.append(row)

        failed = [row for row in audit_rows if row["collect_status"] == "FAIL"]
        if failed:
            raise RuntimeError(
                f"{len(failed)}/{len(audit_rows)} 个任务无法收集；未创建输出"
            )
        if not parsed_tasks:
            raise RuntimeError("没有可收集的任务")

        global_map = parse_type_map(type_map, discovered_elements)
        ensure_empty_output(output)
        systems = defaultdict(lambda: None)
        frame_rows = []
        system_offsets: Counter[str] = Counter()
        for output_path, structure_path, atoms, parsed in parsed_tasks:
            data = one_frame_system(dpdata, atoms, parsed, global_map)
            system_id = exact_formula(data, global_map)
            systems[system_id] = append_system(systems[system_id], data)
            frame_rows.append(
                {
                    "system_id": system_id,
                    "output_frame_index": system_offsets[system_id],
                    "cp2k_output": str(output_path),
                    "structure": str(structure_path),
                    "energy_eV": parsed["final_energy_eV"],
                    "maximum_force_eV_A": parsed["final_max_force_eV_A"],
                }
            )
            system_offsets[system_id] += 1

        system_rows = []
        for system_id, data in sorted(systems.items()):
            npy_path = output / "deepmd_npy" / system_id
            npy_path.parent.mkdir(parents=True, exist_ok=True)
            data.to(
                "deepmd/npy",
                str(npy_path),
                set_size=set_size,
                prec=np.float64,
            )
            loaded = dpdata.LabeledSystem(str(npy_path), fmt="deepmd/npy")
            valid = finite_labeled(loaded, require_virial=False)
            passed = (
                len(loaded) == len(data)
                and int(valid.sum()) == len(data)
                and list(loaded.data["atom_names"]) == global_map
            )
            system_rows.append(
                {
                    "system_id": system_id,
                    "frames": len(data),
                    "atoms": data.get_natoms(),
                    "type_map": " ".join(global_map),
                    "validation": "PASS" if passed else "FAIL",
                    "deepmd_npy": str(npy_path),
                }
            )

        write_csv(output / "task_parse_audit.csv", audit_rows)
        write_csv(output / "frame_manifest.csv", frame_rows)
        write_csv(output / "system_summary.csv", system_rows)
        summary = {
            "root": str(root),
            "output": str(output),
            "scope": "CP2K single-point energy and force collection",
            "method_consistency_checked": False,
            "structure_name": structure_name,
            "type_map": global_map,
            "outputs_discovered": len(paths),
            "tasks_collected": len(parsed_tasks),
            "tasks_skipped": sum(
                row["collect_status"] == "SKIP" for row in audit_rows
            ),
            "systems": len(system_rows),
            "frames": len(frame_rows),
            "all_systems_validated": all(
                row["validation"] == "PASS" for row in system_rows
            ),
            "dpdata_version": getattr(dpdata, "__version__", "unknown"),
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
        }
        write_json(output / "reports" / "summary.json", summary)
        write_sha256_manifest(output)
    except Exception as exc:
        if output.exists():
            shutil.rmtree(output)
        typer.secho(
            f"错误: {type(exc).__name__}: {exc}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(2) from exc

    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["all_systems_validated"]:
        raise typer.Exit(2)
