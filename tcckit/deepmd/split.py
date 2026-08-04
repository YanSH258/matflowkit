"""Reproducibly split DeepMD NPY frames into training and test datasets."""

from __future__ import annotations

import json
import platform
from pathlib import Path

import numpy as np
import typer

from tcckit.common.dpdata_utils import (
    find_deepmd_systems,
    finite_labeled,
    require_dpdata,
)
from tcckit.common.io import (
    ensure_empty_output,
    write_csv,
    write_json,
    write_sha256_manifest,
)


def _test_count(value: str, total_frames: int) -> tuple[int, str]:
    value = value.strip()
    try:
        if any(character in value.lower() for character in (".", "e")):
            fraction = float(value)
            if not 0.0 < fraction < 1.0:
                raise ValueError
            count = max(1, int(total_frames * fraction + 0.5))
            definition = f"fraction:{fraction:.12g}"
        else:
            count = int(value)
            if count <= 0:
                raise ValueError
            definition = f"count:{count}"
    except ValueError as exc:
        raise ValueError("--test-size 必须是 0 到 1 之间的小数，或正整数帧数") from exc
    if count >= total_frames:
        raise ValueError(
            f"测试集帧数 {count} 必须小于总帧数 {total_frames}，训练集不能为空"
        )
    return count, definition


def _selected_indices(
    total_frames: int, test_count: int, method: str, seed: int
) -> np.ndarray:
    if method == "uniform":
        return np.linspace(0, total_frames - 1, test_count, dtype=int)
    if method == "random":
        generator = np.random.default_rng(seed)
        return np.sort(generator.choice(total_frames, test_count, replace=False))
    raise ValueError("--method 只支持 uniform 或 random")


def _system_label(dataset: Path, path: Path) -> Path:
    if path == dataset:
        return Path(dataset.name)
    return path.relative_to(dataset)


def _validate_written(source, selected, output: Path, require_virial: bool) -> None:
    dpdata = require_dpdata()
    restored = dpdata.LabeledSystem(str(output), fmt="deepmd/npy")
    valid = finite_labeled(restored, require_virial=require_virial)
    if len(restored) != len(selected) or int(valid.sum()) != len(restored):
        raise ValueError(f"输出回读验证失败: {output}")
    if list(restored.data["atom_names"]) != list(source.data["atom_names"]):
        raise ValueError(f"输出 type_map 回读不一致: {output}")
    expected = source.sub_system(selected.tolist())
    keys = ["cells", "coords", "energies", "forces"]
    if "virials" in expected.data:
        keys.append("virials")
    for key in keys:
        if key not in restored.data or not np.allclose(
            expected.data[key], restored.data[key], rtol=1.0e-10, atol=1.0e-8
        ):
            raise ValueError(f"输出 {key} 数值回读不一致: {output}")


