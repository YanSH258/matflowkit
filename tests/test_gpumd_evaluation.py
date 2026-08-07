import json
from pathlib import Path
from typing import Optional

import numpy as np
from typer.testing import CliRunner

from tcct.cli import app


runner = CliRunner()


def _write_prediction_files(directory: Path, split: str, tensor: Optional[str] = None) -> None:
    np.savetxt(
        directory / f"energy_{split}.out",
        np.array([[-1.00, -1.01], [-0.80, -0.79]]),
    )
    np.savetxt(
        directory / f"force_{split}.out",
        np.array(
            [
                [0.1, 0.2, 0.3, 0.11, 0.19, 0.31],
                [-0.1, -0.2, -0.3, -0.09, -0.21, -0.29],
            ]
        ),
    )
    if tensor:
        np.savetxt(
            directory / f"{tensor}_{split}.out",
            np.array(
                [
                    [1, 2, 3, 4, 5, 6, 1.1, 1.9, 3.1, 3.9, 5.1, 5.9],
                    [2, 3, 4, 5, 6, 7, 2.1, 2.9, 4.1, 4.9, 6.1, 6.9],
                ]
            ),
        )


def test_gpumd_evaluation_uses_test_as_primary_evidence(tmp_path):
    data = tmp_path / "nep"
    data.mkdir()
    _write_prediction_files(data, "train", tensor="stress")
    _write_prediction_files(data, "test", tensor="stress")
    plot = tmp_path / "evaluation.png"
    metrics = tmp_path / "evaluation.json"
    result = runner.invoke(
        app,
        [
            "gpumd",
            "plot-nep-evaluation",
            str(data),
            "--output",
            str(plot),
            "--metrics",
            str(metrics),
        ],
    )
    assert result.exit_code == 0, result.output
    assert plot.is_file()
    values = json.loads(metrics.read_text())
    assert values["primary_evidence"] == "held-out test set"
    assert set(values["splits"]) == {"train", "test"}
    assert "stress_components" in values["splits"]["test"]
    assert values["splits"]["test"]["energy"]["plot_mode"] == "scatter"
    assert np.isclose(values["splits"]["test"]["energy"]["rmse"], 0.01)


def test_gpumd_evaluation_accepts_test_only_and_optional_tensor(tmp_path):
    data = tmp_path / "nep"
    data.mkdir()
    _write_prediction_files(data, "test", tensor=None)
    result = runner.invoke(
        app,
        [
            "gpumd",
            "plot-nep-evaluation",
            str(data),
            "--output",
            str(tmp_path / "evaluation.png"),
            "--metrics",
            str(tmp_path / "evaluation.json"),
        ],
    )
    assert result.exit_code == 0, result.output
    values = json.loads((tmp_path / "evaluation.json").read_text())
    assert set(values["splits"]) == {"test"}


def test_gpumd_evaluation_draws_each_available_file_independently(tmp_path):
    np.savetxt(tmp_path / "energy_test.out", np.array([[-1.0, -1.1]]))
    np.savetxt(
        tmp_path / "force_train.out",
        np.array([[0.1, 0.2, 0.3, 0.11, 0.19, 0.31]]),
    )
    result = runner.invoke(
        app,
        [
            "gpumd",
            "plot-nep-evaluation",
            str(tmp_path),
            "--output",
            str(tmp_path / "evaluation.png"),
            "--metrics",
            str(tmp_path / "evaluation.json"),
        ],
    )
    assert result.exit_code == 0, result.output
    values = json.loads((tmp_path / "evaluation.json").read_text())
    assert set(values["splits"]["test"]) == {"energy"}
    assert set(values["splits"]["train"]) == {"force_components"}


def test_gpumd_evaluation_marks_training_only_evidence(tmp_path):
    np.savetxt(tmp_path / "energy_train.out", np.array([[-1.0, -1.1]]))
    result = runner.invoke(
        app,
        [
            "gpumd",
            "plot-nep-evaluation",
            str(tmp_path),
            "--output",
            str(tmp_path / "evaluation.png"),
            "--metrics",
            str(tmp_path / "evaluation.json"),
        ],
    )
    assert result.exit_code == 0, result.output
    values = json.loads((tmp_path / "evaluation.json").read_text())
    assert values["primary_evidence"].startswith("training set only")
    assert "只有训练集误差" in result.output


def test_gpumd_evaluation_accepts_loss_only(tmp_path):
    np.savetxt(
        tmp_path / "loss.out",
        np.array(
            [
                [100, 1.0, 0.1, 0.1, 0.5, 0.4, 0.2],
                [200, 0.5, 0.05, 0.05, 0.2, 0.2, 0.1],
            ]
        ),
    )
    plot = tmp_path / "evaluation.png"
    metrics = tmp_path / "evaluation.json"
    result = runner.invoke(
        app,
        [
            "gpumd",
            "plot-nep-evaluation",
            str(tmp_path),
            "--output",
            str(plot),
            "--metrics",
            str(metrics),
        ],
    )
    assert result.exit_code == 0, result.output
    assert plot.is_file()
    values = json.loads(metrics.read_text())
    assert values["splits"] == {}
    assert values["loss"]["rows"] == 2
    assert values["loss"]["step"] == {"first": 100.0, "last": 200.0}
    assert values["loss"]["plot_mode"] == "line"
    assert values["loss"]["series"]["Total"]["final"] == 0.5


def test_gpumd_evaluation_combines_loss_and_prediction_panels(tmp_path):
    np.savetxt(tmp_path / "loss.out", np.array([[100, 1.0], [200, 0.5]]))
    np.savetxt(tmp_path / "energy_test.out", np.array([[-1.0, -1.1]]))
    result = runner.invoke(
        app,
        [
            "gpumd",
            "plot-nep-evaluation",
            str(tmp_path),
            "--output",
            str(tmp_path / "evaluation.png"),
            "--metrics",
            str(tmp_path / "evaluation.json"),
        ],
    )
    assert result.exit_code == 0, result.output
    values = json.loads((tmp_path / "evaluation.json").read_text())
    assert "loss" in values
    assert "energy" in values["splits"]["test"]
    assert values["primary_evidence"] == "held-out test set"


def test_gpumd_evaluation_rejects_directory_without_supported_files(tmp_path):
    result = runner.invoke(
        app,
        ["gpumd", "plot-nep-evaluation", str(tmp_path)],
    )
    assert result.exit_code != 0
    assert "未找到可绘制的 NEP 输出" in result.output
