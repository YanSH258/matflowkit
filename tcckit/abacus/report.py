"""Generate a static report from existing ABACUS audit and convergence parsers."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Optional

import typer

from tcckit.abacus.audit import (
    discover_tasks,
    inspect_task,
    parse_basis_type,
)
from tcckit.abacus.check_relax import parse_series
from tcckit.common.io import ensure_empty_output, write_csv, write_json
from tcckit.report.html import render_abacus_report
from tcckit.report.schema import abacus_tasks_schema


def _relative(path: Path, root: Path) -> str:
    try:
        value = path.relative_to(root)
    except ValueError:
        return str(path)
    return "." if str(value) == "." else str(value)


def analyze_tasks(
    root: Path,
    pattern: str = "**/INPUT",
    expected: Optional[int] = None,
) -> dict:
    """Aggregate factual task status and convergence metrics."""
    tasks = discover_tasks(root, pattern)
    if not tasks:
        raise ValueError("未发现 INPUT 文件")

    report = abacus_tasks_schema()
    rows = []
    calculation_counts: Counter = Counter()
    for task in tasks:
        audited = inspect_task(task)
        calculation = audited["calculation"]
        calculation_counts[calculation] += 1
        log_path = Path(audited["log"]) if audited["log"] else None
        series = parse_series(log_path) if log_path is not None else {
            "energy": [],
            "force": [],
            "stress": [],
            "converged": False,
        }
        parsed_steps = max(
            len(series["energy"]), len(series["force"]), len(series["stress"])
        )
        ionic_steps = (
            parsed_steps if calculation in {"relax", "cell-relax"} else 0
        )
        row = {
            "task": _relative(task, root),
            "calculation": calculation,
            "basis_type": parse_basis_type(task),
            "status": audited["status"],
            "detail": audited["detail"],
            "log": _relative(log_path, root) if log_path is not None else None,
            "exit_0": audited["exit_0"],
            "exit_nonzero": audited["exit_nonzero"],
            "scf_converged": audited["scf_converged"],
            "relax_converged": audited["relax_converged"],
            "finish_time": audited["finish_time"],
            "has_force": audited["has_force"],
            "has_stress": audited["has_stress"],
            "ionic_steps": ionic_steps or None,
            "final_energy_eV": series["energy"][-1] if series["energy"] else None,
            "maximum_force_eV_A": series["force"][-1] if series["force"] else None,
            "maximum_stress_kbar": series["stress"][-1] if series["stress"] else None,
        }
        rows.append(row)

    status_counts = Counter(row["status"] for row in rows)
    expected_match = expected is None or expected == len(rows)
    report["root"] = str(root)
    report["summary"].update(
        {
            "tasks": len(rows),
            "pass": status_counts["PASS"],
            "incomplete": status_counts["INCOMPLETE"],
            "expected": expected,
            "expected_match": expected_match,
            "calculations": dict(sorted(calculation_counts.items())),
        }
    )
    report["jobs"] = rows
    report["figures"] = {
        "task_status": "figures/task_status.png",
        "relax_metrics": "figures/relax_metrics.png",
    }
    if status_counts["INCOMPLETE"]:
        report["warnings"].append(
            {
                "code": "incomplete_tasks",
                "message": f"{status_counts['INCOMPLETE']} 个任务的完成证据不完整",
            }
        )
    missing_logs = sum(row["log"] is None for row in rows)
    if missing_logs:
        report["warnings"].append(
            {"code": "missing_log", "message": f"{missing_logs} 个任务未找到 running_*.log"}
        )
    unknown = calculation_counts["unknown"]
    if unknown:
        report["warnings"].append(
            {"code": "unknown_calculation", "message": f"{unknown} 个任务无法识别 calculation"}
        )
    if not expected_match:
        report["warnings"].append(
            {
                "code": "expected_mismatch",
                "message": f"实际发现 {len(rows)} 个任务，与预期 {expected} 不一致",
            }
        )
    return report


def _write_figures(output: Path, report: dict) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("此命令需要 matplotlib；请安装 `pip install -e '.[plot]'`") from exc

    from tcckit.common.plot_style import COLORS, apply_plot_style, figure_size, save_figure

    apply_plot_style()
    figures = output / "figures"
    calculations = list(report["summary"]["calculations"])
    passed = [
        sum(row["calculation"] == name and row["status"] == "PASS" for row in report["jobs"])
        for name in calculations
    ]
    incomplete = [
        sum(
            row["calculation"] == name and row["status"] == "INCOMPLETE"
            for row in report["jobs"]
        )
        for name in calculations
    ]
    fig, ax = plt.subplots(figsize=figure_size("single", 0.72))
    ax.bar(calculations, passed, label="PASS", color=COLORS["blue"])
    ax.bar(
        calculations,
        incomplete,
        bottom=passed,
        label="INCOMPLETE",
        color=COLORS["orange"],
    )
    ax.set_ylabel("Tasks")
    ax.set_xlabel("Calculation")
    ax.legend(frameon=False)
    save_figure(fig, figures / "task_status.png")

    relax_rows = [
        row
        for row in report["jobs"]
        if row["calculation"] in {"relax", "cell-relax"}
        and row["ionic_steps"] is not None
        and row["maximum_force_eV_A"] is not None
    ]
    fig, ax = plt.subplots(figsize=figure_size("single", 0.72))
    if relax_rows:
        colors = [
            COLORS["blue"] if row["status"] == "PASS" else COLORS["orange"]
            for row in relax_rows
        ]
        forces = [row["maximum_force_eV_A"] for row in relax_rows]
        ax.scatter([row["ionic_steps"] for row in relax_rows], forces, c=colors, s=24)
        if all(value > 0 for value in forces):
            ax.set_yscale("log")
        ax.set_xlabel("Ionic steps")
        ax.set_ylabel(r"Final max force (eV/$\mathrm{\AA}$)")
    else:
        ax.text(0.5, 0.5, "No relax metrics", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
    save_figure(fig, figures / "relax_metrics.png")


def _write_failed_jobs(path: Path, jobs: list[dict]) -> None:
    failed = [row for row in jobs if row["status"] != "PASS"]
    if failed:
        write_csv(path, failed)
    else:
        path.write_text(",".join(jobs[0].keys()) + "\n")


def report(
    root: Path = typer.Argument(Path("."), help="ABACUS 任务根目录"),
    output: Path = typer.Option(Path("abacus_report"), "--output", "-o", help="报告输出目录"),
    pattern: str = typer.Option("**/INPUT", help="相对 root 的 INPUT 搜索模式"),
    expected: Optional[int] = typer.Option(None, help="预期任务数"),
    strict: bool = typer.Option(False, help="存在未完成任务或任务数不符时返回非零退出码"),
) -> None:
    """生成 ABACUS 批量任务的静态状态与收敛报告。"""
    root = root.expanduser().resolve()
    output = output.expanduser().resolve()
    if not root.is_dir():
        typer.secho(f"错误: 目录不存在: {root}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    try:
        if output.exists() and any(output.iterdir()):
            raise FileExistsError(f"输出目录非空，请使用新的目录: {output}")
        result = analyze_tasks(root, pattern, expected)
        ensure_empty_output(output)
        _write_figures(output, result)
        write_json(output / "report.json", result)
        write_csv(output / "jobs.csv", result["jobs"])
        _write_failed_jobs(output / "failed_jobs.csv", result["jobs"])
        (output / "report.html").write_text(
            render_abacus_report(result), encoding="utf-8"
        )
    except Exception as exc:
        typer.secho(f"错误: {type(exc).__name__}: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc

    summary = result["summary"]
    typer.echo(
        f"报告已生成: {output}；任务 {summary['tasks']}，"
        f"PASS {summary['pass']}，未完成 {summary['incomplete']}"
    )
    failed = summary["incomplete"] > 0 or not summary["expected_match"]
    if strict and failed:
        raise typer.Exit(2)
