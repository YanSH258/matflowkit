import csv
import json
from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from tcckit.cli import app


runner = CliRunner()


def _write_system(
    path: Path, frames: int, offset: float, virial: bool = True, element: str = "H"
) -> None:
    import dpdata

    data = {
        "atom_names": [element],
        "atom_numbs": [2],
        "atom_types": np.array([0, 0]),
        "cells": np.tile(np.eye(3) * 10.0, (frames, 1, 1)),
        "coords": np.array(
            [[[0.0, 0.0, 0.0], [offset + index * 0.01, 0.0, 0.0]] for index in range(frames)]
        ),
        "energies": np.arange(frames, dtype=float) + offset,
        "forces": np.zeros((frames, 2, 3)),
        "orig": np.zeros(3),
    }
    if virial:
        data["virials"] = np.tile(np.eye(3), (frames, 1, 1))
    dpdata.LabeledSystem(data=data).to("deepmd/npy", str(path), set_size=3)


def _test_indices(output: Path) -> list[int]:
    with (output / "frame_manifest.csv").open() as handle:
        return [
            int(row["global_frame_index"])
            for row in csv.DictReader(handle)
            if row["split"] == "test"
        ]


def test_deepmd_split_is_reproducible_and_validated(tmp_path):
    dataset = tmp_path / "dataset"
    _write_system(dataset / "first", 7, 0.7)
    _write_system(dataset / "second", 3, 1.2)
    first_output = tmp_path / "split_a"
    second_output = tmp_path / "split_b"
    arguments = [
        "deepmd",
        "split",
        str(dataset),
        "--test-size",
        "0.3",
        "--method",
        "random",
        "--seed",
        "19",
        "--virial",
    ]
    first = runner.invoke(app, arguments + ["--output", str(first_output)])
    second = runner.invoke(app, arguments + ["--output", str(second_output)])
    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert _test_indices(first_output) == _test_indices(second_output)
    assert len(_test_indices(first_output)) == 3

    summary = json.loads((first_output / "summary.json").read_text())
    assert summary["frames"] == 10
    assert summary["train_frames"] == 7
    assert summary["test_frames"] == 3
    assert summary["seed"] == 19
    assert summary["type_map"] == ["H"]
    assert summary["all_outputs_validated"] is True
    assert (first_output / "SHA256SUMS.csv").is_file()
    assert any((first_output / "train").rglob("type.raw"))
    assert any((first_output / "test").rglob("type.raw"))


def test_deepmd_split_uniform_exact_count_and_existing_output(tmp_path):
    dataset = tmp_path / "dataset"
    _write_system(dataset / "H2", 5, 0.7, virial=False)
    output = tmp_path / "split"
    result = runner.invoke(
        app,
        [
            "deepmd",
            "split",
            str(dataset),
            "--output",
            str(output),
            "--test-size",
            "2",
            "--method",
            "uniform",
        ],
    )
    assert result.exit_code == 0, result.output
    assert _test_indices(output) == [0, 4]
    assert json.loads((output / "summary.json").read_text())["seed"] is None

    marker = output / "keep.txt"
    marker.write_text("keep")
    repeated = runner.invoke(
        app,
        ["deepmd", "split", str(dataset), "--output", str(output)],
    )
    assert repeated.exit_code != 0
    assert marker.read_text() == "keep"


def test_deepmd_split_requires_energy_and_force(tmp_path):
    system = tmp_path / "dataset" / "H2"
    setdir = system / "set.000"
    setdir.mkdir(parents=True)
    (system / "type.raw").write_text("0\n0\n")
    (system / "type_map.raw").write_text("H\n")
    np.save(setdir / "coord.npy", np.zeros((2, 6)))
    np.save(setdir / "box.npy", np.tile(np.eye(3), (2, 1, 1)))
    result = runner.invoke(
        app,
        ["deepmd", "split", str(system), "--output", str(tmp_path / "split")],
    )
    assert result.exit_code != 0
    assert "energies not found" in result.output


def test_deepmd_split_rejects_inconsistent_type_map(tmp_path):
    dataset = tmp_path / "dataset"
    _write_system(dataset / "H2", 2, 0.7, element="H")
    _write_system(dataset / "He2", 2, 0.7, element="He")
    result = runner.invoke(
        app,
        ["deepmd", "split", str(dataset), "--output", str(tmp_path / "split")],
    )
    assert result.exit_code != 0
    assert "type_map 不一致" in result.output
