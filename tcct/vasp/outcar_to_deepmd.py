"""Collect VASP OUTCAR labels into composition-resolved DeepMD NPY."""

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
    append_system, exact_formula, finite_labeled, normalize, parse_type_map, require_dpdata,
)
from tcct.common.io import ensure_empty_output, write_csv, write_json, write_sha256_manifest


def outcar_to_deepmd(
    root: Path = typer.Argument(Path("."), help="VASP 任务根目录或 OUTCAR"),
    output: Path = typer.Argument(Path("vasp_dataset"), help="输出目录"),
    pattern: str = typer.Option("**/OUTCAR", help="相对于根目录的 OUTCAR 搜索模式"),
    frames: str = typer.Option("all", help="all 或 final"),
    type_map: Optional[str] = typer.Option(None, help="元素顺序，逗号或空格分隔"),
    set_size: int = typer.Option(2000, min=1),
    expected: Optional[int] = typer.Option(None, help="预期 OUTCAR 数量"),
    require_virial: bool = typer.Option(True, "--virial/--no-virial"),
) -> None:
    """从单个或多个 VASP OUTCAR 提取 DeepMD NPY。"""
    root = root.expanduser().resolve()
    output = output.expanduser().resolve()
    if frames not in {"all", "final"}:
        typer.secho("错误: --frames 必须是 all 或 final", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    if not root.exists():
        typer.secho(f"错误: 输入不存在: {root}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    if output.exists():
        typer.secho(f"错误: 输出路径已存在: {output}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    paths = [root] if root.is_file() else sorted(path for path in root.glob(pattern) if path.is_file())
    if not paths:
        typer.secho("错误: 未发现 OUTCAR", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    if expected is not None and expected != len(paths):
        typer.secho(f"错误: 发现 {len(paths)} 个 OUTCAR，预期 {expected}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2)

    try:
        dpdata = require_dpdata()
        parsed = []
        audit_rows = []
        discovered_elements: set[str] = set()
        for path in paths:
            row = {"outcar": str(path), "format": "vasp/outcar", "status": "PENDING", "error": ""}
            try:
                data = dpdata.LabeledSystem(str(path), fmt="vasp/outcar", convergence_check=True)
                if len(data) < 1:
                    raise ValueError("dpdata 返回零个已收敛帧")
                valid = np.flatnonzero(finite_labeled(data, require_virial=require_virial))
                if valid.size < 1:
                    raise ValueError("没有标注完整的有限值帧")
                if frames == "final":
                    valid = valid[-1:]
                selected = data.sub_system(valid)
                discovered_elements.update(selected.data["atom_names"])
                parsed.append((path, selected, valid))
                row.update({"status": "PASS", "raw_frames": len(data), "written_frames": len(selected)})
            except Exception as exc:
                row.update({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"})
            audit_rows.append(row)
        failed = [row for row in audit_rows if row["status"] != "PASS"]
        if failed:
            raise RuntimeError(f"{len(failed)}/{len(paths)} 个 OUTCAR 无法解析；未创建输出")

        global_map = parse_type_map(type_map, discovered_elements)
        ensure_empty_output(output)
        systems = defaultdict(lambda: None)
        offsets: Counter[str] = Counter()
        frame_rows = []
        for path, data, raw_indices in parsed:
            system_id = exact_formula(data, global_map)
            normalized = normalize(data, global_map)
            systems[system_id] = append_system(systems[system_id], normalized)
            for local_index, raw_index in enumerate(raw_indices):
                frame_rows.append({
                    "system_id": system_id,
                    "output_frame_index": offsets[system_id] + local_index,
                    "outcar": str(path), "parsed_frame_index": int(raw_index),
                    "energy_eV": float(data.data["energies"][local_index]),
                })
            offsets[system_id] += len(data)

        system_rows = []
        for system_id, data in sorted(systems.items()):
            target = output / "deepmd_npy" / system_id
            data.to("deepmd/npy", str(target), set_size=set_size, prec=np.float64)
            loaded = dpdata.LabeledSystem(str(target), fmt="deepmd/npy")
            valid = finite_labeled(loaded, require_virial=require_virial)
            passed = len(loaded) == len(data) and int(valid.sum()) == len(data) and list(loaded.data["atom_names"]) == global_map
            system_rows.append({
                "system_id": system_id, "frames": len(data), "natoms": data.get_natoms(),
                "type_map": " ".join(global_map), "validation": "PASS" if passed else "FAIL",
            })
        write_csv(output / "task_parse_audit.csv", audit_rows)
        write_csv(output / "frame_manifest.csv", frame_rows)
        write_csv(output / "system_summary.csv", system_rows)
        summary = {
            "root": str(root), "output": str(output), "parser": "dpdata.LabeledSystem",
            "input_format": "vasp/outcar", "dpdata_version": getattr(dpdata, "__version__", "unknown"),
            "python_version": platform.python_version(), "numpy_version": np.__version__,
            "frame_mode": frames, "require_virial": require_virial, "type_map": global_map,
            "method_consistency_checked": False,
            "outcars_discovered": len(paths), "outcars_parsed": len(parsed),
            "systems": len(system_rows), "frames": len(frame_rows),
            "all_systems_validated": all(row["validation"] == "PASS" for row in system_rows),
        }
        write_json(output / "reports" / "summary.json", summary)
        write_sha256_manifest(output)
    except Exception as exc:
        if output.exists():
            shutil.rmtree(output)
        typer.secho(f"错误: {type(exc).__name__}: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["all_systems_validated"]:
        raise typer.Exit(2)
