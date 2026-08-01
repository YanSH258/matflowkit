"""Convert periodic CIF, POSCAR, and Extended XYZ structures."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
import warnings
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import numpy as np
import typer


TARGET_ALIASES = {
    "cif": "cif",
    "xyz": "extxyz",
    "extxyz": "extxyz",
    "poscar": "poscar",
    "vasp": "poscar",
    "stru": "stru",
    "abacus": "stru",
}

SOURCE_ALIASES = {
    "cif": "cif",
    "xyz": "extxyz",
    "extxyz": "extxyz",
    "poscar": "poscar",
    "vasp": "poscar",
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
        raise ValueError(f"只支持单结构输入；CIF 中检测到 {len(structures)} 个结构")
    structure = structures[0]
    if not structure.is_ordered:
        raise ValueError("不支持部分占位或无序 CIF")
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


def _validate_input_atoms(atoms, source_format: str) -> None:
    if len(atoms) < 1:
        raise ValueError("输入结构中没有原子")
    if not bool(np.all(atoms.pbc)):
        if source_format == "extxyz":
            raise ValueError("XYZ 缺少完整的 Lattice/pbc；周期结构转换需要 Extended XYZ")
        raise ValueError("输入结构没有完整的三维 PBC")
    if not np.isfinite(atoms.cell.array).all() or atoms.get_volume() <= 0:
        raise ValueError("输入结构的晶胞无效")
    if not np.isfinite(atoms.positions).all():
        raise ValueError("输入结构的坐标包含 NaN/Inf")


def _detect_source_format(path: Path, requested: Optional[str]) -> str:
    if requested is not None:
        normalized = SOURCE_ALIASES.get(requested.strip().lower())
        if normalized is None:
            raise ValueError(f"不支持的输入格式: {requested}")
        return normalized
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix == ".cif":
        return "cif"
    if name in {"poscar", "contcar"} or suffix in {".vasp", ".poscar"}:
        return "poscar"
    if suffix in {".xyz", ".extxyz"}:
        return "extxyz"
    raise ValueError("无法根据文件名识别输入格式；请使用 --from cif|poscar|extxyz")


def read_single_structure(path: Path, requested_format: Optional[str] = None):
    """Read and validate one periodic CIF, POSCAR, or Extended XYZ structure."""
    source_format = _detect_source_format(path, requested_format)
    if source_format == "cif":
        atoms, parser_warnings = read_single_cif(path)
    else:
        read, _ = _require_ase()
        ase_format = "vasp" if source_format == "poscar" else "extxyz"
        frames = read(str(path), format=ase_format, index=":")
        if not isinstance(frames, list):
            frames = [frames]
        if len(frames) != 1:
            raise ValueError(
                f"只支持单结构输入；{source_format} 中检测到 {len(frames)} 帧"
            )
        atoms = frames[0]
        parser_warnings = []
    _validate_input_atoms(atoms, source_format)
    return atoms, parser_warnings, source_format


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
    suffix = {"cif": ".cif", "extxyz": ".xyz", "poscar": ".vasp", "stru": ".STRU"}[
        target
    ]
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


def convert(
    input: Path = typer.Argument(..., help="单结构 CIF、POSCAR 或 Extended XYZ 文件"),
    target: str = typer.Option("xyz", "--to", help="目标格式: cif, xyz, poscar, stru"),
    source_format: Optional[str] = typer.Option(
        None, "--from", help="输入格式；默认根据文件名识别: cif, poscar, extxyz"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出文件"),
    basis: str = typer.Option("pw", help="STRU 基组: pw 或 lcao"),
    pp_dir: Optional[Path] = typer.Option(None, help="赝势目录；默认读取 ABACUS_PP_PATH"),
    orb_dir: Optional[Path] = typer.Option(None, help="轨道目录；默认读取 ABACUS_ORB_PATH"),
    report_json: bool = typer.Option(False, "--json", help="输出完整 JSON 校验记录"),
) -> None:
    """转换单个周期结构，支持 CIF、POSCAR、Extended XYZ 和 ABACUS STRU 输出。

    输入支持 CIF、POSCAR 和带 Lattice/pbc 的 Extended XYZ。XYZ 输出始终是
    Extended XYZ。STRU 默认从
    ABACUS_PP_PATH 查找赝势；basis=lcao 时还会从 ABACUS_ORB_PATH 查找轨道。
    赝势和轨道的绝对路径直接写入 STRU。输出已存在、CIF 部分占位、
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
        typer.secho(f"错误: 输入结构不存在: {input}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    output = (
        output.expanduser()
        if output is not None
        else _default_output(input, normalized_target)
    )
    if output.exists() or output.is_symlink():
        typer.secho(f"错误: 输出已存在: {output}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    temporary: Optional[Path] = None
    try:
        atoms, parser_warnings, normalized_source = read_single_structure(
            input, source_format
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.mfk-{uuid.uuid4().hex}.tmp")
        _, write = _require_ase()
        pseudo_files: Dict[str, Path] = {}
        orbital_files: Dict[str, Path] = {}

        if normalized_target == "cif":
            write(str(temporary), atoms, format="cif")
            restored, output_warnings = read_single_cif(temporary)
            parser_warnings.extend(
                warning for warning in output_warnings if warning not in parser_warnings
            )
        elif normalized_target == "extxyz":
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
            system = dpdata.System(atoms, fmt="ase/structure")
            from ase.data import atomic_masses, atomic_numbers

            resource_references = {
                element: str(path.resolve())
                for element, path in pseudo_files.items()
            }
            orbital_references = {
                element: str(path.resolve())
                for element, path in orbital_files.items()
            }
            if any(
                any(character.isspace() for character in reference)
                for reference in list(resource_references.values())
                + list(orbital_references.values())
            ):
                raise ValueError("写入 STRU 的赝势或轨道路径不能包含空白字符")
            kwargs: Dict[str, Any] = {
                "pp_file": resource_references,
                "mass": [
                    float(atomic_masses[atomic_numbers[element]])
                    for element in system.data["atom_names"]
                ],
            }
            if orbital_files:
                kwargs["numerical_orbital"] = orbital_references
            system.to("abacus/stru", str(temporary), frame_idx=0, **kwargs)
            restored = _ase_from_dpdata(dpdata.System(str(temporary), fmt="abacus/stru"))

        validation = validate_roundtrip(atoms, restored)
        temporary.replace(output)
        temporary = None
    except Exception as exc:
        if temporary is not None and temporary.exists():
            temporary.unlink()
        typer.secho(f"错误: {type(exc).__name__}: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc

    report: Dict[str, Any] = {
        "input": str(input.resolve()),
        "input_format": normalized_source,
        "output": str(output.resolve()),
        "format": {
            "cif": "cif",
            "extxyz": "extended_xyz",
            "poscar": "vasp_poscar",
            "stru": "abacus_stru",
        }[normalized_target],
        "validation": validation,
        "warnings": parser_warnings,
    }
    if normalized_target == "stru":
        report["basis"] = normalized_basis
        report["resource_mode"] = "absolute_path"
        report["pseudopotentials"] = {
            element: {
                "file": resource_references[element],
                "source": str(path.resolve()),
                "sha256": _sha256(path),
            }
            for element, path in pseudo_files.items()
        }
        report["orbitals"] = {
            element: {
                "file": orbital_references[element],
                "source": str(path.resolve()),
                "sha256": _sha256(path),
            }
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
            f"轨道: {len(orbital_files)} | 资源: 绝对路径"
        )
    if parser_warnings:
        typer.echo(f"解析提示: {len(parser_warnings)} 条（使用 --json 查看详情）")
