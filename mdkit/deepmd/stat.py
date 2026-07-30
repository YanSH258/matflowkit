"""mfk deepmd stat：统计 DeePMD raw/npy 格式数据集（纯 numpy 实现）。"""

import json
from collections import Counter
from pathlib import Path

import numpy as np
import typer


def _is_system(d: Path) -> bool:
    return d.is_dir() and (d / "type.raw").is_file() and any(d.glob("set.*"))


def find_systems(root: Path) -> list:
    """DIR 本身是单个 system，或其每个子目录是一个 system。"""
    if _is_system(root):
        return [root]
    return [d for d in sorted(root.iterdir()) if _is_system(d)]


def _load_array(p: Path) -> np.ndarray:
    return np.load(p) if p.suffix == ".npy" else np.loadtxt(p)


def stat_system(sysdir: Path) -> dict:
    """统计单个 DeePMD system。"""
    types = np.atleast_1d(np.loadtxt(sysdir / "type.raw", dtype=int))
    natoms = len(types)

    type_map = None
    tmap_file = sysdir / "type_map.raw"
    if tmap_file.is_file():
        type_map = tmap_file.read_text().split()

    counts = Counter(int(t) for t in types)
    atom_counts = {}
    for t in sorted(counts):
        label = type_map[t] if type_map and t < len(type_map) else f"type_{t}"
        atom_counts[label] = counts[t]

    nframes = 0
    e_min, e_max = np.inf, -np.inf
    f_min, f_max = np.inf, -np.inf
    for setdir in sorted(sysdir.glob("set.*")):
        energy = _load_array(setdir / "energy.npy").reshape(-1)
        force = np.abs(_load_array(setdir / "force.npy").reshape(energy.size, -1))
        nframes += energy.size
        e_min = min(e_min, float(energy.min()))
        e_max = max(e_max, float(energy.max()))
        f_min = min(f_min, float(force.min()))
        f_max = max(f_max, float(force.max()))

    return {
        "path": str(sysdir),
        "nframes": nframes,
        "natoms": natoms,
        "atom_counts": atom_counts,
        "energy_range": [e_min, e_max],
        "force_abs_range": [f_min, f_max],
    }


def stat(
    dir: Path = typer.Argument(Path("."), help="数据集根目录（或其本身即单个 system）"),
    json_out: bool = typer.Option(False, "--json", help="以 JSON 格式输出"),
):
    """统计 DeePMD raw/npy 数据集：system 数、frame/原子数、元素计数、能量与力的范围。"""
    if not dir.is_dir():
        typer.secho(f"错误: 目录不存在: {dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    systems = find_systems(dir)
    if not systems:
        typer.secho(
            f"错误: 在 {dir} 下未找到 DeePMD 数据（需要 type.raw + set.*/ 目录）",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    results = [stat_system(s) for s in systems]
    summary = {
        "n_systems": len(results),
        "total_frames": sum(r["nframes"] for r in results),
        "energy_range": [
            min(r["energy_range"][0] for r in results),
            max(r["energy_range"][1] for r in results),
        ],
        "force_abs_range": [
            min(r["force_abs_range"][0] for r in results),
            max(r["force_abs_range"][1] for r in results),
        ],
        "systems": results,
    }

    if json_out:
        typer.echo(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    typer.echo(f"system 数量: {summary['n_systems']}（共 {summary['total_frames']} 帧）")
    for r in results:
        typer.echo(f"\n[{r['path']}]")
        typer.echo(f"  frame 数: {r['nframes']}    原子数: {r['natoms']}")
        counts = ", ".join(f"{k}: {v}" for k, v in r["atom_counts"].items())
        typer.echo(f"  各元素原子计数: {counts}")
        typer.echo(f"  能量范围: [{r['energy_range'][0]:.6f}, {r['energy_range'][1]:.6f}]")
        typer.echo(f"  力分量绝对值范围: [{r['force_abs_range'][0]:.6f}, {r['force_abs_range'][1]:.6f}]")
    typer.echo(f"\n整体能量范围: [{summary['energy_range'][0]:.6f}, {summary['energy_range'][1]:.6f}]")
    typer.echo(
        f"整体力分量绝对值范围: [{summary['force_abs_range'][0]:.6f}, {summary['force_abs_range'][1]:.6f}]"
    )
