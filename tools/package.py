#!/usr/bin/env python3
"""Create a distributable ZIP after validation."""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tracked_release_files() -> list[Path]:
    """Return reviewed Git-tracked regular files and reject link-based escapes."""
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git ls-files failed: {message or 'unknown error'}")

    files: list[Path] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = Path(raw.decode("utf-8"))
        path = ROOT / relative
        if path.is_symlink():
            raise RuntimeError(f"refusing tracked symlink in release archive: {relative}")
        if not path.is_file():
            raise RuntimeError(f"tracked release file is missing or not regular: {relative}")
        try:
            path.resolve().relative_to(ROOT)
        except ValueError as exc:
            raise RuntimeError(f"release file escapes repository root: {relative}") from exc
        files.append(path)
    if not files:
        raise RuntimeError("no tracked release files found")
    return sorted(files, key=lambda path: str(path.relative_to(ROOT)))


def main() -> int:
    result = subprocess.run([sys.executable, str(ROOT / "tools/validate.py")], cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    version = catalog["version"]
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    output = dist / f"ai-engineering-powerkit-v{version}.zip"

    try:
        files = tracked_release_files()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = path.relative_to(ROOT)
            archive.write(path, Path("ai-engineering-powerkit") / relative)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
