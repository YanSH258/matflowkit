"""Shared helpers for DPA4 commands."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import numpy as np


DEFAULT_MODEL = Path.home() / "dpa4" / "Neo-MPtrj" / "model.pt"


def resolve_model(model: Optional[Path]) -> Path:
    """Resolve --model, DPA4_MODEL, then the user's conventional model path."""
    if model is not None:
        resolved = model.expanduser().resolve()
    elif os.environ.get("DPA4_MODEL"):
        resolved = Path(os.environ["DPA4_MODEL"]).expanduser().resolve()
    else:
        resolved = DEFAULT_MODEL.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(
            f"DPA4 模型不存在: {resolved}。请使用 --model 或设置 DPA4_MODEL"
        )
    return resolved


def require_dependencies(use_d3: bool = True) -> None:
    """Raise an actionable error when optional DPA4 dependencies are absent."""
    missing = []
    for module in ("ase", "deepmd"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if use_d3:
        try:
            __import__("dftd3")
        except ImportError:
            missing.append("dftd3")
    if missing:
        raise RuntimeError(
            "缺少 DPA4 运行依赖: "
            + ", ".join(missing)
            + "。请运行 pip install -e '.[dpa4]'"
        )


def build_calculator(model: Path, use_d3: bool = True):
    """Build a DPA4 calculator, optionally augmented with PBE-D3(BJ)."""
    require_dependencies(use_d3)
    from deepmd.calculator import DP

    try:
        calculator = DP(model=str(model), nlist_backend="auto")
    except Exception as exc:
        raise RuntimeError(
            "DPA4 模型加载失败。请确认正在使用兼容的 dpa4/deepmd/PyTorch "
            f"环境。原始错误: {exc}"
        ) from exc
    if use_d3:
        from dftd3.ase import DFTD3

        calculator = DFTD3(method="pbe", damping="d3bj").add_calculator(
            calculator
        )
    return calculator


def read_fixed_indices(path: Optional[Path], atom_count: int) -> list[int]:
    """Read one-based atom indices and return validated zero-based indices."""
    if path is None:
        return []
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"固定原子文件不存在: {resolved}")
    try:
        one_based = [int(token) for token in resolved.read_text().split()]
    except ValueError as exc:
        raise ValueError(f"固定原子文件包含非整数内容: {resolved}") from exc
    if not one_based:
        raise ValueError(f"固定原子文件为空: {resolved}")
    if min(one_based) < 1 or max(one_based) > atom_count:
        raise ValueError(f"固定原子编号必须位于 1 到 {atom_count} 之间")
    if len(set(one_based)) != len(one_based):
        raise ValueError("固定原子文件包含重复编号")
    return [index - 1 for index in one_based]


def maximum_force(forces: np.ndarray) -> float:
    """Return the maximum Cartesian vector norm from an ASE force array."""
    values = np.asarray(forces, dtype=float)
    if values.size == 0:
        return 0.0
    return float(np.linalg.norm(values.reshape(-1, 3), axis=1).max())
