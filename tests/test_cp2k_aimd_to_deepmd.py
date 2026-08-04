import json
from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from tcckit.cli import app


runner = CliRunner()


def _write_cp2k_aimd_stub(root: Path, frames: int = 2) -> None:
    root.mkdir()
    blocks = [
        " CELL| Vector a [angstrom]: 10.0 0.0 0.0\n"
        " CELL| Vector b [angstrom]: 0.0 10.0 0.0\n"
        " CELL| Vector c [angstrom]: 0.0 0.0 10.0\n"
    ]
    for index in range(frames):
        blocks.append(
            " *** SCF run converged in 5 steps ***\n"
            f" ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]: {-1.0 + index * 0.1}\n"
            " ATOMIC FORCES in [a.u.]\n"
            " # Atom Kind Element X Y Z\n"
            " 1 1 H 1.0E-3 0.0 0.0\n"
            " 2 1 H -1.0E-3 0.0 0.0\n"
            " SUM OF ATOMIC FORCES 0.0 0.0 0.0 0.0\n"
        )
    blocks.append(" PROGRAM ENDED AT\n")
    (root / "output.log").write_text("".join(blocks))
    for name in ("md-pos-1.xyz", "md-frc-1.xyz", "md-1.cell", "md-1.ener"):
        (root / name).write_text("test\n")


def test_cp2k_aimd_to_deepmd_writes_validated_dataset(tmp_path, monkeypatch):
    import dpdata
    import tcckit.cp2k.aimd_to_deepmd as command

    source = tmp_path / "aimd"
    _write_cp2k_aimd_stub(source)
    output = tmp_path / "dataset"
    system = dpdata.LabeledSystem(
        data={
            "atom_names": ["H"],
            "atom_numbs": [2],
            "atom_types": np.array([0, 0]),
            "orig": np.zeros(3),
            "cells": np.repeat(np.eye(3)[None, :, :] * 10.0, 2, axis=0),
            "coords": np.array(
                [
                    [[0.0, 0.0, 0.0], [0.7, 0.0, 0.0]],
                    [[0.0, 0.0, 0.0], [0.8, 0.0, 0.0]],
                ]
            ),
            "energies": np.array([-1.0, -0.9]),
            "forces": np.zeros((2, 2, 3)),
            "virials": np.zeros((2, 3, 3)),
        }
    )
    original_labeled_system = dpdata.LabeledSystem

    class FakeDpdata:
        __version__ = dpdata.__version__

        @staticmethod
        def LabeledSystem(file_name=None, fmt="auto", **kwargs):
            if fmt == "cp2kdata/md":
                return system
            return original_labeled_system(file_name, fmt=fmt, **kwargs)

    monkeypatch.setattr(command, "require_cp2kdata", lambda: "test")
    monkeypatch.setattr(command, "require_dpdata", lambda: FakeDpdata)

    result = runner.invoke(
        app,
        ["cp2k", "aimd-to-deepmd", str(source), str(output)],
    )

    assert result.exit_code == 0, result.output
    assert "转换完成" in result.output
    assert "帧数: 2" in result.output
    assert '"scope"' not in result.output
    summary = json.loads((output / "reports" / "summary.json").read_text())
    assert summary["frames"] == 2
    assert summary["atoms"] == 2
    assert summary["has_virial"] is True
    assert summary["deepmd_roundtrip_validation"] == "PASS"
    assert summary["roundtrip_validation"] == "PASS"
    assert (output / "deepmd_npy" / "H2" / "set.000" / "virial.npy").is_file()
    assert not (output / "train.xyz").exists()
    assert (output / "frame_manifest.csv").is_file()
    assert (output / "source_files.csv").is_file()
    assert (output / "SHA256SUMS.csv").is_file()


def test_cp2k_aimd_to_deepmd_reports_missing_native_files(tmp_path):
    source = tmp_path / "aimd"
    source.mkdir()
    (source / "output.log").write_text("PROGRAM ENDED AT\n")

    result = runner.invoke(
        app,
        ["cp2k", "aimd-to-deepmd", str(source), str(tmp_path / "dataset")],
    )

    assert result.exit_code == 2
    assert "缺少 CP2K AIMD 文件" in result.output
    assert not (tmp_path / "dataset").exists()


def test_cp2k_aimd_to_deepmd_preserves_existing_output(tmp_path):
    source = tmp_path / "aimd"
    _write_cp2k_aimd_stub(source)
    output = tmp_path / "dataset"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep\n")

    result = runner.invoke(
        app,
        ["cp2k", "aimd-to-deepmd", str(source), str(output)],
    )

    assert result.exit_code == 1
    assert marker.read_text() == "keep\n"
