"""tck cp2k aimd-to-deepmd: convert one CP2K AIMD run with dpdata."""

from __future__ import annotations

import json
import logging
import platform
import shutil
from importlib import metadata
from pathlib import Path
from typing import Optional

import numpy as np
import typer

from tcckit.common.dpdata_utils import (
    exact_formula,
    finite_labeled,
    normalize,
    parse_type_map,
    require_dpdata,
)
from tcckit.common.io import (
    ensure_empty_output,
    sha256_file,
    write_csv,
    write_json,
    write_sha256_manifest,
)
from tcckit.cp2k.parser import parse_cp2k_output


SOURCE_PATTERNS = ("*-pos-*.xyz", "*-frc-*.xyz", "*.cell", "*.ener")


def require_cp2kdata() -> str:
    """Load the dpdata CP2K plugin and return its installed version."""
    try:
        import cp2kdata  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "CP2K AIMD 转换需要 cp2kdata；请重新执行 `uv sync` 或重新安装 TCCKit"
        ) from exc
    try:
        return metadata.version("cp2kdata")
    except metadata.PackageNotFoundError:
        return "unknown"


def discover_source_files(root: Path, log_path: Path) -> list[Path]:
    """Return the CP2K log and native AIMD trajectory files."""
    files = [log_path]
    missing = []
    for pattern in SOURCE_PATTERNS:
        matches = sorted(path for path in root.glob(pattern) if path.is_file())
        if not matches:
            missing.append(pattern)
        files.extend(matches)
    if missing:
        raise FileNotFoundError("缺少 CP2K AIMD 文件: " + ", ".join(missing))
    return sorted(set(files))


def labeled_arrays_match(reference, candidate, has_virial: bool) -> bool:
    """Check that a converted labeled system preserves all numeric arrays."""
    keys = ["cells", "coords", "energies", "forces"]
    if has_virial:
        keys.append("virials")
    return all(
        np.allclose(
            np.asarray(reference.data[key], dtype=float),
            np.asarray(candidate.data[key], dtype=float),
            rtol=1.0e-10,
            atol=1.0e-7,
        )
        for key in keys
    )


