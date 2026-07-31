"""mfk abacus check-relax：检查 ABACUS relax 计算的收敛情况。"""

import re
from pathlib import Path

import typer

# 收敛标记：只匹配真正的收敛/完成，不匹中间 "not converged yet" 等未收敛状态
_CONV_RE = re.compile(
    r"convergence has been achieved|relax.{0,10}is converged|is converged!",
    re.IGNORECASE,
)
# 离子步序号，形如 "STEP OF RELAXATION : 12"（ABACUS relax/cell-relax）
_STEP_RE = re.compile(r"STEP OF RELAXATION\s*:?\s*(\d+)", re.IGNORECASE)
# 总能行：形如 "final etot is ..." 或 "!FINAL etot is ..."
_ETOT_RE = re.compile(r"final\s+etot|!FINAL", re.IGNORECASE)
# 最大力行：形如 "LARGEST GRAD (eV/A)  : 0.00123" 或 "... max force ..."
_FORCE_RE = re.compile(r"largest\s+grad|max(imum)?[\s_-]*force", re.IGNORECASE)
_FORCE_NUM_RE = re.compile(r"([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)")


def find_relax_logs(directory: Path) -> list:
    """在 DIR 下查找 ABACUS relax 日志（running_relax.log）。"""
    logs = sorted(directory.glob("OUT.*/running_relax.log"))
    direct = directory / "running_relax.log"
    if direct.is_file():
        logs.insert(0, direct)
    return logs


def check_relax(
    dir: Path = typer.Argument(
        Path("."), help="ABACUS 计算目录（其下应含 OUT.*/running_relax.log 或 running_relax.log）"
    ),
):
    """检查 ABACUS relax 计算是否收敛，报告离子步数、总能与最大力。"""
    if not dir.is_dir():
        typer.secho(f"错误: 目录不存在: {dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    logs = find_relax_logs(dir)
    if not logs:
        typer.secho(
            f"错误: 在 {dir} 下未找到 running_relax.log（也没有 OUT.*/running_relax.log）",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    log = logs[0]
    typer.echo(f"日志文件: {log}")
    lines = log.read_text(errors="replace").splitlines()

    # 1) 收敛情况
    conv_lines = [l.strip() for l in lines if _CONV_RE.search(l)]
    if conv_lines:
        typer.secho("收敛状态: 发现收敛标记", fg=typer.colors.GREEN)
        typer.echo(f"  最终匹配行: {conv_lines[-1]}")
        if len(conv_lines) > 1:
            typer.echo(f"  共 {len(conv_lines)} 条收敛记录")
    else:
        typer.secho("收敛状态: 未发现收敛标记（计算可能未收敛或仍在运行）", fg=typer.colors.YELLOW)

    # 2) 最后一步离子步序号
    steps = [int(m.group(1)) for l in lines for m in [_STEP_RE.search(l)] if m]
    if steps:
        typer.echo(f"离子步数: 最后一步为第 {max(steps)} 步（共 {len(steps)} 条步进记录）")
    else:
        typer.echo("离子步数: 未找到 'STEP OF RELAXATION' 行")


    # 3) 总能
    etot_lines = [l.strip() for l in lines if _ETOT_RE.search(l)]
    if etot_lines:
        typer.echo(f"总能: {etot_lines[-1]}")
    else:
        typer.echo("总能: 未找到总能行（无 'final etot' / '!FINAL' 标记）")

    # 4) 最大力
    force_lines = [l.strip() for l in lines if _FORCE_RE.search(l)]
    if force_lines:
        last = force_lines[-1]
        typer.echo(f"最大力: {last}")
        nums = _FORCE_NUM_RE.findall(last)
        if nums:
            typer.echo(f"  提取数值: {nums[-1]} (eV/A)")
    else:
        typer.echo("最大力: 未找到力信息行（无 'LARGEST GRAD' / 'max force' 标记）")
