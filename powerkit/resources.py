"""Locate PowerKit's immutable distribution assets."""

from __future__ import annotations

import json
import sysconfig
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def distribution_root() -> Path:
    """Return the source checkout or installed shared-data directory."""
    source_root = Path(__file__).resolve().parents[1]
    if (source_root / "catalog.json").is_file():
        return source_root

    installed_root = (
        Path(sysconfig.get_path("data")) / "share" / "ai-engineering-powerkit"
    )
    if (installed_root / "catalog.json").is_file():
        return installed_root

    raise RuntimeError(
        "PowerKit distribution assets are missing. Reinstall the pinned PowerKit release."
    )


def read_json(relative_path: str) -> dict[str, Any]:
    path = distribution_root() / relative_path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to read PowerKit distribution data: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"PowerKit distribution data must be a JSON object: {path}")
    return payload


def catalog() -> dict[str, Any]:
    return read_json("catalog.json")


def distribution_manifest() -> dict[str, Any]:
    return read_json("manifests/powerkit.json")


def distribution_version() -> str:
    return str(catalog()["version"])
