"""Generate an auditable static report for a DeepMD NPY dataset."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional, Union

import numpy as np
import typer

from tcct.common.io import ensure_empty_output, write_csv, write_json
from tcct.deepmd.dataset import (
    DeepMDSystem, find_systems, load_array, read_system, reshape_frames, set_directories,
)
from tcct.dpdata.overlap import normalized_frame_hash
from tcct.report.html import render_deepmd_report
from tcct.report.schema import deepmd_dataset_schema


def _stats(values: Union[list[float], np.ndarray]) -> dict:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if array.size == 0:
        return {"count": 0, "min": None, "max": None, "mean": None, "std": None}
    return {
        "count": int(array.size), "min": float(array.min()), "max": float(array.max()),
        "mean": float(array.mean()), "std": float(array.std()),
    }


def _concat(chunks: list[np.ndarray]) -> np.ndarray:
    return np.concatenate(chunks) if chunks else np.array([], dtype=float)


def _symbols(system: DeepMDSystem) -> list[str]:
    if system.type_map is None:
        return [f"type_{int(value)}" for value in system.types]
    return [
        system.type_map[int(value)] if int(value) < len(system.type_map) else f"type_{int(value)}"
        for value in system.types
    ]


def _minimum_distances(
    symbols: list[str], coords: np.ndarray, box: np.ndarray, pbc: tuple[bool, bool, bool]
) -> tuple[Optional[float], dict[str, float]]:
    """Return exact MIC minima for one frame using ASE's distance matrix."""
    try:
        from ase import Atoms
    except ImportError as exc:
        raise RuntimeError(
            "最小距离审计需要 ASE；请运行 `pip install -e '.[structure]'`"
        ) from exc

    if len(symbols) < 2:
        return None, {}
    # Distances do not depend on atomic numbers; dummy H avoids rejecting type_N labels.
    atoms = Atoms(numbers=np.ones(len(symbols), dtype=int), positions=coords, cell=box, pbc=pbc)
    distances = atoms.get_all_distances(mic=True)
    indices_by_element = {
        element: np.flatnonzero(np.asarray(symbols) == element)
        for element in sorted(set(symbols))
    }
    elements = sorted(indices_by_element)
    pair_minima: dict[str, float] = {}
    for left_index, left in enumerate(elements):
        left_indices = indices_by_element[left]
        for right in elements[left_index:]:
            right_indices = indices_by_element[right]
            values = distances[np.ix_(left_indices, right_indices)]
            if left == right:
                values = values[np.triu_indices(len(left_indices), k=1)]
            finite = values[np.isfinite(values) & (values >= 0.0)]
            if finite.size:
                pair_minima[f"{left}-{right}"] = float(finite.min())
    overall = min(pair_minima.values()) if pair_minima else None
    return overall, pair_minima


def _warn(warnings: list[dict], code: str, message: str, system: Optional[str] = None) -> None:
    item = {"code": code, "message": message}
    if system is not None:
        item["system"] = system
    warnings.append(item)


def _require_matplotlib():
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("此命令需要 matplotlib；请运行 `pip install -e '.[plot]'`") from exc
    from tcct.common.plot_style import apply_plot_style
    apply_plot_style()
    return plt


def _plot_or_note(ax, values, bins: int, xlabel: str, color: str) -> None:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size:
        ax.hist(finite, bins=min(bins, max(1, int(np.sqrt(finite.size)))), color=color, alpha=0.85)
    else:
        ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center", va="center")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Count")


def _write_figures(output: Path, analysis: dict) -> None:
    plt = _require_matplotlib()
    from tcct.common.plot_style import COLORS, figure_size, save_figure

    figures = output / "figures"
    fig, ax = plt.subplots(figsize=figure_size("single", 0.72))
    _plot_or_note(ax, analysis["energy_per_atom"], 60, "Energy per atom (eV/atom)", COLORS["blue"])
    save_figure(fig, figures / "energy_per_atom_distribution.png")

    fig, axes = plt.subplots(1, 3, figsize=figure_size("double", 0.34))
    _plot_or_note(axes[0], analysis["force_components"], 60, "Force component (eV/Å)", COLORS["blue"])
    _plot_or_note(axes[1], analysis["force_magnitudes"], 60, "Atomic force magnitude (eV/Å)", COLORS["orange"])
    _plot_or_note(axes[2], analysis["frame_max_forces"], 60, "Maximum force per frame (eV/Å)", COLORS["green"])
    save_figure(fig, figures / "force_distribution.png")

    labels = sorted(analysis["composition_frames"])
    counts = [analysis["composition_frames"][label] for label in labels]
    fig, ax = plt.subplots(figsize=figure_size("single", max(0.65, 0.09 * len(labels) + 0.4)))
    if labels:
        ax.barh(labels, counts, color=COLORS["blue"])
        ax.set_xlabel("Frames")
        ax.set_ylabel("Composition")
    else:
        ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center", va="center")
    save_figure(fig, figures / "composition.png")


