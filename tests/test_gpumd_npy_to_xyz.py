import json
from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from tcct.cli import app


runner = CliRunner()


def _write_system(path: Path, names: list[str], types: list[int], energy: float) -> None:
    import dpdata

    natoms = len(types)
    counts = [types.count(index) for index in range(len(names))]
    data = {
        "atom_names": names,
        "atom_numbs": counts,
        "atom_types": np.asarray(types),
        "cells": np.asarray([np.eye(3) * 10.0]),
        "coords": np.zeros((1, natoms, 3)),
        "energies": np.asarray([energy]),
        "forces": np.zeros((1, natoms, 3)),
        "virials": np.zeros((1, 3, 3)),
        "orig": np.zeros(3),
    }
    dpdata.LabeledSystem(data=data).to("deepmd/npy", str(path))


def test_npy_to_xyz_combines_different_systems_into_one_xyz(tmp_path: Path):
    import dpdata

    dataset = tmp_path / "dataset"
    _write_system(dataset / "H2", ["H"], [0, 0], -1.0)
    # Source type order (H, Ca) differs from extxyz readback order (Ca, H).
    _write_system(dataset / "HCa", ["Ca", "H"], [1, 0], -2.0)
    output = tmp_path / "train.xyz"

    result = runner.invoke(app, ["gpumd", "npy-to-xyz", str(dataset), str(output), "--virial"])
    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["systems"] == 2
    assert summary["frames"] == 2
    assert summary["roundtrip_validation"] == "PASS"
    assert output.is_file()
    text = output.read_text()
    assert text.count("Properties=") == 2
    assert text.count("Lattice=") == 2
    assert text.count("energy=") == 2
    assert text.count("virial=") == 2

    checked = dpdata.MultiSystems.from_file(str(output), fmt="gpumd/xyz")
    assert len(checked) == 2
    assert sum(len(system) for system in checked) == 2


def test_npy_to_xyz_preserves_existing_output(tmp_path: Path):
    output = tmp_path / "train.xyz"
    output.write_text("keep")
    result = runner.invoke(app, ["gpumd", "npy-to-xyz", str(tmp_path), str(output)])
    assert result.exit_code == 1
    assert output.read_text() == "keep"
