"""Shared DeepMD NPY dataset discovery and parsing."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class DeepMDSystem:
    """Metadata needed by both ``stat`` and ``report``."""

    path: Path
    types: np.ndarray
    type_map: list[str] | None
    atom_counts: dict[str, int]
    elements: list[str]
    composition: str
    pbc: tuple[bool, bool, bool]
    unmapped_type_ids: tuple[int, ...]

    @property
    def natoms(self) -> int:
        return int(self.types.size)


def is_system(path: Path) -> bool:
    return path.is_dir() and (path / "type.raw").is_file() and any(path.glob("set.*"))


def find_systems(root: Path) -> list[Path]:
    """Return one system at ``root`` or systems directly below it."""
    if is_system(root):
        return [root]
    if not root.is_dir():
        return []
    return [path for path in sorted(root.iterdir()) if is_system(path)]


def load_array(path: Path) -> np.ndarray:
    return np.load(path, allow_pickle=False) if path.suffix == ".npy" else np.loadtxt(path)


def read_system(path: Path) -> DeepMDSystem:
    types = np.atleast_1d(np.loadtxt(path / "type.raw", dtype=int)).reshape(-1)
    if types.size == 0 or np.any(types < 0):
        raise ValueError(f"type.raw 无有效的非负类型编号: {path}")

    type_map_path = path / "type_map.raw"
    type_map = type_map_path.read_text().split() if type_map_path.is_file() else None
    counts = Counter(int(value) for value in types)
    atom_counts: dict[str, int] = {}
    unmapped = []
    for type_id in sorted(counts):
        if type_map is not None and type_id < len(type_map):
            label = type_map[type_id]
        else:
            label = f"type_{type_id}"
            if type_map is not None:
                unmapped.append(type_id)
        atom_counts[label] = counts[type_id]
    composition = "".join(
        f"{label}{count if count != 1 else ''}" for label, count in atom_counts.items()
    )
    return DeepMDSystem(
        path=path,
        types=types,
        type_map=type_map,
        atom_counts=atom_counts,
        elements=list(atom_counts),
        composition=composition,
        pbc=(False, False, False) if (path / "nopbc").exists() else (True, True, True),
        unmapped_type_ids=tuple(unmapped),
    )


def set_directories(system: DeepMDSystem) -> list[Path]:
    return [path for path in sorted(system.path.glob("set.*")) if path.is_dir()]


def reshape_frames(array: np.ndarray, nframes: int, width: int, label: str) -> np.ndarray:
    if array.size != nframes * width:
        raise ValueError(
            f"{label} 大小不匹配: 得到 {array.size} 个数，应为 {nframes * width}"
        )
    return array.reshape(nframes, width)
