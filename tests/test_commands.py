import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from mdkit.abacus.audit import discover_tasks, inspect_task, parse_basis_type
from mdkit.abacus.plot_convergence import parse_series
from mdkit.cli import app
from mdkit.dpa4.common import read_fixed_indices
from mdkit.dpa4.batch_relax import read_manifest, safe_case_id
from mdkit.dpa4.evaluate import frame_metrics
from mdkit.dpdata.overlap import frame_hash


def write_deepmd(path: Path, x: float, energy: float) -> None:
    import dpdata

    data = {
        "atom_names": ["H"],
        "atom_numbs": [2],
        "atom_types": np.array([0, 0]),
        "cells": np.array([np.eye(3) * 10.0]),
        "coords": np.array([[[0.0, 0.0, 0.0], [x, 0.0, 0.0]]]),
        "energies": np.array([energy]),
        "forces": np.zeros((1, 2, 3)),
        "virials": np.zeros((1, 3, 3)),
        "orig": np.zeros(3),
    }
    dpdata.LabeledSystem(data=data).to("deepmd/npy", str(path))


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runner = CliRunner()

    def tearDown(self):
        self.temp.cleanup()

    def test_abacus_audit_passes_complete_scf(self):
        task = self.root / "task"
        out = task / "OUT.test"
        out.mkdir(parents=True)
        (task / "INPUT").write_text("INPUT_PARAMETERS\ncalculation scf\n")
        (out / "running_scf.log").write_text(
            "charge density convergence is achieved\n"
            "!FINAL_ETOT_IS -1.0 eV\n"
            "TOTAL-FORCE (eV/Angstrom)\n"
            "TOTAL-STRESS (KBAR)\n"
            "Finish Time : now\n"
        )
        result = inspect_task(task)
        self.assertEqual(result["status"], "PASS")
        report = self.root / "audit.csv"
        cli = self.runner.invoke(
            app, ["abacus", "audit", str(task), "-o", str(report), "--strict"]
        )
        self.assertEqual(cli.exit_code, 0, cli.output)
        self.assertTrue(report.is_file())

    def test_abacus_audit_passes_complete_md(self):
        task = self.root / "mdtask"
        out = task / "OUT.test"
        out.mkdir(parents=True)
        (task / "INPUT").write_text("INPUT_PARAMETERS\ncalculation md\nbasis_type pw\n")
        (out / "running_md.log").write_text("Finish Time : now\n")
        result = inspect_task(task)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["calculation"], "md")

    def test_parse_basis_type(self):
        task = self.root / "task"
        task.mkdir()
        (task / "INPUT").write_text("INPUT_PARAMETERS\nbasis_type pw\n")
        self.assertEqual(parse_basis_type(task), "pw")
        self.assertEqual(parse_basis_type(self.root / "missing"), "lcao")

    def test_dpa4_batch_manifest_and_case_id(self):
        manifest = self.root / "structures.csv"
        manifest.write_text("id,input\ncase one,a.xyz\n")
        rows = read_manifest(manifest)
        self.assertEqual(rows[0]["input"], "a.xyz")
        self.assertEqual(safe_case_id(rows[0]["id"]), "case_one")

    def test_dpa4_batch_manifest_requires_input(self):
        manifest = self.root / "bad.csv"
        manifest.write_text("id,path\none,a.xyz\n")
        with self.assertRaises(ValueError):
            read_manifest(manifest)

    def test_dpa4_evaluate_frame_metrics(self):
        result = frame_metrics(
            energy=-4.0,
            forces=np.array([[3.0, 0.0, 0.0], [0.0, 4.0, 0.0]]),
            atom_count=2,
        )
        self.assertAlmostEqual(result["energy_per_atom_eV"], -2.0)
        self.assertAlmostEqual(result["maximum_atomic_force_eV_A"], 4.0)
        self.assertAlmostEqual(
            result["force_component_rms_eV_A"],
            np.sqrt(25.0 / 6.0),
        )

    def test_dpdata_overlap_detects_shared_frame(self):
        from ase import Atoms
        from ase.io import write

        reference = self.root / "reference.extxyz"
        candidate = self.root / "candidate.extxyz"
        shared = Atoms("H2", positions=[[0, 0, 0], [0.7, 0, 0]])
        other = Atoms("H2", positions=[[0, 0, 0], [0.8, 0, 0]])
        write(reference, [shared, other])
        write(candidate, [shared])
        output = self.root / "overlap.json"
        result = self.runner.invoke(
            app,
            [
                "dpdata",
                "overlap",
                str(reference),
                str(candidate),
                "-o",
                str(output),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        report = json.loads(output.read_text())
        self.assertEqual(report["overlapping_unique_frames"], 1)
        self.assertEqual(report["overlapping_frame_pairs"], 1)

    def test_frame_hash_can_ignore_atom_order(self):
        from ase import Atoms

        first = Atoms("HO", positions=[[0, 0, 0], [1, 0, 0]])
        second = Atoms("OH", positions=[[1, 0, 0], [0, 0, 0]])
        self.assertNotEqual(frame_hash(first), frame_hash(second))
        self.assertEqual(
            frame_hash(first, order_independent=True),
            frame_hash(second, order_independent=True),
        )

    def test_discover_tasks_skips_out_hap_input(self):
        task = self.root / "task"
        out = task / "OUT.test"
        out.mkdir(parents=True)
        (task / "INPUT").write_text("INPUT_PARAMETERS\ncalculation scf\n")
        (out / "INPUT").write_text("INPUT_PARAMETERS\ncalculation scf\n")
        tasks = discover_tasks(self.root, "**/INPUT")
        self.assertEqual(tasks, [task])

    def test_check_relax_reports_concise_convergence(self):
        task = self.root / "relax_task"
        task.mkdir()
        log = task / "running_relax.log"
        log.write_text(
            "STEP OF RELAXATION : 1\n"
            "final etot is -2.0 eV\n"
            "Largest gradient in force is 0.2 eV/A.\n"
            "Relaxation is not converged yet!\n"
            "STEP OF RELAXATION : 2\n"
            "final etot is -2.1 eV\n"
            "Largest gradient in force is 0.02 eV/A.\n"
            "Relaxation is converged!\n"
        )
        result = self.runner.invoke(
            app, ["abacus", "check-relax", str(task)]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Relaxation is converged!", result.output)
        self.assertNotIn("Relaxation is not converged yet!", result.output)
        self.assertIn("离子步数: 最后一步为第 2 步", result.output)
        self.assertIn("提取数值: 0.02", result.output)

    def test_parse_convergence_series(self):
        log = self.root / "running_relax.log"
        log.write_text(
            "final etot is -2.0 eV\n"
            "Largest gradient in force is 0.2\n"
            "Largest gradient in stress is 1.2\n"
            "final etot is -2.1 eV\n"
            "Largest gradient in force is 0.02\n"
            "Relaxation is converged\n"
        )
        result = parse_series(log)
        self.assertEqual(result["energy"], [-2.0, -2.1])
        self.assertEqual(result["force"], [0.2, 0.02])
        self.assertTrue(result["converged"])

    def test_merge_and_convert(self):
        first = self.root / "first" / "H2"
        second = self.root / "second" / "H2"
        write_deepmd(first, 0.7, -1.0)
        write_deepmd(second, 0.8, -0.9)
        merged = self.root / "merged"
        result = self.runner.invoke(
            app,
            [
                "deepmd",
                "merge",
                str(first.parent),
                str(second.parent),
                "--output",
                str(merged),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        summary = json.loads((merged / "reports" / "summary.json").read_text())
        self.assertEqual(summary["frames"], 2)
        self.assertEqual(summary["duplicate_frames"], 0)
        xyz = self.root / "merged.xyz"
        result = self.runner.invoke(
            app,
            [
                "dpdata",
                "convert",
                str(merged / "deepmd_npy" / "H2"),
                str(xyz),
                "--from",
                "deepmd/npy",
                "--to",
                "extxyz",
                "--virial",
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(xyz.is_file())

    def test_merge_rejects_duplicate_frame(self):
        first = self.root / "first" / "H2"
        second = self.root / "second" / "H2"
        write_deepmd(first, 0.7, -1.0)
        write_deepmd(second, 0.7, -1.0)
        output = self.root / "merged"
        result = self.runner.invoke(
            app,
            [
                "deepmd",
                "merge",
                str(first.parent),
                str(second.parent),
                "--output",
                str(output),
            ],
        )
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertTrue((output / "duplicate_frames.csv").is_file())

    def test_xyz_to_deepmd_writes_raw_and_npy(self):
        xyz = self.root / "train.xyz"
        xyz.write_text(
            "2\n"
            'Lattice="10 0 0 0 10 0 0 0 10" '
            "Properties=species:S:1:pos:R:3:force:R:3 "
            'energy=-1.0 virial="0 0 0 0 0 0 0 0 0" pbc="T T T"\n'
            "H 0 0 0 0 0 0\n"
            "H 0.7 0 0 0 0 0\n"
        )
        output = self.root / "deepmd"
        result = self.runner.invoke(
            app,
            ["dpdata", "xyz-to-deepmd", str(xyz), str(output), "--set-size", "1"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        summary = json.loads(result.output)
        self.assertEqual(summary["systems"], 1)
        self.assertEqual(summary["frames"], 1)
        systems = [path for path in output.iterdir() if path.is_dir()]
        self.assertEqual(len(systems), 1)
        self.assertTrue((systems[0] / "coord.raw").is_file())
        self.assertTrue((systems[0] / "set.000" / "coord.npy").is_file())

    def test_xyz_to_deepmd_rejects_nonempty_output(self):
        xyz = self.root / "train.xyz"
        xyz.write_text("not parsed")
        output = self.root / "deepmd"
        output.mkdir()
        (output / "keep").write_text("do not overwrite")
        result = self.runner.invoke(
            app, ["dpdata", "xyz-to-deepmd", str(xyz), str(output)]
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("输出路径已存在且非空", result.stderr)

    def test_gpumd_merge_loss_offsets_restart_steps(self):
        first = self.root / "loss.out"
        restart = self.root / "restart_loss.out"
        output = self.root / "loss_merged.out"
        first.write_text("100 1.0 0.5\n200 0.8 0.4\n")
        restart.write_text("100 0.7 0.3\n200 0.6 0.2\n")
        result = self.runner.invoke(
            app,
            [
                "gpumd",
                "merge-loss",
                str(first),
                str(restart),
                "--output",
                str(output),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            output.read_text().splitlines(),
            [
                "100 1.0 0.5",
                "200 0.8 0.4",
                "300 0.7 0.3",
                "400 0.6 0.2",
            ],
        )

    def test_gpumd_merge_loss_rejects_existing_output(self):
        first = self.root / "loss.out"
        restart = self.root / "restart_loss.out"
        output = self.root / "loss_merged.out"
        first.write_text("100 1.0\n")
        restart.write_text("100 0.8\n")
        output.write_text("keep\n")
        result = self.runner.invoke(
            app,
            [
                "gpumd",
                "merge-loss",
                str(first),
                str(restart),
                "--output",
                str(output),
            ],
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertEqual(output.read_text(), "keep\n")

    def test_gpumd_plot_nep_training_writes_plot_and_metrics(self):
        data_dir = self.root / "nep"
        data_dir.mkdir()
        np.savetxt(
            data_dir / "loss.out",
            np.array(
                [
                    [100, 1.0, 0.1, 0.1, 0.5, 0.4, 0.2],
                    [200, 0.5, 0.05, 0.05, 0.2, 0.2, 0.1],
                ]
            ),
        )
        np.savetxt(
            data_dir / "energy_train.out",
            np.array([[-1.00, -1.01], [-0.80, -0.79]]),
        )
        np.savetxt(
            data_dir / "force_train.out",
            np.array(
                [
                    [0.1, 0.2, 0.3, 0.11, 0.19, 0.31],
                    [-0.1, -0.2, -0.3, -0.09, -0.21, -0.29],
                ]
            ),
        )
        np.savetxt(
            data_dir / "stress_train.out",
            np.array(
                [
                    [1, 2, 3, 4, 5, 6, 1.1, 1.9, 3.1, 3.9, 5.1, 5.9],
                    [2, 3, 4, 5, 6, 7, 2.1, 2.9, 4.1, 4.9, 6.1, 6.9],
                ]
            ),
        )
        plot = self.root / "nep_training.png"
        metrics = self.root / "nep_training_metrics.json"
        result = self.runner.invoke(
            app,
            [
                "gpumd",
                "plot-nep-training",
                str(data_dir),
                "--output",
                str(plot),
                "--metrics",
                str(metrics),
                "--max-points",
                "1000",
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(plot.is_file())
        values = json.loads(metrics.read_text())
        self.assertIn("energy", values)
        self.assertIn("force_components", values)
        self.assertIn("stress_components", values)
        self.assertAlmostEqual(values["energy"]["rmse"], 0.01)

    def test_dpa4_fixed_indices_are_one_based(self):
        indices = self.root / "fixed.txt"
        indices.write_text("1 3 5\n")
        self.assertEqual(read_fixed_indices(indices, 5), [0, 2, 4])

    def test_dpa4_relax_rejects_missing_input(self):
        result = self.runner.invoke(
            app,
            ["dpa4", "relax", str(self.root / "missing.xyz")],
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("输入结构不存在", result.stderr)

    def test_dpa4_neb_rejects_missing_endpoint(self):
        result = self.runner.invoke(
            app,
            [
                "dpa4",
                "neb",
                str(self.root / "missing_initial.xyz"),
                str(self.root / "missing_final.xyz"),
            ],
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("初态结构不存在", result.stderr)


if __name__ == "__main__":
    unittest.main()
