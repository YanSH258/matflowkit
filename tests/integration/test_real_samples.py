"""Opt-in regression tests against preserved real calculation outputs."""

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from matflowkit.cli import app


pytestmark = pytest.mark.integration
runner = CliRunner()


@pytest.fixture(scope="module")
def sample_root() -> Path:
    value = os.environ.get("MFK_REAL_SAMPLE_ROOT")
    if not value:
        pytest.skip("set MFK_REAL_SAMPLE_ROOT to the preserved sample directory")
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        pytest.skip(f"real sample directory does not exist: {root}")
    return root


def _require(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"required real sample is missing: {path}")
    return path


def test_real_abacus_report(sample_root: Path, tmp_path: Path):
    source = _require(sample_root / "conversion_test_inputs" / "abacus")
    output = tmp_path / "abacus_report"
    result = runner.invoke(
        app,
        [
            "abacus",
            "report",
            str(source),
            "--output",
            str(output),
            "--expected",
            "1",
            "--strict",
        ],
    )
    assert result.exit_code == 0, result.output
    report = json.loads((output / "report.json").read_text())
    assert report["summary"]["tasks"] == 1
    assert report["summary"]["pass"] == 1
    assert report["jobs"][0]["final_energy_eV"] is not None


def test_real_cp2k_audit(sample_root: Path, tmp_path: Path):
    source = _require(
        sample_root / "conversion_test_inputs" / "cp2k" / "cp2k_single_points"
    )
    output = tmp_path / "cp2k_audit.csv"
    result = runner.invoke(
        app,
        [
            "cp2k",
            "audit",
            str(source),
            "--output",
            str(output),
            "--expected",
            "4",
            "--strict",
        ],
    )
    assert result.exit_code == 0, result.output
    summary = json.loads(output.with_suffix(".json").read_text())
    assert summary["outputs"] == 4
    assert summary["pass"] == 4


def test_real_cp2k_aimd_to_deepmd(sample_root: Path, tmp_path: Path):
    pytest.importorskip("cp2kdata")
    source = _require(
        sample_root / "conversion_test_inputs" / "cp2k" / "aimd_ni_drop_test"
    )
    output = tmp_path / "cp2k_aimd_dataset"
    result = runner.invoke(
        app,
        ["cp2k", "aimd-to-deepmd", str(source), str(output)],
    )
    assert result.exit_code == 0, result.output
    summary = json.loads((output / "reports" / "summary.json").read_text())
    assert summary["frames"] == 6
    assert summary["atoms"] == 352
    assert summary["type_map"] == ["H", "O", "P", "Ca"]
    assert summary["has_virial"] is True
    assert summary["roundtrip_validation"] == "PASS"
    assert (output / "train.xyz").is_file()


def test_real_vasp_to_deepmd(sample_root: Path, tmp_path: Path):
    source = _require(
        sample_root
        / "conversion_test_inputs"
        / "vasp"
        / "Cu_single-point"
        / "OUTCAR"
    )
    output = tmp_path / "vasp_dataset"
    result = runner.invoke(
        app,
        [
            "vasp",
            "to-deepmd",
            str(source),
            str(output),
            "--frames",
            "final",
            "--expected",
            "1",
        ],
    )
    assert result.exit_code == 0, result.output
    summary = json.loads((output / "reports" / "summary.json").read_text())
    assert summary["outcars_parsed"] == 1
    assert summary["frames"] == 1
    assert summary["all_systems_validated"] is True


def test_real_deepmd_report(sample_root: Path, tmp_path: Path):
    source = _require(
        sample_root
        / "vasp"
        / "cu_single_point_to_deepmd_v2"
        / "deepmd_npy"
    )
    output = tmp_path / "deepmd_report"
    result = runner.invoke(
        app, ["deepmd", "report", str(source), "--output", str(output)]
    )
    assert result.exit_code == 0, result.output
    report = json.loads((output / "report.json").read_text())
    assert report["dataset"]["systems"] == 1
    assert report["dataset"]["frames"] == 1
    assert report["dataset"]["elements"] == ["Cu"]
