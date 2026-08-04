from pathlib import Path

from typer.testing import CliRunner

from tcckit.cli import app
from tcckit.dpdata.xyz_to_deepmd import inspect_xyz_virials


runner = CliRunner()


def _frame(symbol: str, energy: float, virial: bool) -> str:
    label = ' virial="1 0 0 0 1 0 0 0 1"' if virial else ""
    return (
        f"1\nenergy={energy}{label} Lattice=\"10 0 0 0 10 0 0 0 10\" "
        "Properties=species:S:1:pos:R:3:force:R:3\n"
        f"{symbol} 0 0 0 0 0 0\n"
    )


def test_xyz_to_deepmd_reports_missing_virial_frames(tmp_path: Path):
    source = tmp_path / "mixed.xyz"
    source.write_text(_frame("H", -1.0, True) + _frame("H", -2.0, False) + _frame("H", -3.0, True))
    result = runner.invoke(app, ["dpdata", "xyz-to-deepmd", str(source), str(tmp_path / "out")])
    assert result.exit_code == 2
    assert "virial 标签不一致" in result.output
    assert "组成 H1" in result.output
    assert "总帧 3" in result.output
    assert "有 virial 2" in result.output
    assert "缺少 virial 1" in result.output
    assert "从 1 开始）: 2" in result.output
    assert not (tmp_path / "out").exists()


def test_xyz_to_deepmd_allows_virial_difference_between_compositions(tmp_path: Path):
    source = tmp_path / "different_compositions.xyz"
    source.write_text(_frame("H", -1.0, True) + _frame("O", -2.0, False))
    summary = inspect_xyz_virials(source)
    assert summary == {
        "frames": 2,
        "compositions": 2,
        "frames_with_virial": 1,
        "frames_without_virial": 1,
    }
    output = tmp_path / "out"
    result = runner.invoke(app, ["dpdata", "xyz-to-deepmd", str(source), str(output)])
    assert result.exit_code == 0, result.output
    assert list(output.rglob("virial.npy"))
    assert len(list(output.rglob("energy.npy"))) == 2
    for name in ("box.raw", "coord.raw", "energy.raw", "force.raw", "virial.raw"):
        assert not list(output.rglob(name))
    assert list(output.rglob("type.raw"))
    assert list(output.rglob("type_map.raw"))
