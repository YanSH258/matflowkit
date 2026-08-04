"""Prepare one ABACUS task directory per periodic Extended XYZ frame."""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path
from typing import Optional

import typer

from tcckit.abacus.audit import parse_basis_type, parse_calculation
from tcckit.common.io import sha256_file, write_csv, write_json, write_sha256_manifest
from tcckit.structure.convert import _require_ase, write_abacus_stru


_SUFFIX_RE = re.compile(r"^(\s*)suffix\s+\S+.*$", re.IGNORECASE)


def _xyz_files(source: Path) -> list[Path]:
    if source.is_file():
        if source.suffix.lower() not in {".xyz", ".extxyz"}:
            raise ValueError("输入文件必须是 .xyz 或 .extxyz")
        return [source.resolve()]
    if not source.is_dir():
        raise FileNotFoundError(f"输入不存在: {source}")
    files = sorted(
        {
            path.resolve()
            for suffix in ("*.xyz", "*.extxyz")
            for path in source.glob(suffix)
            if path.is_file()
        }
    )
    if not files:
        raise ValueError(f"{source} 中没有 .xyz 或 .extxyz 文件")
    return files


def _input_with_suffix(text: str, suffix: str) -> str:
    lines = text.splitlines()
    matches = [index for index, line in enumerate(lines) if _SUFFIX_RE.match(line)]
    if len(matches) > 1:
        raise ValueError("模板 INPUT 中存在多个 suffix")
    if matches:
        index = matches[0]
        indent = _SUFFIX_RE.match(lines[index]).group(1)
        lines[index] = f"{indent}suffix              {suffix}"
    else:
        insert_at = 1 if lines and lines[0].strip().upper() == "INPUT_PARAMETERS" else 0
        lines.insert(insert_at, f"suffix              {suffix}")
    return "\n".join(lines) + "\n"


def prepare_from_xyz(
    source: Path = typer.Argument(..., help="多帧 Extended XYZ，或包含多个 XYZ 的目录"),
    template: Path = typer.Argument(..., help="包含 INPUT 和 KPT 的 ABACUS 模板目录"),
    output: Path = typer.Argument(
        Path("abacus_tasks"), help="创建新的工作目录"
    ),
    pp_dir: Optional[Path] = typer.Option(
        None, help="赝势目录；默认读取 ABACUS_PP_PATH"
    ),
    orb_dir: Optional[Path] = typer.Option(
        None, help="轨道目录；LCAO 默认读取 ABACUS_ORB_PATH"
    ),
) -> None:
    """将周期 Extended XYZ 的每一帧准备为独立 ABACUS 任务。

    SOURCE 可以是一个多帧 Extended XYZ，也可以是包含多个 .xyz/.extxyz 文件的
    目录。TEMPLATE 必须包含已经确认过的 INPUT 和 KPT；所有计算参数原样保留，
    只为每个任务设置唯一 suffix。每个输出任务包含 INPUT、KPT 和 STRU，STRU 中
    写入赝势及 LCAO 轨道的绝对路径。普通 XYZ 没有晶胞/PBC 时拒绝生成。
    """
    source = source.expanduser().resolve()
    template = template.expanduser().resolve()
    output = output.expanduser().resolve()
    if output.exists():
        typer.secho(
            f"错误: 工作目录已存在，请输入新的工作目录: {output}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    staging = output.with_name(f".{output.name}.tck-{uuid.uuid4().hex}")
    try:
        files = _xyz_files(source)
        input_path = template / "INPUT"
        kpt_path = template / "KPT"
        missing = [path.name for path in (input_path, kpt_path) if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"模板目录缺少: {', '.join(missing)}")
        basis = parse_basis_type(template, default="")
        if basis not in {"pw", "lcao"}:
            raise ValueError("模板 INPUT 必须明确设置 basis_type pw 或 lcao")
        calculation = parse_calculation(template)
        if calculation == "unknown":
            raise ValueError("模板 INPUT 缺少 calculation")

        read, _ = _require_ase()
        (staging / "tasks").mkdir(parents=True)
        template_text = input_path.read_text()
        manifest = []
        source_rows = []
        resource_summary = {"pseudopotentials": {}, "orbitals": {}}
        task_number = 0

        for xyz_path in files:
            frames = read(str(xyz_path), format="extxyz", index=":")
            if not isinstance(frames, list):
                frames = [frames]
            if not frames:
                raise ValueError(f"{xyz_path} 中没有结构帧")
            source_rows.append(
                {
                    "path": str(xyz_path),
                    "frames": len(frames),
                    "sha256": sha256_file(xyz_path),
                }
            )
            for frame_index, atoms in enumerate(frames):
                task_number += 1
                task_id = f"task_{task_number:06d}"
                suffix = f"mfk_{task_number:06d}"
                task_dir = staging / "tasks" / task_id
                task_dir.mkdir()
                (task_dir / "INPUT").write_text(
                    _input_with_suffix(template_text, suffix)
                )
                shutil.copy2(kpt_path, task_dir / "KPT")
                stru_result = write_abacus_stru(
                    atoms, task_dir / "STRU", basis, pp_dir, orb_dir
                )
                for group in resource_summary:
                    resource_summary[group].update(stru_result[group])
                validation = stru_result["validation"]
                manifest.append(
                    {
                        "task_id": task_id,
                        "task_rel": f"tasks/{task_id}",
                        "source_file": str(xyz_path),
                        "source_frame": frame_index,
                        "suffix": suffix,
                        "calculation": calculation,
                        "basis_type": basis,
                        "formula": validation["formula"],
                        "natoms": validation["natoms"],
                        "cell_volume_A3": validation["cell_volume_A3"],
                        "minimum_distance_A": validation["minimum_distance_A"],
                        "maximum_coordinate_deviation_A": validation[
                            "maximum_coordinate_deviation_A"
                        ],
                        "input_sha256": sha256_file(task_dir / "INPUT"),
                        "kpt_sha256": sha256_file(task_dir / "KPT"),
                        "stru_sha256": sha256_file(task_dir / "STRU"),
                    }
                )

        if not manifest:
            raise ValueError("没有可生成的结构帧")
        write_csv(staging / "task_manifest.csv", manifest)
        (staging / "task_list.txt").write_text(
            "".join(f"{row['task_rel']}\n" for row in manifest)
        )
        write_json(
            staging / "summary.json",
            {
                "schema_version": "1.0",
                "source": str(source),
                "source_files": source_rows,
                "template": str(template),
                "template_input_sha256": sha256_file(input_path),
                "template_kpt_sha256": sha256_file(kpt_path),
                "tasks": len(manifest),
                "calculation": calculation,
                "basis_type": basis,
                "structure_validation": "passed",
                "resources": resource_summary,
            },
        )
        write_sha256_manifest(staging)
        staging.replace(output)
    except Exception as exc:
        if staging.exists():
            shutil.rmtree(staging)
        typer.secho(f"错误: {type(exc).__name__}: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc

    typer.echo(
        f"ABACUS 任务已生成: {output}；{len(files)} 个 XYZ 文件，"
        f"{len(manifest)} 个任务；{calculation}/{basis}"
    )
