"""Reusable parsers for CP2K text outputs containing energies and forces."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np


HARTREE_TO_EV = 27.211386245988
BOHR_TO_ANGSTROM = 0.529177210903
HARTREE_PER_BOHR_TO_EV_PER_ANGSTROM = HARTREE_TO_EV / BOHR_TO_ANGSTROM
FLOAT = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
ENERGY_PATTERN = re.compile(
    rf"^\s*ENERGY\|\s+Total FORCE_EVAL.*?energy "
    rf"\[(?:hartree|a\.u\.)\]\s*:?\s+({FLOAT})",
    re.MULTILINE,
)
FORCE_PATTERN = re.compile(
    rf"^\s*FORCES\|\s+(\d+)\s+({FLOAT})\s+({FLOAT})\s+({FLOAT})(?:\s+{FLOAT})?",
)
TABLE_FORCE_PATTERN = re.compile(
    rf"^\s*(\d+)\s+\d+\s+\S+\s+({FLOAT})\s+({FLOAT})\s+({FLOAT})\s*$"
)
CELL_PATTERN = re.compile(
    rf"^\s*CELL\|\s+Vector\s+([abc])\s+\[angstrom\]:\s+"
    rf"({FLOAT})\s+({FLOAT})\s+({FLOAT})",
    re.MULTILINE,
)


def _number(value: str) -> float:
    return float(value.replace("D", "E").replace("d", "e"))


def force_blocks(text: str) -> list[np.ndarray]:
    """Return every contiguous CP2K atomic-force block found in an output."""
    blocks: list[list[list[float]]] = []
    current: list[list[float]] = []
    expected_index = 1
    table_active = False
    for line in text.splitlines():
        if "ATOMIC FORCES in" in line:
            if current:
                blocks.append(current)
            current = []
            expected_index = 1
            table_active = True
            continue
        if table_active:
            if "SUM OF ATOMIC FORCES" in line:
                if current:
                    blocks.append(current)
                current = []
                expected_index = 1
                table_active = False
                continue
            table_match = TABLE_FORCE_PATTERN.match(line)
            if table_match:
                atom_index = int(table_match.group(1))
                if atom_index != expected_index:
                    current = []
                    expected_index = 1
                    table_active = False
                    continue
                current.append(
                    [_number(table_match.group(i)) for i in (2, 3, 4)]
                )
                expected_index += 1
                continue
        match = FORCE_PATTERN.match(line)
        if not match:
            continue
        atom_index = int(match.group(1))
        if atom_index == 1:
            if current:
                blocks.append(current)
            current = []
            expected_index = 1
        if atom_index != expected_index:
            current = []
            expected_index = 1
            if atom_index != 1:
                continue
        current.append([_number(match.group(i)) for i in (2, 3, 4)])
        expected_index += 1
    if current and not table_active:
        blocks.append(current)
    return [
        np.asarray(block, dtype=float)
        * HARTREE_PER_BOHR_TO_EV_PER_ANGSTROM
        for block in blocks
        if block
    ]


def parse_cp2k_output(path: Path) -> dict:
    """Parse completion, SCF, energy, force, and cell evidence from CP2K."""
    text = path.read_text(errors="replace")
    energy_hartree = [_number(value) for value in ENERGY_PATTERN.findall(text)]
    blocks = force_blocks(text)
    cell_vectors: dict[str, list[float]] = {}
    for match in CELL_PATTERN.finditer(text):
        cell_vectors[match.group(1)] = [
            _number(match.group(2)),
            _number(match.group(3)),
            _number(match.group(4)),
        ]
    cell = (
        np.asarray(
            [cell_vectors["a"], cell_vectors["b"], cell_vectors["c"]],
            dtype=float,
        )
        if set(cell_vectors) == {"a", "b", "c"}
        else None
    )
    last_forces = blocks[-1] if blocks else None
    final_energy_eV = (
        energy_hartree[-1] * HARTREE_TO_EV if energy_hartree else None
    )
    final_force_max = (
        float(np.linalg.norm(last_forces, axis=1).max())
        if last_forces is not None
        else None
    )
    converged = text.count("SCF run converged")
    not_converged = text.count("SCF run NOT converged")
    completed = "PROGRAM ENDED AT" in text
    passed = bool(
        completed
        and converged > 0
        and not_converged == 0
        and final_energy_eV is not None
        and last_forces is not None
        and cell is not None
    )
    return {
        "output": str(path.resolve()),
        "completed": completed,
        "scf_converged_runs": converged,
        "scf_not_converged_runs": not_converged,
        "energy_records": len(energy_hartree),
        "final_energy_eV": final_energy_eV,
        "force_blocks": len(blocks),
        "final_force_atoms": 0 if last_forces is None else len(last_forces),
        "final_max_force_eV_A": final_force_max,
        "cell_found": cell is not None,
        "status": "PASS" if passed else "INCOMPLETE",
        "_forces": last_forces,
        "_cell": cell,
    }
