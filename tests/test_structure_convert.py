import json
from pathlib import Path

import pytest
from ase import Atoms
from ase.io import read, write
from typer.testing import CliRunner

from matflowkit.cli import app
from matflowkit.menu import _run_command
from matflowkit.structure.convert import validate_roundtrip


runner = CliRunner()


def _write_cif(path: Path) -> None:
    atoms = Atoms(
        "Al2",
        positions=[[0.0, 0.0, 0.0], [2.0, 2.0, 2.0]],
        cell=[4.0, 4.0, 4.0],
        pbc=True,
    )
    write(path, atoms, format="cif")


def _library(path: Path, filename: str) -> Path:
    path.mkdir()
    resource = path / filename
    resource.write_text("test resource\n")
    (path / "element.json").write_text(json.dumps({"Al": filename}))
    if filename.lower().endswith(".upf"):
        (path / "ecutwfc.json").write_text(json.dumps({"Al": 80.0}))
    return resource


def test_cif_to_extended_xyz_preserves_periodic_cell(tmp_path: Path):
    source = tmp_path / "Al.cif"
    _write_cif(source)
    result = runner.invoke(app, ["structure", "convert", str(source), "--to", "xyz"])
    assert result.exit_code == 0, result.output
    output = tmp_path / "Al.xyz"
    lines = output.read_text().splitlines()
    assert "Lattice=" in lines[1]
    assert 'pbc="T T T"' in lines[1]
    restored = read(output, format="extxyz")
    assert len(restored) == 2
    assert restored.get_volume() == pytest.approx(64.0)


def test_cif_to_poscar_roundtrip(tmp_path: Path):
    source = tmp_path / "Al.cif"
    _write_cif(source)
    output = tmp_path / "POSCAR"
    result = runner.invoke(
        app,
        ["structure", "convert", str(source), "--to", "poscar", "-o", str(output)],
    )
    assert result.exit_code == 0, result.output
    restored = read(output, format="vasp")
    assert restored.get_chemical_formula() == "Al2"
    assert restored.get_volume() == pytest.approx(64.0)


def test_roundtrip_validation_tolerates_numeric_noise_at_rounding_boundary():
    source = Atoms(
        "O",
        scaled_positions=[[0.04209475, 0.1692557, 0.2866428]],
        cell=[[18.8, 0.0, 0.0], [-9.4, 16.28, 0.0], [0.0, 0.0, 13.73]],
        pbc=True,
    )
    restored = source.copy()
    restored.set_scaled_positions([[0.04209475 - 4e-14, 0.1692557, 0.2866428]])
    validation = validate_roundtrip(source, restored)
    assert validation["maximum_coordinate_deviation_A"] < 1e-10


def test_roundtrip_validation_rejects_real_coordinate_change():
    source = Atoms("Al", scaled_positions=[[0.1, 0.2, 0.3]], cell=[4, 4, 4], pbc=True)
    restored = source.copy()
    restored.set_scaled_positions([[0.11, 0.2, 0.3]])
    with pytest.raises(ValueError, match="输出分数坐标"):
        validate_roundtrip(source, restored)


def test_roundtrip_validation_allows_reordered_atoms_of_same_element():
    source = Atoms(
        "O2",
        scaled_positions=[[0.1, 0.2, 0.3], [0.6, 0.7, 0.8]],
        cell=[4, 4, 4],
        pbc=True,
    )
    restored = source[[1, 0]]
    validation = validate_roundtrip(source, restored)
    assert validation["maximum_coordinate_deviation_A"] == pytest.approx(0.0)