def split(
    dataset: Path = typer.Argument(..., help="DeepMD NPY 单个 system 或数据集根目录"),
    output: Path = typer.Option(
        Path("deepmd_split"), "--output", "-o", help="新的划分结果目录"
    ),
    test_size: str = typer.Option(
        "0.1", "--test-size", help="测试集比例（0 到 1）或测试集帧数"
    ),
    method: str = typer.Option(
        "random", "--method", help="选择方法：random 或 uniform"
    ),
    seed: int = typer.Option(42, "--seed", help="random 方法的随机种子"),
    set_size: int = typer.Option(2000, "--set-size", min=1, help="每个 set.* 的最大帧数"),
    require_virial: bool = typer.Option(
        False, "--virial/--no-virial", help="是否要求所有输入帧都有 virial"
    ),
) -> None:
    """可复现地划分 DeepMD NPY 训练集和测试集，并记录逐帧来源。"""
    dataset = dataset.expanduser().resolve()
    output = output.expanduser().resolve()
    method = method.strip().lower()
    if not dataset.is_dir():
        typer.secho(f"错误: 数据集目录不存在: {dataset}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    try:
        dpdata = require_dpdata()
        paths = find_deepmd_systems(dataset)
        if not paths:
            raise ValueError("未发现 DeepMD NPY system（需要 type.raw + set.*/）")

        loaded = []
        frame_refs = []
        common_type_map = None
        for system_index, path in enumerate(paths):
            data = dpdata.LabeledSystem(str(path), fmt="deepmd/npy")
            if len(data) == 0:
                raise ValueError(f"system 为零帧: {path}")
            valid = finite_labeled(data, require_virial=require_virial)
            if int(valid.sum()) != len(data):
                raise ValueError(f"system 含 NaN/Inf 或不完整标签帧: {path}")
            current_type_map = list(data.data["atom_names"])
            if common_type_map is None:
                common_type_map = current_type_map
            elif current_type_map != common_type_map:
                raise ValueError(
                    f"type_map 不一致: {path} 为 {current_type_map}，"
                    f"预期 {common_type_map}"
                )
            label = _system_label(dataset, path)
            loaded.append((path, label, data))
            frame_refs.extend((system_index, frame) for frame in range(len(data)))

        test_count, test_size_definition = _test_count(test_size, len(frame_refs))
        test_indices = set(
            _selected_indices(len(frame_refs), test_count, method, seed).tolist()
        )
        ensure_empty_output(output)

        selected_by_system = {
            (split_name, index): []
            for split_name in ("train", "test")
            for index in range(len(loaded))
        }
        manifest = []
        output_offsets: dict[tuple[str, int], int] = {
            key: 0 for key in selected_by_system
        }
        for global_index, (system_index, source_frame) in enumerate(frame_refs):
            split_name = "test" if global_index in test_indices else "train"
            output_frame = output_offsets[(split_name, system_index)]
            output_offsets[(split_name, system_index)] += 1
            selected_by_system[(split_name, system_index)].append(source_frame)
            source_path, label, _ = loaded[system_index]
            manifest.append(
                {
                    "global_frame_index": global_index,
                    "split": split_name,
                    "source_system": str(source_path),
                    "source_frame_index": source_frame,
                    "output_system": str(Path(split_name) / label),
                    "output_frame_index": output_frame,
                }
            )

        system_rows = []
        for system_index, (source_path, label, data) in enumerate(loaded):
            for split_name in ("train", "test"):
                indices = selected_by_system[(split_name, system_index)]
                if not indices:
                    continue
                destination = output / split_name / label
                subset = data.sub_system(indices)
                subset.to(
                    "deepmd/npy",
                    str(destination),
                    set_size=set_size,
                    prec=np.float64,
                )
                _validate_written(data, np.asarray(indices), destination, require_virial)
                system_rows.append(
                    {
                        "split": split_name,
                        "system": str(label),
                        "frames": len(indices),
                        "natoms": data.get_natoms(),
                        "source_system": str(source_path),
                        "validation": "PASS",
                    }
                )

        write_csv(output / "frame_manifest.csv", manifest)
        write_csv(output / "systems.csv", system_rows)
        summary = {
            "schema_version": "1.0",
            "dataset": str(dataset),
            "output": str(output),
            "format": "deepmd_npy",
            "type_map": common_type_map,
            "method": method,
            "seed": seed if method == "random" else None,
            "test_size_request": test_size_definition,
            "systems": len(loaded),
            "frames": len(frame_refs),
            "train_frames": len(frame_refs) - test_count,
            "test_frames": test_count,
            "require_virial": require_virial,
            "set_size": set_size,
            "dpdata_version": getattr(dpdata, "__version__", "unknown"),
            "numpy_version": np.__version__,
            "python_version": platform.python_version(),
            "all_outputs_validated": all(
                row["validation"] == "PASS" for row in system_rows
            ),
        }
        write_json(output / "summary.json", summary)
        write_sha256_manifest(output)
    except Exception as exc:
        typer.secho(f"错误: {type(exc).__name__}: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc

    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))
