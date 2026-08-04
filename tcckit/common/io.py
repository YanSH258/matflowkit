"""Small reusable I/O helpers for TCCKit commands."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable


def ensure_empty_output(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"输出目录非空，请使用新的目录: {path}")
    path.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_sha256_manifest(root: Path, skip: Iterable[str] = ()) -> None:
    skipped = set(skip) | {"SHA256SUMS.csv"}
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name not in skipped:
            rows.append(
                {
                    "relative_path": str(path.relative_to(root)),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    write_csv(root / "SHA256SUMS.csv", rows)
