import csv
import json
from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from matflowkit.cli import app


runner = CliRunner()


def _write_dataset(root: Path) -> Path:
    system = root / "H2O"
    setdir = system / "set.000"
    setdir.mkdir(parents=True)
    (system / "type.raw").write_text("0\n0\n1\n")
    (system / "type_map.raw").write_text("H O\n")
    coords = np.array([
        [[0.0, 0.0, 0.0], [0.8, 0.0, 0.0], [0.4, 0.6, 0.0]],
        [[0.0, 0.0, 0.0], [0.8, 0.0, 0.0], [0.4, 0.6, 0.0]],
        [[0.0, 0.0, 0.0], [0.9, 0.0, 0.0], [0.4, 0.6, 0.0]],
    ])
    np.save(setdir / "coord.npy", coords)
    np.save(setdir / "box.npy", np.tile(np.eye(3) * 10.0, (3, 1, 1)))
    np.save(setdir / "energy.npy", np.array([-10.0, -10.0, -9.0]))
    forces = np.zeros((3, 3, 3))
    forces[2, 0, 0] = 12.0
    np.save(setdir / "force.npy", forces)
    np.save(setdir / "virial.npy", np.zeros((3, 9)))
    return root


def test_deepmd_report_generates_schema_html_and_duplicates(tmp_path):
    dataset = _write_dataset(tmp_path / "dataset")
    output = tmp_path / "report"
    result = runner.invoke(app, ["deepmd", "report", str(dataset), "-o", str(output), "--force-threshold", "10"])
    assert result.exit_code == 0, result.output
    assert (output / "report.html").is_file()
    assert (output / "figures" / "energy_per_atom_distribution.png").is_file()
    assert (output / "figures" / "force_distribution.png").is_file()
    assert (output / "figures" / "composition.png").is_file()

    report = json.loads((output / "report.json").read_text())
    assert report["schema_version"] == "1.0"
    assert report["report_type"] == "deepmd_dataset"
    assert report["dataset"]["systems"] == 1
    assert report["dataset"]["frames"] == 3
    assert report["properties"]["force"]["atoms_above_threshold"] == 1
    assert report["duplicates"]["groups"] == 1
    assert report["duplicates"]["duplicate_frames"] == 1
    with (output / "duplicates.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert {row["size"] for row in rows} == {"2"}


def test_deepmd_report_missing_dataset_fails(tmp_path):
    result = runner.invoke(app, ["deepmd", "report", str(tmp_path / "missing")])
    assert result.exit_code != 0
    assert "不存在" in result.output


def test_deepmd_report_missing_required_array_fails(tmp_path):
    dataset = tmp_path / "dataset"
    system = dataset / "system"
    (system / "set.000").mkdir(parents=True)
    (system / "type.raw").write_text("0\n")
    np.save(system / "set.000" / "coord.npy", np.zeros((1, 3)))
    result = runner.invoke(app, ["deepmd", "report", str(dataset), "-o", str(tmp_path / "report")])
    assert result.exit_code != 0
    assert "box.npy" in result.output
