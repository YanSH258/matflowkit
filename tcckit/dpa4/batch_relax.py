"""tck dpa4 batch-relax: resumable manifest-driven DPA4 optimization."""

from __future__ import annotations

import csv
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Optional

import typer

from tcckit.common.io import sha256_file, write_csv, write_json
from tcckit.dpa4.relax import relaxation_paths, run_relaxation


def read_manifest(path: Path) -> list[dict[str, str]]:
    """Read and validate a batch manifest containing at least an input column."""
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "input" not in reader.fieldnames:
            raise ValueError("manifest 必须包含 input 列")
        rows = list(reader)
    if not rows:
        raise ValueError("manifest 不含任务")
    return rows


def safe_case_id(value: str) -> str:
    """Convert a user-provided case ID into one safe path component."""
    result = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._")
    if not result:
        raise ValueError(f"无法生成有效任务 ID: {value!r}")
    return result


def batch_relax(
    manifest: Path = typer.Argument(
        Path("structures.csv"),
        help="CSV，需包含 input 列",
    ),
    output_dir: Path = typer.Option(
        Path("dpa4_batch_relax"),
        "--output-dir",
        "-o",
        help="批量结果目录",
    ),
    model: Optional[Path] = typer.Option(
        None,
        "--model",
        envvar="DPA4_MODEL",
        help="DPA4 model.pt；也可设置 DPA4_MODEL",
    ),
    fmax: float = typer.Option(0.05, min=1.0e-6, help="收敛力阈值，eV/angstrom"),
    steps: int = typer.Option(300, min=1, help="每个结构的最大优化步数"),
    optimizer: str = typer.Option("bfgs", help="bfgs、lbfgs 或 fire"),
    fixed_cell: bool = typer.Option(
        True,
        "--fixed-cell/--relax-cell",
        help="默认固定晶胞",
    ),
    use_d3: bool = typer.Option(
        True,
        "--d3/--no-d3",
        help="是否叠加 PBE-D3(BJ)",
    ),
    retry_failed: bool = typer.Option(
        False,
        "--retry-failed",
        help="清理本命令生成的失败任务文件并重新运行",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="存在失败或未收敛任务时返回退出码 2",
    ),
) -> None:
    """批量运行 DPA4 结构优化。"""
    manifest = manifest.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not manifest.is_file():
        typer.secho(f"错误: manifest 不存在: {manifest}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)

    try:
        records = read_manifest(manifest)
        tasks = []
        seen_ids: set[str] = set()
        for row_number, record in enumerate(records, start=2):
            raw_input = record.get("input", "").strip()
            if not raw_input:
                raise ValueError(f"manifest 第 {row_number} 行 input 为空")
            input_path = Path(raw_input).expanduser()
            if not input_path.is_absolute():
                input_path = manifest.parent / input_path
            input_path = input_path.resolve()
            if not input_path.is_file():
                raise FileNotFoundError(
                    f"manifest 第 {row_number} 行输入不存在: {input_path}"
                )
            case_id = safe_case_id(record.get("id", "") or input_path.stem)
            if case_id in seen_ids:
                raise ValueError(f"manifest 中任务 ID 重复: {case_id}")
            seen_ids.add(case_id)
            tasks.append((case_id, input_path))
    except Exception as exc:
        typer.secho(f"错误: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    status_csv = output_dir / "batch_status.csv"
    old_rows: dict[str, dict] = {}
    if status_csv.is_file():
        with status_csv.open(newline="") as handle:
            old_rows = {
                row["id"]: row for row in csv.DictReader(handle) if row.get("id")
            }

    rows_by_id = dict(old_rows)
    started = time.time()
    for case_id, input_path in tasks:
        previous = old_rows.get(case_id)
        if previous and previous.get("status") == "PASS":
            typer.echo(f"[SKIP PASS] {case_id}")
            continue
        if previous and previous.get("status") in {"ERROR", "NOT_CONVERGED"}:
            if not retry_failed:
                typer.echo(f"[SKIP FAILED] {case_id}")
                continue

        case_dir = output_dir / case_id
        output = case_dir / "relaxed.extxyz"
        generated = relaxation_paths(input_path, output)
        if retry_failed:
            for path in generated:
                path.unlink(missing_ok=True)
        case_dir.mkdir(parents=True, exist_ok=True)

        case_started = time.time()
        try:
            status, _ = run_relaxation(
                input=input_path,
                output=output,
                model=model,
                fmax=fmax,
                steps=steps,
                optimizer=optimizer,
                fixed_cell=fixed_cell,
                use_d3=use_d3,
            )
            row = {
                "id": case_id,
                "input": str(input_path),
                "input_sha256": sha256_file(input_path),
                **status,
            }
        except Exception as exc:
            row = {
                "id": case_id,
                "input": str(input_path),
                "input_sha256": sha256_file(input_path),
                "status": "ERROR",
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_seconds": round(time.time() - case_started, 3),
            }
        rows_by_id[case_id] = row
        write_csv(status_csv, [rows_by_id[key] for key in sorted(rows_by_id)])
        typer.echo(f"[{row['status']}] {case_id}")

    current_ids = sorted(case_id for case_id, _ in tasks)
    rows = [rows_by_id[key] for key in current_ids]
    counts = Counter(row.get("status", "UNKNOWN") for row in rows)
    summary = {
        "manifest": str(manifest),
        "manifest_sha256": sha256_file(manifest),
        "output_dir": str(output_dir),
        "tasks_in_manifest": len(tasks),
        "status_counts": dict(sorted(counts.items())),
        "elapsed_seconds": round(time.time() - started, 3),
        "status_csv": str(status_csv),
    }
    write_json(output_dir / "batch_summary.json", summary)
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))
    if strict and any(row.get("status") != "PASS" for row in rows):
        raise typer.Exit(2)
