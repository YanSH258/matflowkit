"""mfk cp2k audit: inspect CP2K completion and label evidence."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Optional

import typer

from matflowkit.common.io import write_csv, write_json
from matflowkit.cp2k.parser import parse_cp2k_output


def discover_outputs(root: Path, pattern: str) -> list[Path]:
    """Discover one output file or recursively matching CP2K outputs."""
    if root.is_file():
        return [root]
    return sorted(path for path in root.glob(pattern) if path.is_file())


def public_row(parsed: dict) -> dict:
    """Remove in-memory arrays before writing an audit table."""
    return {key: value for key, value in parsed.items() if not key.startswith("_")}


def audit(
    root: Path = typer.Argument(
        Path("."),
        help="任务目录或输出文件",
    ),
    pattern: str = typer.Option(
        "**/output.log",
        help="相对于任务根目录的输出搜索模式",
    ),
    output: Path = typer.Option(
        Path("cp2k_audit.csv"),
        "--output",
        "-o",
        help="逐任务审计 CSV",
    ),
    expected: Optional[int] = typer.Option(None, help="预期输出文件数量"),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="存在未通过任务或数量不符时返回退出码 2",
    ),
) -> None:
    """批量检查 CP2K 完成、SCF、能量、力和晶胞，生成 CSV/JSON。"""
    root = root.expanduser().resolve()
    output = output.expanduser().resolve()
    if not root.exists():
        typer.secho(f"错误: 路径不存在: {root}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    paths = discover_outputs(root, pattern)
    if not paths:
        typer.secho("错误: 未发现 CP2K 输出文件", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    if output.exists() or output.with_suffix(".json").exists():
        typer.secho("错误: 审计输出已存在", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)

    rows = [public_row(parse_cp2k_output(path)) for path in paths]
    write_csv(output, rows)
    counts = Counter(row["status"] for row in rows)
    summary = {
        "root": str(root),
        "pattern": pattern,
        "outputs": len(rows),
        "pass": counts["PASS"],
        "incomplete": counts["INCOMPLETE"],
        "expected": expected,
        "expected_match": expected is None or expected == len(rows),
        "audit_csv": str(output),
    }
    write_json(output.with_suffix(".json"), summary)
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))
    failed = counts["INCOMPLETE"] > 0 or (
        expected is not None and expected != len(rows)
    )
    if strict and failed:
        raise typer.Exit(2)
