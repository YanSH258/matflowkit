import csv
import json
from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from tcct.cli import app


runner = CliRunner()


def _template(root: Path) -> Path:
    root.mkdir()
    (root / "INPUT").write_text(
        "INPUT_PARAMETERS\n"
        "suffix old\n"
        "calculation scf\n"
        "basis_type lcao\n"
        "ecutwfc 100\n"
    )
    (root / "KPT").write_text("K_POINTS\n0\nGamma\n1 1 1 0 0 0\n")
    return root


def _resources(root: Path) -> tuple[Path, Path]:
    pp = root / "pp"
    orb = root / "orb"
    pp.mkdir()
    orb.mkdir()
    (pp / "Al.upf").write_text("pseudo\n")
    (orb / "Al.orb").write_text("orbital\n")
    return pp, orb


def _write_xyz(path: Path, shifts: list[float], periodic: bool = True) -> None:
    from ase import Atoms
    from ase.io import write

    frames = [
        Atoms(
            "Al2",
            positions=[[0.0, 0.0, 0.0], [1.0 + shift, 1.0, 1.0]],
            cell=np.eye(3) * 5.0 if periodic else None,
            pbc=periodic,
        )
        for shift in shifts
    ]
    write(path, frames, format="extxyz")


def test_prepare_from_xyz_accepts_directory_and_multiframe_files(tmp_path: Path):
    source = tmp_path / "xyz"
    source.mkdir()
    _write_xyz(source / "a.xyz", [0.0, 0.1])
    _write_xyz(source / "b.extxyz", [0.2])
    template = _template(tmp_path / "template")
    pp, orb = _resources(tmp_path)
    output = tmp_path / "tasks_out"

    result = runner.invoke(
        app,
        [
            "abacus",
            "prepare-from-xyz",
            str(source),
            str(template),
            str(output),
            "--pp-dir",
            str(pp),
            "--orb-dir",
            str(orb),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "2 个 XYZ 文件，3 个任务" in result.output
    for number in range(1, 4):
        task = output / "tasks" / f"task_{number:06d}"
        assert {path.name for path in task.iterdir()} == {"INPUT", "KPT", "STRU"}
        assert f"suffix              tcct_{number:06d}" in (task / "INPUT").read_text()
        assert "calculation scf" in (task / "INPUT").read_text()
        stru = (task / "STRU").read_text()
        assert str((pp / "Al.upf").resolve()) in stru
        assert str((orb / "Al.orb").resolve()) in stru

    with (output / "task_manifest.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert [row["source_frame"] for row in rows] == ["0", "1", "0"]
    assert all(float(row["maximum_coordinate_deviation_A"]) <= 1.0e-6 for row in rows)
    summary = json.loads((output / "summary.json").read_text())
    assert summary["tasks"] == 3
    assert summary["calculation"] == "scf"
    assert summary["basis_type"] == "lcao"
    assert summary["structure_validation"] == "passed"
    assert (output / "SHA256SUMS.csv").is_file()


def test_prepare_from_xyz_rejects_plain_xyz_without_cell(tmp_path: Path):
    source = tmp_path / "plain.xyz"
    _write_xyz(source, [0.0], periodic=False)
    template = _template(tmp_path / "template")
    pp, orb = _resources(tmp_path)
    output = tmp_path / "tasks_out"

    result = runner.invoke(
        app,
        [
            "abacus",
            "prepare-from-xyz",
            str(source),
            str(template),
            str(output),
            "--pp-dir",
            str(pp),
            "--orb-dir",
            str(orb),
        ],
    )

    assert result.exit_code == 2
    assert "Lattice/pbc" in result.output
    assert not output.exists()


def test_prepare_from_xyz_refuses_existing_output(tmp_path: Path):
    source = tmp_path / "structures.xyz"
    _write_xyz(source, [0.0])
    template = _template(tmp_path / "template")
    output = tmp_path / "tasks_out"
    output.mkdir()

    result = runner.invoke(
        app,
        ["abacus", "prepare-from-xyz", str(source), str(template), str(output)],
    )

    assert result.exit_code == 1
    assert "工作目录已存在" in result.output