def analyze_dataset(
    root: Path,
    force_threshold: Optional[float],
    minimum_distance_threshold: Optional[float] = None,
    analyze_minimum_distance: bool = False,
    decimals: int = 6,
) -> tuple[dict, list[dict], list[dict], dict]:
    """Return schema report, systems rows, duplicate rows, and plotting arrays."""
    systems_paths = find_systems(root)
    if not systems_paths:
        raise ValueError(f"在 {root} 下未找到 DeepMD NPY 数据（需要 type.raw + set.*/）")

    result = deepmd_dataset_schema()
    warnings = result["warnings"]
    systems_rows: list[dict] = []
    energies: list[np.ndarray] = []
    energy_per_atom: list[np.ndarray] = []
    relative_by_composition: dict[str, list[np.ndarray]] = defaultdict(list)
    force_components: list[np.ndarray] = []
    force_magnitudes: list[np.ndarray] = []
    frame_max_forces: list[np.ndarray] = []
    system_force_max: dict[str, Optional[float]] = {}
    virials: list[np.ndarray] = []
    composition_systems: Counter = Counter()
    composition_frames: Counter = Counter()
    hashes: dict[str, list[str]] = defaultdict(list)
    all_elements: set[str] = set()
    total_frames = 0
    minimum_distances: list[float] = []
    minimum_distance_by_pair: dict[str, float] = {}
    minimum_distance_per_system: dict[str, Optional[float]] = {}
    frames_below_minimum_distance = 0

    for system_path in systems_paths:
        system = read_system(system_path)
        system_name = "." if system_path == root else str(system_path.relative_to(root))
        all_elements.update(system.elements)
        composition_systems[system.composition] += 1
        if system.type_map is None:
            _warn(warnings, "missing_type_map", f"{system_name}: 缺少 type_map.raw，元素以 type_N 表示", system_name)
        elif system.unmapped_type_ids:
            values = ", ".join(str(value) for value in system.unmapped_type_ids)
            _warn(warnings, "invalid_type_map", f"{system_name}: type_map.raw 未覆盖类型 {values}，以 type_N 表示", system_name)

        setdirs = set_directories(system)
        if not setdirs:
            raise ValueError(f"{system_name}: 未找到 set.* 目录")
        frame_count = 0
        label_set_counts = {name: 0 for name in ("energy", "force", "virial")}
        nonempty_sets = 0
        local_force_max: list[np.ndarray] = []
        local_minimum_distances: list[float] = []
        symbols = _symbols(system)
        for setdir in setdirs:
            coord_path, box_path = setdir / "coord.npy", setdir / "box.npy"
            if not coord_path.is_file() or not box_path.is_file():
                missing = [path.name for path in (coord_path, box_path) if not path.is_file()]
                raise ValueError(f"{setdir} 缺少必需文件: {', '.join(missing)}")
            coords_raw = load_array(coord_path)
            if coords_raw.size == 0:
                _warn(warnings, "empty_set", f"{system_name}/{setdir.name}: coord.npy 为空", system_name)
                continue
            if coords_raw.size % (system.natoms * 3):
                raise ValueError(f"{coord_path} 大小不能按 {system.natoms} 个原子重排")
            nframes = coords_raw.size // (system.natoms * 3)
            nonempty_sets += 1
            coords = reshape_frames(coords_raw, nframes, system.natoms * 3, str(coord_path)).reshape(nframes, system.natoms, 3)
            boxes = reshape_frames(load_array(box_path), nframes, 9, str(box_path)).reshape(nframes, 3, 3)
            frame_count += nframes

            arrays: dict[str, np.ndarray] = {}
            for name in ("energy", "force", "virial"):
                path = setdir / f"{name}.npy"
                if path.is_file():
                    arrays[name] = load_array(path)
                    label_set_counts[name] += 1
            for name, array in [("coord", coords), ("box", boxes), *arrays.items()]:
                if not np.all(np.isfinite(array)):
                    count = int(array.size - np.isfinite(array).sum())
                    _warn(warnings, "non_finite", f"{system_name}/{setdir.name}/{name}: {count} 个 NaN/Inf", system_name)

            if "energy" in arrays:
                energy = reshape_frames(arrays["energy"], nframes, 1, str(setdir / "energy.npy")).reshape(-1)
                energies.append(energy)
                per_atom = energy / system.natoms
                energy_per_atom.append(per_atom)
                relative_by_composition[system.composition].append(per_atom)
            if "force" in arrays:
                force = reshape_frames(arrays["force"], nframes, system.natoms * 3, str(setdir / "force.npy")).reshape(nframes, system.natoms, 3)
                magnitudes = np.linalg.norm(force, axis=2)
                maxima = np.max(magnitudes, axis=1)
                force_components.append(force.reshape(-1))
                force_magnitudes.append(magnitudes.reshape(-1))
                frame_max_forces.append(maxima)
                local_force_max.append(maxima)
            if "virial" in arrays:
                virial = reshape_frames(arrays["virial"], nframes, 9, str(setdir / "virial.npy"))
                virials.append(virial.reshape(-1))

            for index, (coord, box) in enumerate(zip(coords, boxes)):
                value = normalized_frame_hash(symbols, box, coord, system.pbc, decimals=decimals)
                hashes[value].append(f"{system_name}/{setdir.name}:{index}")
                frame_minimum, frame_pairs = (None, {})
                if analyze_minimum_distance:
                    frame_minimum, frame_pairs = _minimum_distances(
                        symbols, coord, box, system.pbc
                    )
                if frame_minimum is not None:
                    minimum_distances.append(frame_minimum)
                    local_minimum_distances.append(frame_minimum)
                    if (
                        minimum_distance_threshold is not None
                        and frame_minimum < minimum_distance_threshold
                    ):
                        frames_below_minimum_distance += 1
                for pair, distance in frame_pairs.items():
                    if (
                        pair not in minimum_distance_by_pair
                        or distance < minimum_distance_by_pair[pair]
                    ):
                        minimum_distance_by_pair[pair] = distance

        total_frames += frame_count
        composition_frames[system.composition] += frame_count
        labels_present = {
            name: nonempty_sets > 0 and count == nonempty_sets
            for name, count in label_set_counts.items()
        }
        for name, count in label_set_counts.items():
            if count < nonempty_sets:
                _warn(
                    warnings, f"missing_{name}",
                    f"{system_name}: {nonempty_sets - count}/{nonempty_sets} 个非空 set 缺少 {name}.npy",
                    system_name,
                )
        local_values = _concat(local_force_max)
        local_finite = local_values[np.isfinite(local_values)]
        system_force_max[system_name] = float(local_finite.max()) if local_finite.size else None
        minimum_distance_per_system[system_name] = (
            float(min(local_minimum_distances)) if local_minimum_distances else None
        )
        systems_rows.append({
            "system": system_name, "frames": frame_count, "natoms": system.natoms,
            "elements": " ".join(system.elements), "composition": system.composition,
            "has_energy": labels_present["energy"], "has_force": labels_present["force"],
            "has_virial": labels_present["virial"],
            "minimum_distance_A": minimum_distance_per_system[system_name],
        })

    relative: list[np.ndarray] = []
    for chunks in relative_by_composition.values():
        finite = _concat(chunks)
        finite = finite[np.isfinite(finite)]
        if finite.size:
            relative.append(finite - finite.min())
    duplicate_rows = []
    group_count = 0
    duplicate_frames = 0
    for frame_ids in hashes.values():
        if len(frame_ids) > 1:
            group_count += 1
            duplicate_frames += len(frame_ids) - 1
            for frame_id in frame_ids:
                duplicate_rows.append({"group_id": group_count, "frame_id": frame_id, "size": len(frame_ids)})
    if group_count:
        _warn(warnings, "exact_duplicate", f"发现 {group_count} 组 exact normalized duplicate，共 {duplicate_frames} 个冗余帧")

    result["dataset"].update({"path": str(root), "systems": len(systems_rows), "frames": total_frames, "elements": sorted(all_elements)})
    result["properties"]["energy"] = {
        "unit": "eV", "total": _stats(_concat(energies)), "per_atom": _stats(_concat(energy_per_atom)),
        "relative_within_composition": _stats(_concat(relative)),
    }
    threshold_count = None
    if force_threshold is not None:
        threshold_count = int(np.sum(_concat(force_magnitudes) > force_threshold))
    result["properties"]["force"] = {
        "unit": "eV/angstrom", "component": _stats(_concat(force_components)),
        "magnitude": _stats(_concat(force_magnitudes)), "max_atomic_force_per_frame": _stats(_concat(frame_max_forces)),
        "maximum_per_system": system_force_max,
        "threshold": force_threshold, "atoms_above_threshold": threshold_count,
    }
    result["properties"]["virial"] = {"unit": "eV", "component": _stats(_concat(virials))}
    result["composition"] = {
        "systems": dict(sorted(composition_systems.items())),
        "frames": dict(sorted(composition_frames.items())),
    }
    result["duplicates"] = {
        "groups": group_count, "duplicate_frames": duplicate_frames,
        "frames_in_duplicate_groups": len(duplicate_rows),
        "definition": "exact normalized duplicate, not structural similarity",
        "normalization": {"elements": True, "cell": True, "coordinates": True, "pbc": True, "decimals": decimals, "atom_order_independent": False, "wrapped": False},
    }
    result["geometry"] = {
        "minimum_distance": {
            "status": "calculated" if analyze_minimum_distance else "not_calculated",
            "unit": "angstrom",
            "per_frame": _stats(minimum_distances),
            "overall": min(minimum_distances) if minimum_distances else None,
            "by_element_pair": dict(sorted(minimum_distance_by_pair.items())),
            "minimum_per_system": minimum_distance_per_system,
            "threshold": minimum_distance_threshold,
            "frames_below_threshold": (
                frames_below_minimum_distance
                if minimum_distance_threshold is not None
                else None
            ),
            "definition": "minimum distance between distinct atoms with the frame cell and PBC",
        }
    }
    if minimum_distance_threshold is not None and frames_below_minimum_distance:
        _warn(
            warnings,
            "minimum_distance_below_threshold",
            f"有 {frames_below_minimum_distance} 帧的最小原子距离小于 "
            f"{minimum_distance_threshold} Å",
        )
    plotting = {
        "energy_per_atom": _concat(energy_per_atom), "force_components": _concat(force_components),
        "force_magnitudes": _concat(force_magnitudes), "frame_max_forces": _concat(frame_max_forces),
        "composition_frames": dict(composition_frames),
    }
    return result, systems_rows, duplicate_rows, plotting


