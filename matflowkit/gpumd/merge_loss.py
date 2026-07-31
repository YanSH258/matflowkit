"""mfk gpumd merge-loss: merge NEP loss files across restarted training runs."""

from __future__ import annotations

from pathlib import Path

import typer


def _numeric_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.split()
        try:
            float(fields[0])
            [float(value) for value in fields[1:]]
        except ValueError as exc:
            raise ValueError(
                f"{path}:{line_number} 不是有效的 loss.out 数值行"
            ) from exc
        rows.append(fields)
    if not rows:
        raise ValueError(f"{path} 中没有数值数据")
    return rows


def merge_loss_files(
    first: Path,
    restart: Path,
    output: Path,
    offset: float | None = None,
) -> tuple[int, int, float]:
    """Merge two loss tables and return their row counts and applied offset."""
    first_rows = _numeric_rows(first)
    restart_rows = _numeric_rows(restart)
    first_columns = len(first_rows[0])
    restart_columns = len(restart_rows[0])
    if any(len(row) != first_columns for row in first_rows):
        raise ValueError(f"{first} 的列数不一致")
    if any(len(row) != restart_columns for row in restart_rows):
        raise ValueError(f"{restart} 的列数不一致")
    if first_columns != restart_columns:
        raise ValueError(
            f"两个 loss 文件列数不同: {first_columns} 和 {restart_columns}"
        )

    applied_offset = float(first_rows[-1][0]) if offset is None else float(offset)
    merged_lines = [" ".join(row) for row in first_rows]
    for row in restart_rows:
        shifted_step = float(row[0]) + applied_offset
        if shifted_step.is_integer():
            step_text = str(int(shifted_step))
        else:
            step_text = f"{shifted_step:.12g}"
        merged_lines.append(" ".join([step_text, *row[1:]]))
    output.write_text("\n".join(merged_lines) + "\n")
    return len(first_rows), len(restart_rows), applied_offset


def merge_loss(
    first: Path = typer.Argument(
        Path("loss.out"),
        help="首次 NEP 训练产生的 loss.out",
    ),
    restart: Path = typer.Argument(
        Path("restart/loss.out"),
        help="续训产生的 loss.out",
    ),
    output: Path = typer.Option(
        Path("loss_merged.out"),
        "--output",
        "-o",
        help="合并后的输出文件",
    ),
    offset: float | None = typer.Option(
        None,
        help="续训步数偏移；默认取首次训练最后一个步数",
    ),
) -> None:
    """合并 NEP 首次训练和续训的 ``loss.out``。

    默认将 ``restart/loss.out`` 第一列加上首次 ``loss.out`` 的最后一个
    训练步数，再写入 ``loss_merged.out``。如果续训文件已经使用全局步数，
    可设置 ``--offset 0``。输出文件已存在时拒绝覆盖。
    """
    for path in (first, restart):
        if not path.is_file():
            typer.secho(f"错误: 文件不存在: {path}", err=True, fg=typer.colors.RED)
            raise typer.Exit(1)
    if output.exists():
        typer.secho(
            f"错误: 输出文件已存在: {output}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    try:
        first_count, restart_count, applied_offset = merge_loss_files(
            first, restart, output, offset
        )
    except (OSError, ValueError) as exc:
        typer.secho(f"错误: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc

    typer.echo(f"首次训练数据: {first_count} 行")
    typer.echo(f"续训数据: {restart_count} 行")
    typer.echo(f"续训步数偏移: {applied_offset:g}")
    typer.echo(f"已生成: {output}")
