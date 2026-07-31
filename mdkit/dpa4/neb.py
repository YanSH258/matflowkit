"""mfk dpa4 neb: run an ASE NEB or CI-NEB path with DPA4."""

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
    read_fixed_indices,
    require_dependencies,
    resolve_model,
)


def _save_images(path: Path, images) -> None:
    from ase.io import write

    for index, image in enumerate(images):
        snapshot = image.copy()
        snapshot.calc = None
        write(path, snapshot, format="extxyz", append=index > 0)


def _evaluate_images(images, model: Path, use_d3: bool) -> tuple[np.ndarray, np.ndarray]:
    calculator = build_calculator(model, use_d3)
    energies = []
    force_maxima = []
    for image in images:
        probe = image.copy()
        probe.calc = calculator
        energies.append(float(probe.get_potential_energy()))
        force_maxima.append(maximum_force(probe.get_forces()))
    return np.asarray(energies), np.asarray(force_maxima)


def _attach_shared_calculator(images, model: Path, use_d3: bool) -> None:
    calculator = build_calculator(model, use_d3)
    for image in images:
        image.calc = calculator


def _validate_endpoints(initial, final) -> None:
    if len(initial) != len(final):
        raise ValueError(
            f"初态和末态原子数不同: {len(initial)} 和 {len(final)}"
        )
    if initial.get_chemical_symbols() != final.get_chemical_symbols():
        raise ValueError("初态和末态的元素顺序不同")
    if not np.array_equal(initial.pbc, final.pbc):
        raise ValueError("初态和末态的周期性边界不同")
    if not np.allclose(initial.cell.array, final.cell.array, atol=1.0e-6):
        raise ValueError("初态和末态的晶胞不同")
    if not np.isfinite(initial.positions).all() or not np.isfinite(
        final.positions
    ).all():
        raise ValueError("端点结构包含非有限坐标")


