"""mfk dpa4 evaluate: label one or more structures with DPA4."""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import numpy as np
import typer

from mdkit.dpa4.common import (
    build_calculator,
    maximum_force,
    require_dependencies,
    resolve_model,
)


def frame_metrics(energy: float, forces: np.ndarray, atom_count: int) -> dict:
    """Return compact energy and force diagnostics for one frame."""
    values = np.asarray(forces, dtype=float)
    return {
        "energy_eV": float(energy),
        "energy_per_atom_eV": float(energy / atom_count),
        "force_component_rms_eV_A": float(np.sqrt(np.mean(values**2))),
        "force_component_mae_eV_A": float(np.mean(np.abs(values))),
        "maximum_atomic_force_eV_A": maximum_force(values),
    }


def evaluate(
    input: Path = typer.Argument(..., help="ASE 可读取的单帧或多帧结构文件"),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="带 DPA4 标注的 extxyz；默认 INPUT_dpa4_evaluated.extxyz",
    ),
    model: Path | None = typer.Option(
        None,
        "--model",
        envvar="DPA4_MODEL",
        help="DPA4 model.pt；也可设置 DPA4_MODEL",
    ),
    index: str = typer.Option(
        ":",
        "--index",
        help="ASE 帧选择表达式，默认读取全部帧",
    ),
    use_d3: bool = typer.Option(
        True,
        "--d3/--no-d3",
        help="是否叠加 PBE-D3(BJ)",
    ),
    stress: bool = typer.Option(
        False,
        "--stress/--no-stress",
        help="同时请求六分量应力；默认只计算能量和力",
    ),
) -> None:
    """使用 DPA4 为结构文件中的选定帧计算能量、原子力和可选应力。

    输出带单点标注的 extxyz、逐帧 CSV 和 JSON 汇总。该命令不优化结构，也不
    覆盖已有输出。DPA4 模型按 ``--model``、``DPA4_MODEL`` 和用户约定路径查找。
    """
    input = input.expanduser().resolve()
    if not input.is_file():
        typer.secho(f"错误: 输入不存在: {input}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    output = (
        output.expanduser().resolve()
        if output is not None
        else input.with_name(f"{input.stem}_dpa4_evaluated.extxyz")
    )
    metrics_path = output.with_name(f"{output.stem}_metrics.csv")
    summary_path = output.with_name(f"{output.stem}_summary.json")
    existing = [path for path in (output, metrics_path, summary_path) if path.exists()]
    if existing:
        typer.secho(
            "错误: 以下输出已存在: " + ", ".join(str(path) for path in existing),
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    try:
        require_dependencies(use_d3)
        model_path = resolve_model(model)
        from ase.calculators.singlepoint import SinglePointCalculator
        from ase.io import read, write

        frames = read(input, index=index)
        if not isinstance(frames, list):
            frames = [frames]
        if not frames:
            raise ValueError("帧选择结果为空")

        output.parent.mkdir(parents=True, exist_ok=True)
        calculator = build_calculator(model_path, use_d3)
        labeled = []
        rows = []
        started = time.time()
        stress_frames = 0
        for frame_index, atoms in enumerate(frames):
            if len(atoms) == 0:
                raise ValueError(f"第 {frame_index} 帧不含原子")
            atoms.calc = calculator
            energy = float(atoms.get_potential_energy())
            forces = np.asarray(atoms.get_forces(), dtype=float)
            if not np.isfinite(energy) or not np.isfinite(forces).all():
                raise ValueError(f"第 {frame_index} 帧产生非有限能量或原子力")

            result = {"energy": energy, "forces": forces}
            stress_values = None
            if stress:
                stress_values = np.asarray(
                    atoms.get_stress(voigt=True), dtype=float
                )
                if stress_values.shape != (6,) or not np.isfinite(stress_values).all():
                    raise ValueError(f"第 {frame_index} 帧应力结果无效")
                result["stress"] = stress_values
                stress_frames += 1

            labeled_atoms = atoms.copy()
            labeled_atoms.calc = SinglePointCalculator(labeled_atoms, **result)
            labeled.append(labeled_atoms)
            row = {
                "frame": frame_index,
                "formula": atoms.get_chemical_formula(),
                "atoms": len(atoms),
                **frame_metrics(energy, forces, len(atoms)),
            }
            if stress_values is not None:
                for name, value in zip(
                    ("xx", "yy", "zz", "yz", "xz", "xy"), stress_values
                ):
                    row[f"stress_{name}_eV_A3"] = float(value)
            rows.append(row)

        write(output, labeled, format="extxyz")
        with metrics_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        energy_per_atom = np.asarray(
            [row["energy_per_atom_eV"] for row in rows], dtype=float
        )
        summary = {
            "input": str(input),
            "index": index,
            "frames": len(rows),
            "model": str(model_path),
            "calculator": "DPA4 + PBE-D3(BJ)" if use_d3 else "DPA4",
            "stress_requested": stress,
            "stress_frames": stress_frames,
            "energy_per_atom_range_eV": [
                float(energy_per_atom.min()),
                float(energy_per_atom.max()),
            ],
            "maximum_atomic_force_eV_A": float(
                max(row["maximum_atomic_force_eV_A"] for row in rows)
            ),
            "elapsed_seconds": round(time.time() - started, 3),
            "output": str(output),
            "metrics": str(metrics_path),
        }
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
        )
    except Exception as exc:
        for path in (output, metrics_path, summary_path):
            path.unlink(missing_ok=True)
        typer.secho(
            f"错误: {type(exc).__name__}: {exc}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(2) from exc

    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))