def aimd_to_deepmd(
    root: Path = typer.Argument(Path("."), help="单个 CP2K AIMD 计算目录"),
    output: Path = typer.Argument(
        Path("cp2k_aimd_dataset"),
        help="新的数据集目录",
    ),
    log_name: str = typer.Option(
        "output.log",
        "--log-name",
        help="计算目录中的 CP2K 标准输出文件名",
    ),
    type_map: Optional[str] = typer.Option(
        None,
        "--type-map",
        help="元素顺序，逗号或空格分隔",
    ),
    set_size: int = typer.Option(
        5000,
        min=1,
        help="每个 DeepMD set.* 的最大帧数",
    ),
    restart: bool = typer.Option(
        False,
        "--restart/--no-restart",
        help="输入是否为 CP2K restart 续算轨迹",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="在终端输出完整 JSON 汇总",
    ),
) -> None:
    """用 dpdata + cp2kdata 将 CP2K AIMD 转为 DeepMD NPY。"""
    root = root.expanduser().resolve()
    output = output.expanduser().resolve()
    if not root.is_dir():
        typer.secho(f"错误: AIMD 目录不存在: {root}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    log_path = root / log_name
    if not log_path.is_file():
        typer.secho(f"错误: CP2K 输出不存在: {log_path}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    if output.exists():
        typer.secho(
            f"错误: 输出路径已存在，请使用新的目录: {output}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    try:
        source_files = discover_source_files(root, log_path)
        parsed = parse_cp2k_output(log_path)
        if parsed["status"] != "PASS":
            raise ValueError("CP2K 输出未通过完成、SCF、能量、力和晶胞审计")

        cp2kdata_version = require_cp2kdata()
        dpdata = require_dpdata()
        plugin_logger = logging.getLogger("cp2kdata.dpdata_plugin")
        previous_level = plugin_logger.level
        plugin_logger.setLevel(logging.ERROR)
        try:
            data = dpdata.LabeledSystem(
                str(root),
                fmt="cp2kdata/md",
                cp2k_output_name=log_name,
                restart=restart,
                true_symbols=True,
            )
        finally:
            plugin_logger.setLevel(previous_level)
        if len(data) < 1:
            raise ValueError("dpdata 返回零帧")
        has_virial = "virials" in data.data
        finite = finite_labeled(data, require_virial=has_virial)
        if int(finite.sum()) != len(data):
            bad = np.flatnonzero(~finite).tolist()
            raise ValueError(f"存在 NaN/Inf 帧: {bad}")
        if parsed["scf_not_converged_runs"]:
            raise ValueError("CP2K 输出包含未收敛 SCF")
        if parsed["scf_converged_runs"] < len(data):
            raise ValueError(
                f"只有 {parsed['scf_converged_runs']} 次收敛 SCF，"
                f"但 dpdata 读取到 {len(data)} 帧"
            )

        discovered = {str(name) for name in data.data["atom_names"]}
        global_map = parse_type_map(type_map, discovered)
        data = normalize(data, global_map)
        system_id = exact_formula(data, global_map)

        ensure_empty_output(output)
        npy_path = output / "deepmd_npy" / system_id
        npy_path.parent.mkdir(parents=True, exist_ok=True)
        data.to(
            "deepmd/npy",
            str(npy_path),
            set_size=set_size,
            prec=np.float64,
        )
        loaded = dpdata.LabeledSystem(str(npy_path), fmt="deepmd/npy")
        loaded_finite = finite_labeled(loaded, require_virial=has_virial)
        deepmd_validation = bool(
            len(loaded) == len(data)
            and loaded.get_natoms() == data.get_natoms()
            and int(loaded_finite.sum()) == len(data)
            and list(loaded.data["atom_names"]) == global_map
            and labeled_arrays_match(data, loaded, has_virial)
        )
        if not deepmd_validation:
            raise RuntimeError("DeepMD NPY 回读验证失败")

        energies = np.asarray(data.data["energies"], dtype=float)
        forces = np.asarray(data.data["forces"], dtype=float)
        force_maxima = np.linalg.norm(forces, axis=2).max(axis=1)
        volumes = np.abs(np.linalg.det(np.asarray(data.data["cells"], dtype=float)))
        frame_rows = [
            {
                "frame": index,
                "energy_eV": float(energies[index]),
                "maximum_force_eV_A": float(force_maxima[index]),
                "cell_volume_A3": float(volumes[index]),
                "has_virial": has_virial,
            }
            for index in range(len(data))
        ]
        source_rows = [
            {
                "file": str(path.relative_to(root)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in source_files
        ]
        write_csv(output / "frame_manifest.csv", frame_rows)
        write_csv(output / "source_files.csv", source_rows)

        summary = {
            "input": str(root),
            "output": str(output),
            "scope": "CP2K AIMD to DeepMD NPY via dpdata and cp2kdata",
            "log": str(log_path),
            "restart": restart,
            "system": system_id,
            "frames": len(data),
            "atoms": data.get_natoms(),
            "type_map": global_map,
            "has_virial": has_virial,
            "energy_range_eV": [float(energies.min()), float(energies.max())],
            "maximum_force_eV_A": float(force_maxima.max()),
            "cell_volume_range_A3": [float(volumes.min()), float(volumes.max())],
            "cp2k_audit": {
                "completed": parsed["completed"],
                "scf_converged_runs": parsed["scf_converged_runs"],
                "scf_not_converged_runs": parsed["scf_not_converged_runs"],
                "energy_records": parsed["energy_records"],
                "force_blocks": parsed["force_blocks"],
            },
            "deepmd_npy": str(npy_path),
            "deepmd_roundtrip_validation": "PASS",
            "roundtrip_validation": "PASS",
            "dpdata_version": getattr(dpdata, "__version__", "unknown"),
            "cp2kdata_version": cp2kdata_version,
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

    if json_output:
        typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    typer.echo("转换完成")
    typer.echo(f"体系: {summary['system']}")
    typer.echo(f"帧数: {summary['frames']}    原子数: {summary['atoms']}")
    typer.echo(f"元素顺序: {' '.join(summary['type_map'])}")
    typer.echo(f"位力: {'有' if summary['has_virial'] else '无'}")
    typer.echo(f"DeepMD NPY: {summary['deepmd_npy']}")
    typer.echo(f"验证: {summary['roundtrip_validation']}")
    typer.echo(f"详细报告: {output / 'reports' / 'summary.json'}")