def neb(
    initial: Path = typer.Argument(..., help="已优化的初态结构"),
    final: Path = typer.Argument(..., help="已优化的末态结构"),
    output_dir: Path = typer.Option(
        Path("dpa4_neb"),
        "--output-dir",
        "-o",
        help="NEB 输出目录，必须为空或不存在",
    ),
    model: Path | None = typer.Option(
        None,
        "--model",
        envvar="DPA4_MODEL",
        help="DPA4 model.pt；也可设置 DPA4_MODEL",
    ),
    intermediate_images: int = typer.Option(
        5,
        "--images",
        min=1,
        help="初态和末态之间的中间图像数",
    ),
    fixed_indices_file: Path | None = typer.Option(
        None,
        "--fix-indices-file",
        help="每个图像中固定的原子编号，使用从 1 开始的编号",
    ),
    neb_fmax: float = typer.Option(
        0.10,
        min=1.0e-6,
        help="普通 NEB 收敛阈值，单位 eV/angstrom",
    ),
    ci_fmax: float = typer.Option(
        0.05,
        min=1.0e-6,
        help="CI-NEB 收敛阈值，单位 eV/angstrom",
    ),
    neb_steps: int = typer.Option(600, min=1, help="普通 NEB 最大步数"),
    ci_steps: int = typer.Option(800, min=1, help="CI-NEB 最大步数"),
    climb: bool = typer.Option(
        True,
        "--climb/--no-climb",
        help="普通 NEB 收敛后是否继续执行 CI-NEB",
    ),
    use_d3: bool = typer.Option(
        True,
        "--d3/--no-d3",
        help="是否叠加 PBE-D3(BJ) 色散修正",
    ),
) -> None:
    """使用 DPA4 执行 IDPP 插值、普通 NEB 和可选 CI-NEB。

    初态和末态必须具有相同原子数、元素顺序、晶胞和周期性。命令首先使用
    IDPP 构建路径，再用 FIRE 优化普通 NEB；普通 NEB 收敛且最高能图像位于
    路径内部时，默认继续执行 CI-NEB。结果属于 DPA4 预测的最低能量路径，
    不等同于第一性原理 NEB。
    """
    initial = initial.expanduser().resolve()
    final = final.expanduser().resolve()
    for label, path in (("初态", initial), ("末态", final)):
        if not path.is_file():
            typer.secho(
                f"错误: {label}结构不存在: {path}",
                err=True,
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)
    output_dir = output_dir.expanduser().resolve()
    if output_dir.exists():
        if output_dir.is_file() or any(output_dir.iterdir()):
            typer.secho(
                f"错误: 输出路径已存在且非空: {output_dir}",
                err=True,
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)
    else:
        output_dir.mkdir(parents=True)

    try:
        require_dependencies(use_d3)
        model_path = resolve_model(model)
        from ase.constraints import FixAtoms
        from ase.io import read, write
        from ase.mep import NEB
        from ase.optimize import FIRE

        initial_atoms = read(initial)
        final_atoms = read(final)
        _validate_endpoints(initial_atoms, final_atoms)
        fixed_indices = read_fixed_indices(
            fixed_indices_file, len(initial_atoms)
        )

        images = [initial_atoms.copy()]
        images.extend(
            initial_atoms.copy() for _ in range(intermediate_images)
        )
        images.append(final_atoms.copy())
        if fixed_indices:
            for image in images:
                image.set_constraint(FixAtoms(indices=fixed_indices))

        interpolator = NEB(images, climb=False, method="aseneb")
        interpolator.interpolate(method="idpp", mic=bool(initial_atoms.pbc.any()))
        _save_images(output_dir / "interpolated_images.extxyz", images)

        started = time.time()
        _attach_shared_calculator(images, model_path, use_d3)
        path = NEB(
            images,
            climb=False,
            method="aseneb",
            allow_shared_calculator=True,
        )
        stage1 = FIRE(
            path,
            logfile=str(output_dir / "neb_fire.log"),
            dt=0.05,
            maxstep=0.05,
        )
        stage1_converged = bool(
            stage1.run(fmax=neb_fmax, steps=neb_steps)
        )
        stage1_force = maximum_force(path.get_forces())
        _save_images(output_dir / "neb_images.extxyz", images)

        energies, raw_force_maxima = _evaluate_images(
            images, model_path, use_d3
        )
        relative = energies - energies[0]
        highest_image = int(np.argmax(relative))
        internal_maximum = 0 < highest_image < len(images) - 1

        stage2_attempted = bool(stage1_converged and climb and internal_maximum)
        stage2_converged = False
        stage2_steps_completed = 0
        final_neb_force = stage1_force
        if stage2_attempted:
            _attach_shared_calculator(images, model_path, use_d3)
            path = NEB(
                images,
                climb=True,
                method="aseneb",
                allow_shared_calculator=True,
            )
            stage2 = FIRE(
                path,
                logfile=str(output_dir / "ci_neb_fire.log"),
                dt=0.03,
                maxstep=0.03,
            )
            stage2_converged = bool(
                stage2.run(fmax=ci_fmax, steps=ci_steps)
            )
            stage2_steps_completed = int(stage2.nsteps)
            final_neb_force = maximum_force(path.get_forces())
            _save_images(output_dir / "ci_neb_images.extxyz", images)
            energies, raw_force_maxima = _evaluate_images(
                images, model_path, use_d3
            )
            relative = energies - energies[0]
            highest_image = int(np.argmax(relative))

        rows = []
        for index, (energy, rel, raw_fmax) in enumerate(
            zip(energies, relative, raw_force_maxima)
        ):
            rows.append(
                {
                    "image": index,
                    "energy_eV": f"{energy:.12f}",
                    "relative_to_initial_eV": f"{rel:.12f}",
                    "raw_fmax_eV_A": f"{raw_fmax:.8f}",
                }
            )
        with (output_dir / "energy_profile.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

        ts_candidate = images[highest_image].copy()
        ts_candidate.calc = None
        write(
            output_dir / "highest_energy_image.extxyz",
            ts_candidate,
            format="extxyz",
        )

        if stage2_converged:
            status_name = "PASS_CI_NEB"
            passed = True
        elif stage1_converged and not climb:
            status_name = "PASS_NEB"
            passed = True
        elif stage1_converged and not internal_maximum:
            status_name = "PASS_NEB_ENDPOINT_MAXIMUM"
            passed = True
        elif stage1_converged:
            status_name = "INCOMPLETE_CI_NEB"
            passed = False
        else:
            status_name = "INCOMPLETE_NEB"
            passed = False

        forward_barrier = float(relative.max())
        reaction_energy = float(relative[-1])
        status = {
            "status": status_name,
            "initial": str(initial),
            "final": str(final),
            "output_dir": str(output_dir),
            "model": str(model_path),
            "calculator": "DPA4 + PBE-D3(BJ)" if use_d3 else "DPA4",
            "atoms_per_image": len(initial_atoms),
            "intermediate_images": intermediate_images,
            "total_images": len(images),
            "fixed_atoms": len(fixed_indices),
            "stage1_converged": stage1_converged,
            "stage1_steps": int(stage1.nsteps),
            "stage1_neb_fmax_eV_A": stage1_force,
            "stage2_attempted": stage2_attempted,
            "stage2_converged": stage2_converged,
            "stage2_steps": stage2_steps_completed,
            "final_neb_fmax_eV_A": final_neb_force,
            "highest_energy_image": highest_image,
            "forward_barrier_eV": forward_barrier,
            "reaction_energy_eV": reaction_energy,
            "reverse_barrier_eV": forward_barrier - reaction_energy,
            "elapsed_seconds": round(time.time() - started, 3),
            "method_scope": "DPA4 minimum-energy path; not a DFT NEB result",
        }
        (output_dir / "status.json").write_text(
            json.dumps(status, ensure_ascii=False, indent=2) + "\n"
        )
    except Exception as exc:
        typer.secho(
            f"错误: {type(exc).__name__}: {exc}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(2) from exc

    typer.echo(json.dumps(status, ensure_ascii=False, indent=2))
    if not passed:
        raise typer.Exit(2)
