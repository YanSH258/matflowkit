"""Shared dpdata helpers loaded only by commands that need dpdata."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

PERIODIC_ORDER = [
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
    "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca",
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr",
    "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
    "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd",
    "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb",
    "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
    "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th",
    "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm",
    "Md", "No", "Lr",
]


def require_dpdata():
    try:
        import dpdata
    except ImportError as exc:
        raise RuntimeError(
            "此命令需要 dpdata；请运行 `pip install -e '.[dpdata]'`"
        ) from exc
    return dpdata


def parse_type_map(value: Optional[str], discovered: set[str]) -> list[str]:
    if value:
        names = [item.strip() for item in value.replace(",", " ").split() if item.strip()]
        if len(names) != len(set(names)):
            raise ValueError("type map 包含重复元素")
        missing = sorted(discovered - set(names))
        if missing:
            raise ValueError(f"type map 缺少元素: {missing}")
        return names
    unknown = sorted(discovered - set(PERIODIC_ORDER))
    if unknown:
        raise ValueError(f"无法自动排序未知元素: {unknown}")
    return [name for name in PERIODIC_ORDER if name in discovered]


def exact_formula(data, type_map: list[str]) -> str:
    names = list(data.data["atom_names"])
    numbers = list(data.data["atom_numbs"])
    if len(names) != len(numbers):
        raise ValueError("atom_names 与 atom_numbs 长度不一致")
    counts = dict(zip(names, numbers))
    return "".join(
        f"{name}{counts.get(name, 0)}" for name in type_map if counts.get(name, 0)
    )


def finite_labeled(data, require_virial: bool = True) -> np.ndarray:
    keys = ["cells", "coords", "energies", "forces"]
    if require_virial:
        keys.append("virials")
    missing = [key for key in keys if key not in data.data]
    if missing:
        raise ValueError(f"缺少标注数组: {missing}")
    nframes = len(data)
    mask = np.ones(nframes, dtype=bool)
    for key in keys:
        values = np.asarray(data.data[key])
        if values.shape[0] != nframes:
            raise ValueError(f"{key} 帧数不一致")
        mask &= np.isfinite(values.reshape(nframes, -1)).all(axis=1)
    return mask


def normalize(data, type_map: list[str]):
    data.apply_type_map(type_map)
    data.sort_atom_types()
    return data


def append_system(current, addition):
    if current is None:
        return addition
    current.append(addition)
    return current


def find_deepmd_systems(root: Path) -> list[Path]:
    if (root / "type.raw").is_file() and any(root.glob("set.*")):
        return [root]
    systems = []
    for type_file in root.rglob("type.raw"):
        system = type_file.parent
        if any(system.glob("set.*")):
            systems.append(system)
    return sorted(set(systems))
