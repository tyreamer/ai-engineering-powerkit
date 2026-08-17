"""Select reviewed regular files for source-derived release artifacts."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable


def git_tracked_files(root: Path) -> set[Path] | None:
    """Return reviewed source files, or None outside a Git checkout."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return {
        Path(raw.decode("utf-8"))
        for raw in result.stdout.split(b"\0")
        if raw
    }


def validate_source_file(root: Path, relative: Path, artifact: str) -> Path:
    path = root / relative
    if path.is_symlink():
        raise RuntimeError(f"refusing symlinked {artifact} source: {relative}")
    if not path.is_file():
        raise RuntimeError(f"{artifact} source is missing or not regular: {relative}")
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError(f"{artifact} source escapes repository root: {relative}") from exc
    return path


def select_distribution_files(
    root: Path,
    top_level_assets: Iterable[Path],
    asset_roots: Iterable[Path],
    tracked_files: set[Path] | None,
) -> list[Path]:
    """Select regular wheel assets, restricting Git checkouts to tracked inputs."""
    selected: list[Path] = []
    for relative in top_level_assets:
        if tracked_files is not None and relative not in tracked_files:
            raise RuntimeError(f"required wheel source is not Git-tracked: {relative}")
        validate_source_file(root, relative, "wheel")
        selected.append(relative)

    for asset_root in asset_roots:
        for path in sorted((root / asset_root).rglob("*")):
            relative = path.relative_to(root)
            if tracked_files is not None and relative not in tracked_files:
                continue
            if path.is_symlink():
                validate_source_file(root, relative, "wheel")
            if not path.is_file() or path.suffix in {".pyc", ".pyo"}:
                continue
            validate_source_file(root, relative, "wheel")
            selected.append(relative)
    return selected
