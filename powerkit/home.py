"""Central configuration and storage for PowerKit globally installed versions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from powerkit.installer import atomic_write_text, read_json_file


def default_powerkit_home(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".powerkit"


def global_config_path(home: Path | None = None) -> Path:
    return default_powerkit_home(home) / "config.json"


def releases_directory(home: Path | None = None) -> Path:
    return default_powerkit_home(home) / "releases"


def workspaces_directory(home: Path | None = None) -> Path:
    return default_powerkit_home(home) / "workspaces"


def load_global_config(home: Path | None = None) -> dict[str, Any]:
    path = global_config_path(home)
    if not path.is_file():
        return {}
    return read_json_file(path) or {}


def write_global_config(config: dict[str, Any], home: Path | None = None) -> None:
    path = global_config_path(home)
    atomic_write_text(path, json.dumps(config, indent=2) + "\n")


def get_global_default_version(home: Path | None = None) -> str | None:
    config = load_global_config(home)
    return config.get("default_version")


def set_global_default_version(version: str, home: Path | None = None) -> None:
    config = load_global_config(home)
    config["default_version"] = version
    write_global_config(config, home)


def repository_identity(target: Path) -> str:
    path_str = str(target.expanduser().resolve())
    return hashlib.sha256(path_str.encode("utf-8")).hexdigest()[:16]


def project_workspace(target: Path, home: Path | None = None) -> Path:
    return workspaces_directory(home) / f"{target.name}-{repository_identity(target)}"