def report(
    dataset_path: Path = typer.Argument(..., help="DeepMD NPY 数据集目录"),
    output: Path = typer.Option(Path("deepmd_report"), "--output", "-o", help="报告输出目录"),
    force_threshold: Optional[float] = typer.Option(None, "--force-threshold", min=0.0, help="统计超过该原子力模长的原子数 (eV/Å)"),
    minimum_distance_threshold: Optional[float] = typer.Option(
        None,
        "--minimum-distance-threshold",
        min=0.0,
        help="统计最小原子距离低于该值的帧数 (Å)",
    ),
    minimum_distance: bool = typer.Option(
        False,
        "--minimum-distance/--no-minimum-distance",
        help="是否对全部帧计算 PBC 最小原子距离（大型数据集较慢）",
    ),
) -> None:
    """生成 DeepMD NPY 数据集的静态统计与质量审计报告。"""
    dataset_path = dataset_path.expanduser().resolve()
    output = output.expanduser().resolve()
    if not dataset_path.is_dir():
        typer.secho(f"错误: 数据集目录不存在: {dataset_path}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    try:
        if output.exists() and any(output.iterdir()):
            raise FileExistsError(f"输出目录非空，请使用新的目录: {output}")
        calculate_minimum_distance = (
            minimum_distance or minimum_distance_threshold is not None
        )
        result, systems, duplicates, plotting = analyze_dataset(
            dataset_path,
            force_threshold,
            minimum_distance_threshold,
            calculate_minimum_distance,
        )
        ensure_empty_output(output)
        write_json(output / "report.json", result)
        write_csv(output / "systems.csv", systems)
        with (output / "duplicates.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=("group_id", "frame_id", "size"))
            writer.writeheader()
            writer.writerows(duplicates)
        _write_figures(output, plotting)
        (output / "report.html").write_text(render_deepmd_report(result, systems))
    except Exception as exc:
        typer.secho(f"错误: {type(exc).__name__}: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc
    typer.echo(f"报告已生成: {output}")