def test_cif_to_stru_uses_library_paths_without_links(tmp_path: Path):
    source = tmp_path / "Al.cif"
    _write_cif(source)
    pp_file = _library(tmp_path / "pp", "Al_test.upf")
    output = tmp_path / "job" / "STRU"
    result = runner.invoke(
        app,
        [
            "structure",
            "convert",
            str(source),
            "--to",
            "stru",
            "--pp-dir",
            str(pp_file.parent),
            "--json",
            "-o",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Al_test.upf" in output.read_text()
    assert "Al 26.982 Al_test.upf" in output.read_text()
    assert "NUMERICAL_ORBITAL" not in output.read_text()
    assert not (output.parent / pp_file.name).exists()
    input_text = (output.parent / "INPUT").read_text()
    assert f"pseudo_dir  {pp_file.parent.resolve()}" in input_text
    assert "calculation  scf" in input_text
    assert "basis_type  pw" in input_text
    assert "ecutwfc     80" in input_text
    assert "kspacing     0.2" in input_text
    report = json.loads(result.output)
    assert report["validation"]["status"] == "passed"
    assert len(report["pseudopotentials"]["Al"]["sha256"]) == 64
    assert report["resource_mode"] == "library"
    assert report["ecutwfc_Ry"] == 80.0


def test_structure_convert_uses_compact_output_by_default(tmp_path: Path):
    source = tmp_path / "Al.cif"
    _write_cif(source)
    result = runner.invoke(app, ["structure", "convert", str(source), "--to", "xyz"])
    assert result.exit_code == 0, result.output
    assert "转换完成:" in result.output
    assert "校验: passed" in result.output
    assert '"pseudopotentials"' not in result.output


def test_cif_to_lcao_stru_adds_matching_orbital(tmp_path: Path):
    source = tmp_path / "Al.cif"
    _write_cif(source)
    pp_file = _library(tmp_path / "pp", "Al_test.upf")
    orb_file = _library(tmp_path / "orb", "Al_test.orb")
    output = tmp_path / "STRU"
    result = runner.invoke(
        app,
        [
            "structure",
            "convert",
            str(source),
            "--to",
            "stru",
            "--basis",
            "lcao",
            "--pp-dir",
            str(pp_file.parent),
            "--orb-dir",
            str(orb_file.parent),
            "--copy-files",
            "-o",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "NUMERICAL_ORBITAL" in output.read_text()
    assert orb_file.name in output.read_text()
    assert (output.parent / pp_file.name).is_file()
    assert not (output.parent / pp_file.name).is_symlink()
    assert (output.parent / orb_file.name).is_file()
    input_text = (output.parent / "INPUT").read_text()
    assert "pseudo_dir  ." in input_text
    assert "orbital_dir ." in input_text
    assert "gamma_only   1" in input_text


def test_cif_to_stru_fails_before_output_when_element_is_missing(tmp_path: Path):
    source = tmp_path / "Al.cif"
    _write_cif(source)
    pp_dir = tmp_path / "pp"
    pp_dir.mkdir()
    (pp_dir / "element.json").write_text(json.dumps({"O": "O.upf"}))
    output = tmp_path / "STRU"
    result = runner.invoke(
        app,
        [
            "structure",
            "convert",
            str(source),
            "--to",
            "stru",
            "--pp-dir",
            str(pp_dir),
            "-o",
            str(output),
        ],
    )
    assert result.exit_code == 2
    assert "缺少元素 Al" in result.output
    assert not output.exists()


def test_structure_convert_refuses_existing_output(tmp_path: Path):
    source = tmp_path / "Al.cif"
    _write_cif(source)
    output = tmp_path / "Al.xyz"
    output.write_text("keep\n")
    result = runner.invoke(app, ["structure", "convert", str(source), "--to", "xyz"])
    assert result.exit_code == 1
    assert output.read_text() == "keep\n"


def test_structure_convert_rejects_partial_occupancy_cif(tmp_path: Path):
    source = tmp_path / "partial.cif"
    source.write_text(
        "data_partial\n"
        "_cell_length_a 4\n_cell_length_b 4\n_cell_length_c 4\n"
        "_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n"
        "_space_group_name_H-M_alt 'P 1'\n"
        "loop_\n_atom_site_label\n_atom_site_type_symbol\n"
        "_atom_site_fract_x\n_atom_site_fract_y\n_atom_site_fract_z\n"
        "_atom_site_occupancy\nAl1 Al 0 0 0 0.5\n"
    )
    result = runner.invoke(app, ["structure", "convert", str(source), "--to", "xyz"])
    assert result.exit_code == 2
    assert "部分占位" in result.output
    assert not (tmp_path / "partial.xyz").exists()


def test_stru_requires_unambiguous_resource_match_without_mapping(tmp_path: Path):
    source = tmp_path / "Al.cif"
    _write_cif(source)
    pp_dir = tmp_path / "pp"
    pp_dir.mkdir()
    (pp_dir / "Al_a.upf").write_text("a")
    (pp_dir / "Al_b.upf").write_text("b")
    result = runner.invoke(
        app,
        ["structure", "convert", str(source), "--to", "stru", "--pp-dir", str(pp_dir)],
    )
    assert result.exit_code == 2
    assert "匹配到多个赝势文件" in result.output
    assert not (tmp_path / "Al.STRU").exists()


def test_stru_refuses_existing_input_without_writing_output(tmp_path: Path):
    source = tmp_path / "Al.cif"
    _write_cif(source)
    pp_file = _library(tmp_path / "pp", "Al_test.upf")
    (tmp_path / "INPUT").write_text("keep\n")
    result = runner.invoke(
        app,
        ["structure", "convert", str(source), "--to", "stru", "--pp-dir", str(pp_file.parent)],
    )
    assert result.exit_code == 1
    assert "INPUT 已存在" in result.output
    assert (tmp_path / "INPUT").read_text() == "keep\n"
    assert not (tmp_path / "Al.STRU").exists()


def test_stru_requires_cutoff_metadata_or_explicit_value(tmp_path: Path):
    source = tmp_path / "Al.cif"
    _write_cif(source)
    pp_dir = tmp_path / "pp"
    pp_dir.mkdir()
    (pp_dir / "Al_test.upf").write_text("test resource\n")
    (pp_dir / "element.json").write_text(json.dumps({"Al": "Al_test.upf"}))
    result = runner.invoke(
        app,
        ["structure", "convert", str(source), "--to", "stru", "--pp-dir", str(pp_dir)],
    )
    assert result.exit_code == 2
    assert "无法确定元素 Al 的 ecutwfc" in result.output
    assert not (tmp_path / "INPUT").exists()
    assert not (tmp_path / "Al.STRU").exists()


def test_menu_does_not_print_command_error_twice(monkeypatch, capsys):
    answers = iter(["missing.cif", "bad-format", "pw"])
    monkeypatch.setattr("matflowkit.menu._prompt", lambda *args: next(answers))
    _run_command(
        app,
        "structure",
        "convert",
        [
            ("input", "输入 CIF", "structure.cif", False),
            ("--to", "目标格式", "xyz", False),
            ("--basis", "STRU 基组", "pw", False),
        ],
    )
    assert capsys.readouterr().out.count("不支持的目标格式") == 1
