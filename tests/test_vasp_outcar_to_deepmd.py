from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from matflowkit.common.dpdata_utils import finite_labeled
from matflowkit.cli import app


runner = CliRunner()


def test_finite_labeled_accepts_vasp_shaped_labels():
    class Data:
        data = {
            "cells": np.eye(3)[None, :, :],
            "coords": np.zeros((1, 2, 3)),
            "energies": np.zeros(1),
            "forces": np.zeros((1, 2, 3)),
            "virials": np.zeros((1, 3, 3)),
        }

        def __len__(self):
            return 1

    assert finite_labeled(Data(), require_virial=True).tolist() == [True]


def test_vasp_outcar_to_deepmd_missing_input_fails(tmp_path: Path):
    result = runner.invoke(app, ["vasp", "outcar-to-deepmd", str(tmp_path / "missing"), str(tmp_path / "out")])
    assert result.exit_code != 0
    assert "输入不存在" in result.output


def test_vasp_outcar_to_deepmd_rejects_invalid_frame_mode(tmp_path: Path):
    source = tmp_path / "OUTCAR"
    source.write_text("")
    result = runner.invoke(app, ["vasp", "outcar-to-deepmd", str(source), str(tmp_path / "out"), "--frames", "middle"])
    assert result.exit_code != 0
    assert "all 或 final" in result.output
