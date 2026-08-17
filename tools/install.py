#!/usr/bin/env python3
"""Backward-compatible entry point for the PowerKit installer."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from powerkit.installer import (  # noqa: E402
    confined_manifest_path,
    main,
)


if __name__ == "__main__":
    raise SystemExit(main())
