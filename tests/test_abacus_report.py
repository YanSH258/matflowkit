import csv
import json
from pathlib import Path

from typer.testing import CliRunner

from matflowkit.cli import app


runner = CliRunner()


def _write_scf_task(path: Path) -> None:
    out = path / "OUT.test"
    out.mkdir(parents=True)
    (path / "INPUT").write_text("INPUT_PARAMETERS\ncalculation scf\nbasis_type pw\n")
    (out / "running_scf.log").write_text(
        "charge density convergence is achieved\n"
        "!FINAL_ETOT_IS -10.5 eV\n"
        "TOTAL-FORCE (eV/Angstrom)\n"
        "TOTAL-STRESS (KBAR)\n"
        "Finish Time : now\n"
    )


def _write_incomplete_relax_task(path: Path) -> None:
    out = path / "OUT.test"
    out.mkdir(parents=True)
    (path / "INPUT").write_text("INPUT_PARAMETERS\ncalculation relax\nbasis_type lcao\n")
    (out / "running_relax.log").write_text(
        "charge density convergence is achieved\n"
        "STEP OF RELAXATION : 1\n"
        "final etot is -9.0 eV\n"
        "Largest gradient in force is 0.2\n"
        "STEP OF RELAXATION : 2\n"
        "final etot is -9.2 eV\n"
        "Largest gradient in force is 0.05\n"
    )


def test_abacus_report_writes_auditable_outputs(tmp_path: Path):
    root = tmp_path / "tasks"
    _write_scf_task(root / "scf")
    _write_incomplete_relax_task(root / "relax")
    output = tmp_path / "report"

    result = runner.invoke(
        app,
        ["abacus", "report", str(root), "--output", str(output), "--expected", "3"],
    )

    assert result.exit_code == 0, result.output
    for relative in (
        "report.html",
        "report.json",
        "jobs.csv",
        "failed_jobs.csv",
        "figures/task_status.png",
        "figures/relax_metrics.png",
    ):
        assert (output / relative).is_file(), relative

    report = json.loads((output / "report.json").read_text())
    assert report["schema_version"] == "1.0"
    assert report["report_type"] == "abacus_tasks"
    assert report["summary"] == {
        "tasks": 2,
        "pass": 1,
        "incomplete": 1,
        "expected": 3,
        "expected_match": False,
        "calculations": {"relax": 1, "scf": 1},
    }
    rows = {row["task"]: row for row in report["jobs"]}
    assert rows["scf"]["final_energy_eV"] == -10.5
    assert rows["relax"]["ionic_steps"] == 2
    assert rows["relax"]["maximum_force_eV_A"] == 0.05
    assert {item["code"] for item in report["warnings"]} == {
        "incomplete_tasks",
        "expected_mismatch",
    }
    with (output / "failed_jobs.csv").open() as handle:
        failed = list(csv.DictReader(handle))
    assert [row["task"] for row in failed] == ["relax"]
    assert "ABACUS 任务报告" in (output / "report.html").read_text()


def test_abacus_report_strict_fails_after_writing_report(tmp_path: Path):
    root = tmp_path / "tasks"
    _write_incomplete_relax_task(root / "relax")
    output = tmp_path / "report"

    result = runner.invoke(
        app, ["abacus", "report", str(root), "-o", str(output), "--strict"]
    )

    assert result.exit_code == 2
    assert (output / "report.json").is_file()


def test_abacus_report_rejects_missing_tasks_and_preserves_nonempty_output(tmp_path: Path):
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    output = tmp_path / "report"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep")

    result = runner.invoke(
        app, ["abacus", "report", str(empty_root), "-o", str(output)]
    )

    assert result.exit_code == 2
    assert marker.read_text() == "keep"
