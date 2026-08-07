"""Inspect the local TCCT installation and optional runtime resources."""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import sys
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, Optional

import typer

from tcct import __version__


OPTIONAL_DEPENDENCIES = (
    ("dpdata", "dpdata", "dpdata"),
    ("CP2KData", "cp2kdata", "cp2kdata"),
    ("ASE", "ase", "ase"),
    ("pymatgen", "pymatgen", "pymatgen"),
    ("matplotlib", "matplotlib", "matplotlib"),
    ("DeepMD-kit", "deepmd", "deepmd-kit"),
    ("dftd3", "dftd3", "dftd3"),
)


def _dependency_status(module: str, distribution: str) -> Dict[str, Optional[str]]:
    try:
        available = importlib.util.find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        available = False
    version: Optional[str] = None
    if available:
        try:
            version = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            version = None
    return {
        "status": "installed" if available else "not_installed",
        "version": version,
    }


def _resource_status(environment: str, suffix: str) -> Dict[str, Any]:
    raw = os.environ.get(environment)
    if raw is None or not raw.strip():
        return {"status": "unset", "path": None, "files": 0}
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        return {"status": "missing", "path": str(path), "files": 0}
    count = sum(
        1
        for candidate in path.iterdir()
        if candidate.is_file() and candidate.suffix.lower() == suffix
    )
    return {
        "status": "ready" if count else "empty",
        "path": str(path),
        "files": count,
    }


def inspect_environment() -> Dict[str, Any]:
    """Return factual installation, dependency, and ABACUS resource status."""
    executable = shutil.which("tcct")
    dependencies = {
        label: _dependency_status(module, distribution)
        for label, module, distribution in OPTIONAL_DEPENDENCIES
    }
    return {
        "tcct_version": __version__,
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
        },
        "tcct_executable": executable,
        "dependencies": dependencies,
        "abacus_resources": {
            "pseudopotentials": _resource_status("ABACUS_PP_PATH", ".upf"),
            "orbitals": _resource_status("ABACUS_ORB_PATH", ".orb"),
        },
    }


def _display_status(item: Dict[str, Any]) -> str:
    status = item["status"]
    if status == "installed":
        return item.get("version") or "installed"
    return status


def doctor(
    json_output: bool = typer.Option(False, "--json", help="输出 JSON，便于保存或接入脚本"),
):
    """检查 TCCT、可选 Python 依赖和 ABACUS 资源目录。"""
    result = inspect_environment()
    if json_output:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
        return

    typer.echo(f"TCCT       {result['tcct_version']}")
    typer.echo(f"Python           {result['python']['version']}")
    typer.echo(f"Python 路径      {result['python']['executable']}")
    typer.echo(f"tcct 路径         {result['tcct_executable'] or 'PATH 中未找到'}")
    typer.echo("\n可选依赖")
    for label, item in result["dependencies"].items():
        typer.echo(f"{label:<17} {_display_status(item)}")

    typer.echo("\nABACUS 资源")
    resources = result["abacus_resources"]
    for label, environment, item in (
        ("Pseudopotentials", "ABACUS_PP_PATH", resources["pseudopotentials"]),
        ("Orbitals", "ABACUS_ORB_PATH", resources["orbitals"]),
    ):
        detail = item["path"] or environment
        if item["status"] == "ready":
            detail = f"{detail} ({item['files']} files)"
        typer.echo(f"{label:<17} {item['status']}: {detail}")
