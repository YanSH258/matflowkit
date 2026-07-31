"""mfk dpa4 relax: optimize an atomistic structure with DPA4."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import typer

from matflowkit.dpa4.common import (
    build_calculator,
    maximum_force,
    read_fixed_indices,
    require_dependencies,
    resolve_model,
)


OPTIMIZER_NAMES = ("bfgs", "lbfgs", "fire")


def relaxation_paths(input: Path, output: Path | None) -> tuple[Path, Path, Path, Path]:
    """Return the structure, optimizer log, trajectory, and status paths."""
    resolved_output = (
        output.expanduser().resolve()
        if output is not None
        else input.with_name(f"{input.stem}_dpa4_relaxed.extxyz")
    )
    return (
        resolved_output,
        resolved_output.with_name(f"{resolved_output.stem}.log"),
        resolved_output.with_name(f"{resolved_output.stem}_trajectory.extxyz"),
        resolved_output.with_name(f"{resolved_output.stem}_status.json"),
    )


def run_relaxation(
    input: Path,
    output: Path | None = None,
    model: Path | None = None,
    fmax: float = 0.05,
    steps: int = 300,
    optimizer: str = "bfgs",
    fixed_cell: bool = True,
    fixed_indices_file: Path | None = None,
    use_d3: bool = True,
) -> tuple[dict, bool]:
    """Run one DPA4 optimization and return its status and pass flag."""
    input = input.expanduser().resolve()
    if not input.is_file():
        raise FileNotFoundError(f"输入结构不存在: {input}")
    if optimizer not in OPTIMIZER_NAMES:
        raise ValueError(f"optimizer 必须为 {', '.join(OPTIMIZER_NAMES)}")
    output, log_path, trajectory_path, status_path = relaxation_paths(input, output)
    output.parent.mkdir(parents=True, exist_ok=True)
    existing = [
        path
        for path in (output, log_path, trajectory_path, status_path)
        if path.exists()
    ]
    if existing:
        raise FileExistsError(
            "以下输出已存在: " + ", ".join(str(path) for path in existing)
        )

    require_dependencies(use_d3)
    model_path = resolve_model(model)
    from ase.constraints import FixAtoms
    from ase.filters import UnitCellFilter
    from ase.io import read, write
    from ase.optimize import BFGS, FIRE, LBFGS

    optimizers = {"bfgs": BFGS, "lbfgs": LBFGS, "fire": FIRE}
    atoms = read(input)
    if len(atoms) == 0:
        raise ValueError("输入结构不含原子")
    if not fixed_cell and not atoms.pbc.all():
        raise ValueError("变胞优化要求三个方向均为周期性边界")
    fixed_indices = read_fixed_indices(fixed_indices_file, len(atoms))
    if fixed_indices:
        atoms.set_constraint(FixAtoms(indices=fixed_indices))
    initial_symbols = atoms.get_chemical_symbols()
    initial_cell = atoms.cell.array.copy()
    initial_volume = float(atoms.get_volume()) if atoms.cell.rank == 3 else None

    atoms.calc = build_calculator(model_path, use_d3)
    started = time.time()
    initial_energy = float(atoms.get_potential_energy())
    initial_fmax = maximum_force(atoms.get_forces(apply_constraint=True))

    target = atoms if fixed_cell else UnitCellFilter(atoms)
    write(trajectory_path, atoms, format="extxyz")
    engine = optimizers[optimizer](target, logfile=str(log_path))
    engine.attach(
        lambda: write(
            trajectory_path,
            atoms,
            format="extxyz",
            append=True,
        ),
        interval=1,
    )
    converged = bool(engine.run(fmax=fmax, steps=steps))

    final_energy = float(atoms.get_potential_energy())
    final_atomic_fmax = maximum_force(atoms.get_forces(apply_constraint=True))
    optimizer_fmax = maximum_force(target.get_forces())
    final_volume = float(atoms.get_volume()) if atoms.cell.rank == 3 else None
    if atoms.get_chemical_symbols() != initial_symbols:
        raise RuntimeError("优化过程中元素种类或原子顺序发生变化")
    if not np.isfinite(atoms.positions).all():
        raise RuntimeError("最终结构包含非有限坐标")
    if fixed_cell and not np.allclose(atoms.cell.array, initial_cell):
        raise RuntimeError("固定晶胞优化意外改变了晶胞")

    write(output, atoms)
    passed = converged and optimizer_fmax <= fmax + 1.0e-8
    status = {
        "status": "PASS" if passed else "NOT_CONVERGED",
        "converged": converged,
        "input": str(input),
        "output": str(output),
        "model": str(model_path),
        "calculator": "DPA4 + PBE-D3(BJ)" if use_d3 else "DPA4",
        "formula": atoms.get_chemical_formula(),
        "atoms": len(atoms),
        "fixed_atoms": len(fixed_indices),
        "fixed_cell": fixed_cell,
        "optimizer": optimizer,
        "steps_completed": int(engine.nsteps),
        "steps_limit": steps,
        "fmax_target_eV_A": fmax,
        "initial_fmax_eV_A": initial_fmax,
        "final_atomic_fmax_eV_A": final_atomic_fmax,
        "final_optimizer_fmax_eV_A": optimizer_fmax,
        "initial_energy_eV": initial_energy,
        "final_energy_eV": final_energy,
        "energy_change_eV": final_energy - initial_energy,
        "initial_volume_A3": initial_volume,
        "final_volume_A3": final_volume,
        "elapsed_seconds": round(time.time() - started, 3),
        "log": str(log_path),
        "trajectory": str(trajectory_path),
    }
    status_path.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n"
    )
    return status, passed


def relax(
    input: Path = typer.Argument(..., help="ASE 可读取的输入结构"),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="优化后结构；默认 INPUT_dpa4_relaxed.extxyz",
    ),
    model: Path | None = typer.Option(
        None,
        "--model",
        envvar="DPA4_MODEL",
        help="DPA4 model.pt；也可设置 DPA4_MODEL",
    ),
    fmax: float = typer.Option(
        0.05,
        min=1.0e-6,
        help="收敛力阈值，单位 eV/angstrom",
    ),
    steps: int = typer.Option(300, min=1, help="最大优化步数"),
    optimizer: str = typer.Option(
        "bfgs",
        help="优化器: bfgs、lbfgs 或 fire",
    ),
    fixed_cell: bool = typer.Option(
        True,
        "--fixed-cell/--relax-cell",
        help="默认只优化原子；--relax-cell 同时优化晶胞",
    ),
    fixed_indices_file: Path | None = typer.Option(
        None,
        "--fix-indices-file",
        help="固定原子的文本文件，使用从 1 开始的原子编号",
    ),
    use_d3: bool = typer.Option(
        True,
        "--d3/--no-d3",
        help="是否叠加 PBE-D3(BJ) 色散修正",
    ),
) -> None:
    """使用 DPA4 对结构进行固定晶胞或变胞优化。

    默认使用固定晶胞、BFGS、0.05 eV/angstrom，并在输出结构旁生成优化日志、
    extxyz 轨迹和 JSON 状态文件。DPA4 模型按 ``--model``、环境变量
    ``DPA4_MODEL``、``~/dpa4/Neo-MPtrj/model.pt`` 的顺序查找。
    """
    try:
        status, passed = run_relaxation(
            input=input,
            output=output,
            model=model,
            fmax=fmax,
            steps=steps,
            optimizer=optimizer,
            fixed_cell=fixed_cell,
            fixed_indices_file=fixed_indices_file,
            use_d3=use_d3,
        )
    except Exception as exc:
        typer.secho(
            f"错误: {type(exc).__name__}: {exc}",
            err=True,
            fg=typer.colors.RED,
        )
        exit_code = 1 if isinstance(exc, (FileNotFoundError, FileExistsError)) else 2
        raise typer.Exit(exit_code) from exc

    typer.echo(json.dumps(status, ensure_ascii=False, indent=2))
    if not passed:
        raise typer.Exit(2)
