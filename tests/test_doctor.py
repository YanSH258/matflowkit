import json
from importlib.metadata import version

from typer.testing import CliRunner

from tcckit.cli import app
from tcckit.doctor import inspect_environment
from tcckit import __version__


runner = CliRunner()


def test_package_metadata_matches_runtime_version():
    assert version("tcckit") == __version__


def test_doctor_json_reports_dependencies_and_resources(tmp_path, monkeypatch):
    pp_dir = tmp_path / "pp"
    orb_dir = tmp_path / "orb"
    pp_dir.mkdir()
    orb_dir.mkdir()
    (pp_dir / "O.UPF").write_text("test")
    (orb_dir / "O.orb").write_text("test")
    monkeypatch.setenv("ABACUS_PP_PATH", str(pp_dir))
    monkeypatch.setenv("ABACUS_ORB_PATH", str(orb_dir))

    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["tcckit_version"]
    assert "dpdata" in payload["dependencies"]
    assert "CP2KData" in payload["dependencies"]
    assert payload["abacus_resources"]["pseudopotentials"] == {
        "status": "ready",
        "path": str(pp_dir),
        "files": 1,
    }
    assert payload["abacus_resources"]["orbitals"]["files"] == 1


def test_doctor_reports_unset_resource_paths(monkeypatch):
    monkeypatch.delenv("ABACUS_PP_PATH", raising=False)
    monkeypatch.delenv("ABACUS_ORB_PATH", raising=False)

    payload = inspect_environment()

    assert payload["abacus_resources"]["pseudopotentials"]["status"] == "unset"
    assert payload["abacus_resources"]["orbitals"]["status"] == "unset"


def test_doctor_is_available_from_menu():
    result = runner.invoke(app, input="9\n1\n0\n")

    assert result.exit_code == 0, result.output
    assert "等价命令: tck doctor" in result.output
    assert "可选依赖" in result.output
