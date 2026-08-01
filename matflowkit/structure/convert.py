"""Convert a single CIF structure to Extended XYZ, POSCAR, or ABACUS STRU."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
import warnings
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import typer


TARGET_ALIASES = {
    "xyz": "extxyz",
    "extxyz": "extxyz",
    "poscar": "poscar",
    "vasp": "poscar",
    "stru": "stru",
    "abacus": "stru",
}


def _require_ase():
    try:
        from ase.io import read, write
    except ImportError as exc:
        raise RuntimeError(
            "缺少 ASE；请安装 MatFlowKit structure 依赖：pip install 'matflowkit[structure]'"
        ) from exc
    return read, write


def _require_dpdata():
    try:
        import dpdata
    except ImportError as exc:
        raise RuntimeError(
            "生成 STRU 需要 dpdata；请安装：pip install 'matflowkit[dpdata,structure]'"
        ) from exc
    return dpdata


def _require_pymatgen():
    try:
        from pymatgen.io.cif import CifParser
    except ImportError as exc:
        raise RuntimeError(
            "缺少 pymatgen；请安装 MatFlowKit structure 依赖："
            "pip install 'matflowkit[structure]'"
        ) from exc
    return CifParser


def read_single_cif(path: Path):
    """Read one fully occupied periodic CIF structure with pymatgen."""
    CifParser = _require_pymatgen()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        structures = CifParser(str(path), occupancy_tolerance=1.0).parse_structures(
            primitive=False
        )
    if len(structures) != 1:
        raise ValueError(f"第一版只支持单结构 CIF；检测到 {len(structures)} 个结构")
    structure = structures[0]
    if not structure.is_ordered:
        raise ValueError("第一版不支持部分占位或无序 CIF")
    from ase import Atoms

    atoms = Atoms(
        symbols=[site.specie.symbol for site in structure],
        scaled_positions=structure.frac_coords,
        cell=structure.lattice.matrix,
        pbc=True,
    )
    if len(atoms) < 1:
        raise ValueError("CIF 中没有原子")
    if not bool(np.all(atoms.pbc)):
        raise ValueError("CIF 没有完整的三维周期性")
    if not np.isfinite(atoms.cell.array).all() or atoms.get_volume() <= 0:
        raise ValueError("CIF 晶胞无效")
    if not np.isfinite(atoms.positions).all():
        raise ValueError("CIF 坐标包含 NaN/Inf")
    parser_warnings = list(dict.fromkeys(str(item.message) for item in caught))
    return atoms, parser_warnings


def _maximum_coordinate_deviation(
    source, restored, direct_order_tolerance: float = 1e-6
) -> float:
    """Return the largest species-aware periodic displacement in angstrom."""
    source_symbols = np.asarray(source.get_chemical_symbols())
    restored_symbols = np.asarray(restored.get_chemical_symbols())
    source_scaled = np.mod(source.get_scaled_positions(wrap=True), 1.0)
    restored_scaled = np.mod(restored.get_scaled_positions(wrap=True), 1.0)

    if np.array_equal(source_symbols, restored_symbols):
        delta = source_scaled - restored_scaled
        delta -= np.rint(delta)
        distances = np.linalg.norm(delta @ source.cell.array, axis=1)
        direct_maximum = float(distances.max()) if distances.size else 0.0
        if direct_maximum <= direct_order_tolerance:
            return direct_maximum

    maximum = 0.0
    for element in sorted(set(source_symbols)):
        left = source_scaled[source_symbols == element]
        right = restored_scaled[restored_symbols == element]
        if len(left) != len(right):
            raise ValueError("输出元素组成发生变化")

        # Formats may group or reorder atoms. Match equivalent atoms instead of
        # relying on their output order.
        from scipy.optimize import linear_sum_assignment

        delta = left[:, None, :] - right[None, :, :]
        delta -= np.rint(delta)
        cost = np.linalg.norm(delta @ source.cell.array, axis=2)
        rows, columns = linear_sum_assignment(cost)
        distances = cost[rows, columns]
        if distances.size:
            maximum = max(maximum, float(distances.max()))
    return maximum


def _minimum_distance(atoms) -> Optional[float]:
    if len(atoms) < 2:
        return None
    distances = atoms.get_all_distances(mic=True)
    values = distances[np.triu_indices(len(atoms), 1)]
    return float(values.min()) if values.size else None


def validate_roundtrip(source, restored) -> Dict[str, Any]:
    """Validate composition, lattice metric, fractional coordinates, and PBC."""
    if len(source) != len(restored):
        raise ValueError(f"输出原子数变化: {len(source)} -> {len(restored)}")
    if sorted(source.get_chemical_symbols()) != sorted(restored.get_chemical_symbols()):
        raise ValueError("输出元素组成发生变化")
    if not bool(np.all(restored.pbc)):
        raise ValueError("输出没有保留三维 PBC")
    source_metric = source.cell.array @ source.cell.array.T
    restored_metric = restored.cell.array @ restored.cell.array.T
    if not np.allclose(source_metric, restored_metric, rtol=1e-7, atol=1e-7):
        raise ValueError("输出晶格度量发生变化")
    if not np.isclose(source.get_volume(), restored.get_volume(), rtol=1e-7, atol=1e-7):
        raise ValueError("输出晶胞体积发生变化")
    coordinate_deviation = _maximum_coordinate_deviation(source, restored)
    if coordinate_deviation > 1e-6:
        raise ValueError("输出分数坐标或元素对应关系发生变化")
    return {
        "status": "passed",
        "natoms": len(restored),
        "formula": restored.get_chemical_formula(mode="hill"),
        "pbc": [bool(value) for value in restored.pbc],
        "cell_volume_A3": float(restored.get_volume()),
        "maximum_coordinate_deviation_A": coordinate_deviation,
        "minimum_distance_A": _minimum_distance(restored),
    }


def _default_output(input_path: Path, target: str) -> Path:
    suffix = {"extxyz": ".xyz", "poscar": ".vasp", "stru": ".STRU"}[target]
    return input_path.with_name(input_path.stem + suffix)


def _library_path(option: Optional[Path], environment: str, label: str) -> Path:
    value = option if option is not None else os.environ.get(environment)
    if value is None or str(value).strip() == "":
        raise ValueError(f"未配置{label}目录；请设置 {environment} 或使用对应命令行选项")
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"{label}目录不存在: {path}")
    return path


def _element_prefix(filename: str, element: str) -> bool:
    if not filename.lower().startswith(element.lower()):
        return False
    return len(filename) == len(element) or not filename[len(element)].isalpha()


def resolve_library_files(
    directory: Path,
    elements: Iterable[str],
    suffix: str,
    label: str,
) -> Dict[str, Path]:
    """Resolve one file per element, preferring an authoritative element.json."""
    elements = list(elements)
    mapping_file = directory / "element.json"
    resolved: Dict[str, Path] = {}
    if mapping_file.is_file():
        raw = json.loads(mapping_file.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"{mapping_file} 必须是元素到文件名的 JSON 对象")
        for element in elements:
            filename = raw.get(element)
            if not isinstance(filename, str) or not filename.strip():
                raise ValueError(f"{mapping_file} 缺少元素 {element} 的{label}映射")
            candidate = (directory / filename).resolve()
            if not candidate.is_file():
                raise ValueError(f"{element} 的{label}文件不存在: {candidate}")
            resolved[element] = candidate
        return resolved

    candidates = [
        path.resolve()
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() == suffix.lower()
    ]
    for element in elements:
        matches = [path for path in candidates if _element_prefix(path.name, element)]
        if not matches:
            raise ValueError(f"{directory} 中找不到元素 {element} 的{label}文件")
        if len(matches) > 1:
            names = ", ".join(sorted(path.name for path in matches))
            raise ValueError(f"元素 {element} 匹配到多个{label}文件，请用 element.json 明确指定: {names}")
        resolved[element] = matches[0]
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _recommended_ecutwfc(
    directory: Path,
    elements: Iterable[str],
    orbital_files: Dict[str, Path],
    requested: Optional[float],
) -> float:
    """Resolve a documented energy cutoff without inventing a default."""
    if requested is not None:
        if not np.isfinite(requested) or requested <= 0:
            raise ValueError("--ecutwfc 必须是正数")
        return float(requested)

    values: Dict[str, List[float]] = {element: [] for element in elements}
    recommendation = directory / "ecutwfc.json"
    if recommendation.is_file():
        raw = json.loads(recommendation.read_text(encoding="utf-8"))
        for element in elements:
            value = raw.get(element) if isinstance(raw, dict) else None
            if isinstance(value, (int, float)) and np.isfinite(value) and value > 0:
                values[element].append(float(value))

    cutoff_pattern = re.compile(r"Energy\s+Cutoff\s*\(Ry\)\s+([0-9.eE+-]+)", re.I)
    for element, path in orbital_files.items():
        header = path.read_text(encoding="utf-8", errors="replace")[:4096]
        match = cutoff_pattern.search(header)
        if match:
            values[element].append(float(match.group(1)))

    missing = [element for element, candidates in values.items() if not candidates]
    if missing:
        raise ValueError(
            f"无法确定元素 {', '.join(missing)} 的 ecutwfc；请在赝势目录提供 "
            "ecutwfc.json，或使用 --ecutwfc 指定"
        )
    return max(value for candidates in values.values() for value in candidates)


def _write_single_point_input(
    path: Path,
    stru_name: str,
    basis: str,
    pseudo_dir: Path,
    orbital_dir: Optional[Path],
    ecutwfc: float,
    local_resources: bool,
) -> None:
    pseudo_value = "." if local_resources else str(pseudo_dir)
    orbital_value = "." if local_resources else str(orbital_dir)
    resource_paths = [pseudo_value]
    if basis == "lcao":
        resource_paths.append(orbital_value)
    if any(any(char.isspace() for char in value) for value in resource_paths):
        raise ValueError("ABACUS 资源库路径不能包含空白字符")
    lines = [
        "INPUT_PARAMETERS",
        "# Review k-points, spin, and convergence before production calculations.",
        "calculation  scf",
        f"basis_type  {basis}",
        f"stru_file   {stru_name}",
        f"pseudo_dir  {pseudo_value}",
    ]
    if basis == "lcao":
        lines.extend(
            [
                f"orbital_dir {orbital_value}",
                f"ecutwfc     {ecutwfc:g}",
                "scf_thr      1e-7",
                "gamma_only   1",
            ]
        )
    else:
        lines.extend(
            [
                f"ecutwfc     {ecutwfc:g}",
                "scf_thr      1e-9",
                "kspacing     0.2  # Review k-point convergence.",
            ]
        )
    if any(len(line) > 150 for line in lines):
        raise ValueError("资源库路径过长，生成的 INPUT 行超过 ABACUS 的 150 字符限制")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ase_from_dpdata(system):
    from ase import Atoms

    names = system.data["atom_names"]
    symbols = [names[int(index)] for index in system.data["atom_types"]]
    return Atoms(
        symbols=symbols,
        positions=system.data["coords"][0],
        cell=system.data["cells"][0],
        pbc=True,
    )


def _preflight_copy_targets(output_dir: Path, files: Iterable[Path]) -> None:
    seen: Dict[str, Path] = {}
    for source in files:
        previous = seen.get(source.name)
        if previous is not None and previous != source:
            raise ValueError(f"两个资源文件使用同一文件名: {source.name}")
        seen[source.name] = source
        destination = output_dir / source.name
        if destination.exists() or destination.is_symlink():
            try:
                same = destination.resolve() == source.resolve()
            except OSError:
                same = False
            if not same:
                raise ValueError(f"资源文件目标已存在且来源不同: {destination}")


def _copy_resource_files(output_dir: Path, files: Iterable[Path]) -> List[Path]:
    created: List[Path] = []
    for source in files:
        destination = output_dir / source.name
        if destination.exists() or destination.is_symlink():
            continue
        shutil.copy2(source, destination)
        created.append(destination)
    return created


def convert(
    input: Path = typer.Argument(..., help="单结构 CIF 文件"),
    target: str = typer.Option("xyz", "--to", help="目标格式: xyz, poscar, stru"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出文件"),
    basis: str = typer.Option("pw", help="STRU 基组: pw 或 lcao"),
    pp_dir: Optional[Path] = typer.Option(None, help="赝势目录；默认读取 ABACUS_PP_PATH"),
    orb_dir: Optional[Path] = typer.Option(None, help="轨道目录；默认读取 ABACUS_ORB_PATH"),
    copy_files: bool = typer.Option(False, "--copy-files", help="将赝势和轨道复制到输出目录"),
    ecutwfc: Optional[float] = typer.Option(None, help="INPUT 截断能/Ry；默认读取资源库推荐值"),
    report_json: bool = typer.Option(False, "--json", help="输出完整 JSON 校验记录"),
) -> None:
    """将单结构 CIF 转为 Extended XYZ、POSCAR 或可用的 ABACUS STRU。

    XYZ 始终写为保留晶胞和 PBC 的 Extended XYZ。STRU 默认从
    ABACUS_PP_PATH 查找赝势；basis=lcao 时还会从 ABACUS_ORB_PATH 查找轨道。
    转为 STRU 时同时生成单点 SCF 的 INPUT。输出已存在、CIF 部分占位、
    资源缺失或回读验证失败时拒绝转换。
    """
    normalized_target = TARGET_ALIASES.get(target.strip().lower())
    if normalized_target is None:
        typer.secho(f"错误: 不支持的目标格式: {target}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    normalized_basis = basis.strip().lower()
    if normalized_basis not in {"pw", "lcao"}:
        typer.secho("错误: --basis 只能是 pw 或 lcao", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    input = input.expanduser()
    if not input.is_file():
        typer.secho(f"错误: CIF 不存在: {input}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    output = (
        output.expanduser()
        if output is not None
        else _default_output(input, normalized_target)
    )
    if output.exists() or output.is_symlink():
        typer.secho(f"错误: 输出已存在: {output}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    input_file = output.parent / "INPUT" if normalized_target == "stru" else None
    if input_file is not None and (input_file.exists() or input_file.is_symlink()):
        typer.secho(f"错误: INPUT 已存在: {input_file}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)

    temporary: Optional[Path] = None
    temporary_input: Optional[Path] = None
    created_input = False
    created_resources: List[Path] = []
    try:
        atoms, parser_warnings = read_single_cif(input)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.mfk-{uuid.uuid4().hex}.tmp")
        _, write = _require_ase()
        pseudo_files: Dict[str, Path] = {}
        orbital_files: Dict[str, Path] = {}

        if normalized_target == "extxyz":
            write(str(temporary), atoms, format="extxyz")
            read, _ = _require_ase()
            restored = read(str(temporary), format="extxyz")
        elif normalized_target == "poscar":
            write(str(temporary), atoms, format="vasp", direct=True, vasp5=True)
            read, _ = _require_ase()
            restored = read(str(temporary), format="vasp")
        else:
            dpdata = _require_dpdata()
            elements = list(dict.fromkeys(atoms.get_chemical_symbols()))
            pseudo_path = _library_path(pp_dir, "ABACUS_PP_PATH", "赝势")
            pseudo_files = resolve_library_files(pseudo_path, elements, ".upf", "赝势")
            if normalized_basis == "lcao":
                orbital_path = _library_path(orb_dir, "ABACUS_ORB_PATH", "轨道")
                orbital_files = resolve_library_files(orbital_path, elements, ".orb", "轨道")
            resources = list(pseudo_files.values()) + list(orbital_files.values())
            if copy_files:
                _preflight_copy_targets(output.parent, resources)
            system = dpdata.System(atoms, fmt="ase/structure")
            from ase.data import atomic_masses, atomic_numbers

            kwargs: Dict[str, Any] = {
                "pp_file": {element: path.name for element, path in pseudo_files.items()},
                "mass": [
                    float(atomic_masses[atomic_numbers[element]])
                    for element in system.data["atom_names"]
                ],
            }
            if orbital_files:
                kwargs["numerical_orbital"] = {
                    element: path.name for element, path in orbital_files.items()
                }
            system.to("abacus/stru", str(temporary), frame_idx=0, **kwargs)
            restored = _ase_from_dpdata(dpdata.System(str(temporary), fmt="abacus/stru"))

            resolved_ecutwfc = _recommended_ecutwfc(
                pseudo_path, elements, orbital_files, ecutwfc
            )
            temporary_input = input_file.with_name(
                f".{input_file.name}.mfk-{uuid.uuid4().hex}.tmp"
            )
            _write_single_point_input(
                temporary_input,
                output.name,
                normalized_basis,
                pseudo_path,
                orbital_path if normalized_basis == "lcao" else None,
                resolved_ecutwfc,
                copy_files,
            )

        validation = validate_roundtrip(atoms, restored)
        if normalized_target == "stru" and copy_files:
            created_resources = _copy_resource_files(
                output.parent, list(pseudo_files.values()) + list(orbital_files.values())
            )
        if temporary_input is not None:
            temporary_input.replace(input_file)
            temporary_input = None
            created_input = True
        temporary.replace(output)
        temporary = None
    except Exception as exc:
        if temporary is not None and temporary.exists():
            temporary.unlink()
        if temporary_input is not None and temporary_input.exists():
            temporary_input.unlink()
        if created_input and input_file is not None and input_file.exists():
            input_file.unlink()
        for resource in created_resources:
            if resource.exists() or resource.is_symlink():
                resource.unlink()
        typer.secho(f"错误: {type(exc).__name__}: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc

    report: Dict[str, Any] = {
        "input": str(input.resolve()),
        "output": str(output.resolve()),
        "format": {"extxyz": "extended_xyz", "poscar": "vasp_poscar", "stru": "abacus_stru"}[
            normalized_target
        ],
        "validation": validation,
        "warnings": parser_warnings,
    }
    if normalized_target == "stru":
        report["basis"] = normalized_basis
        report["input_file"] = str(input_file.resolve())
        report["ecutwfc_Ry"] = resolved_ecutwfc
        report["resource_mode"] = "copy" if copy_files else "library"
        report["pseudopotentials"] = {
            element: {"file": path.name, "sha256": _sha256(path)}
            for element, path in pseudo_files.items()
        }
        report["orbitals"] = {
            element: {"file": path.name, "sha256": _sha256(path)}
            for element, path in orbital_files.items()
        }
    if report_json:
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
        return

    typer.echo(f"转换完成: {report['output']}")
    typer.echo(
        f"结构: {validation['formula']}, {validation['natoms']} atoms | "
        f"校验: passed | 最大坐标偏差: "
        f"{validation['maximum_coordinate_deviation_A']:.3g} Å"
    )
    if normalized_target == "stru":
        typer.echo(
            f"STRU: {normalized_basis.upper()} | 赝势: {len(pseudo_files)} | "
            f"轨道: {len(orbital_files)} | ecutwfc: {resolved_ecutwfc:g} Ry"
        )
        typer.echo(f"INPUT: {input_file.resolve()} | 资源: {report['resource_mode']}")
    if parser_warnings:
        typer.echo(f"解析提示: {len(parser_warnings)} 条（使用 --json 查看详情）")
