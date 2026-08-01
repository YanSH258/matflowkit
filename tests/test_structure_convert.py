import json
from pathlib import Path

import pytest
from ase import Atoms
from ase.io import read, write
from typer.testing import CliRunner

from matflowkit.cli import app


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


def test_cif_to_stru_uses_mapping_and_links_pseudopotential(tmp_path: Path):
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
            "-o",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Al_test.upf" in output.read_text()
    assert "Al 26.982 Al_test.upf" in output.read_text()
    assert "NUMERICAL_ORBITAL" not in output.read_text()
    link = output.parent / pp_file.name
    assert link.is_symlink()
    assert link.resolve() == pp_file.resolve()
    report = json.loads(result.output)
    assert report["validation"]["status"] == "passed"
    assert len(report["pseudopotentials"]["Al"]["sha256"]) == 64


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
