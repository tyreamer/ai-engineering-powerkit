#!/usr/bin/env python3
"""Create a distributable ZIP after validation."""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    result = subprocess.run([sys.executable, str(ROOT / "tools/validate.py")], cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    version = catalog["version"]
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    output = dist / f"ai-engineering-powerkit-v{version}.zip"

    excluded_parts = {".git", "__pycache__", "dist", "build"}
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if any(part in excluded_parts for part in relative.parts):
                continue
            archive.write(path, Path("ai-engineering-powerkit") / relative)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
