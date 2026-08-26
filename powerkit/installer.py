#!/usr/bin/env python3
"""Install selected PowerKit profiles into a project or user scope."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from powerkit.resources import catalog as distribution_catalog
from powerkit.resources import distribution_manifest, distribution_root


ROOT = distribution_root()
START = "<!-- AI-ENGINEERING-POWERKIT:START -->"
END = "<!-- AI-ENGINEERING-POWERKIT:END -->"
MANAGED_MARKER = "AI-ENGINEERING-POWERKIT-MANAGED"
MANIFEST_PATH = Path(".ai-powerkit/install-manifest.json")
COMMAND_MANIFEST_PATH = ROOT / ".agents/skills/pk/references/command-manifest.json"


def has_managed_marker(text: str) -> bool:
    markers = {f"# {MANAGED_MARKER}", f"<!-- {MANAGED_MARKER} -->"}
    return any(line.strip() in markers for line in text.splitlines())


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_tree(path: Path) -> str:
    digest = hashlib.sha256()
    children = sorted(path.rglob("*"))
    for child in children:
        if child.is_symlink():
            raise RuntimeError(f"Refusing skill directory with symlinked content {child}.")
    for child in (item for item in children if item.is_file()):
        relative = child.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(sha256_file(child)))
    return digest.hexdigest()


def read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def atomic_write_text(path: Path, value: str, *, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    destination_mode = (
        mode
        if mode is not None
        else (path.stat().st_mode & 0o777 if path.is_file() else 0o644)
    )
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.chmod(temporary_path, destination_mode)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def safe_asset_path(base: Path, raw: object) -> Path | None:
    if not isinstance(raw, str) or not raw:
        return None
    relative = PurePosixPath(raw)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    candidate = base.joinpath(*relative.parts)
    current = base
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return None
    resolved = candidate.resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError:
        return None
    return candidate


def normalized_legacy_inventory(manifest: dict[str, Any]) -> set[str]:
    """Validate schema-v1 file inventories and return paths relative to their old root."""
    values: list[str] = []
    for field in ("files", "stale_files"):
        raw_values = manifest.get(field, [])
        if not isinstance(raw_values, list) or any(
            not isinstance(item, str) or not item for item in raw_values
        ):
            raise RuntimeError(f"Legacy installation manifest has an invalid {field} list.")
        values.extend(raw_values)

    absolute_entries = [Path(item) for item in values if Path(item).is_absolute()]
    legacy_root: Path | None = None
    if absolute_entries:
        root_markers = {".agents", ".claude", ".codex", ".copilot", ".github", ".ai-powerkit"}
        inferred_roots: set[Path] = set()
        for entry in absolute_entries:
            cursor = entry
            while cursor != cursor.parent:
                if cursor.name in root_markers:
                    inferred_roots.add(cursor.parent)
                    break
                cursor = cursor.parent
        if len(inferred_roots) != 1:
            raise RuntimeError("Legacy installation manifest paths do not identify one install root.")
        legacy_root = inferred_roots.pop()

    normalized: set[str] = set()
    for value in values:
        candidate = Path(value)
        if candidate.is_absolute():
            if legacy_root is None:
                raise RuntimeError("Legacy installation manifest contains an unsafe absolute path.")
            try:
                candidate = candidate.relative_to(legacy_root)
            except ValueError as exc:
                raise RuntimeError(
                    f"Legacy installation manifest entry escapes its install root: {value}"
                ) from exc
        if not candidate.parts or any(part in {".", ".."} for part in candidate.parts):
            raise RuntimeError(f"Legacy installation manifest contains an unsafe path: {value}")
        normalized.add(candidate.as_posix())
    return normalized


def ensure_managed_path(base: Path, path: Path) -> None:
    try:
        relative = path.relative_to(base)
    except ValueError as exc:
        raise RuntimeError(f"Managed path escapes the installation root: {path}") from exc
    current = base
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise RuntimeError(
                f"Refusing symlinked installation destination {current}: "
                "symlinked managed path component."
            )


def preflight_distribution_source(path: Path, *, directory: bool = False) -> None:
    """Reject missing, escaping, or symlinked distribution inputs before target mutation."""
    try:
        relative = path.relative_to(ROOT)
    except ValueError as exc:
        raise RuntimeError(f"Toolkit source escapes distribution root: {path}") from exc
    current = ROOT
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise RuntimeError(f"Toolkit source must not use a symlink: {current}")
    valid = path.is_dir() if directory else path.is_file()
    if not valid:
        kind = "directory" if directory else "file"
        raise RuntimeError(f"Toolkit source {kind} is missing: {path}")
    if directory:
        Installer.preflight_directory_contents(path)


def read_distribution_text(path: Path) -> str:
    preflight_distribution_source(path)
    return path.read_text(encoding="utf-8")


def instruction_block(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if text.count(START) != 1 or text.count(END) != 1:
        return None
    _, remainder = text.split(START, 1)
    body, _ = remainder.split(END, 1)
    return f"{START}{body}{END}"


def asset_digest(path: Path, kind: object) -> str | None:
    if kind == "skill":
        return sha256_tree(path) if path.is_dir() else None
    if kind in {"managed-file", "staged-file"}:
        return sha256_file(path) if path.is_file() else None
    if kind == "instruction-block":
        block = instruction_block(path)
        return sha256_text(block) if block is not None else None
    return None


def verify_removable_asset(base: Path, asset: dict[str, Any]) -> tuple[Path | None, str | None]:
    path = safe_asset_path(base, asset.get("path"))
    if path is None:
        return None, f"unsafe managed path {asset.get('path')!r}"
    if not path.exists():
        return path, None
    if path.is_symlink():
        return path, f"managed path was replaced by a symlink: {asset.get('path')}"
    kind = asset.get("kind")
    digest = asset_digest(path, kind)
    if digest is None or digest != asset.get("sha256"):
        return path, f"managed asset changed outside PowerKit: {asset.get('path')}"
    if kind == "skill":
        marker = read_json_file(path / ".powerkit-origin.json")
        if not marker or marker.get("source") != "ai-engineering-powerkit":
            return path, f"skill ownership marker is missing: {asset.get('path')}"
    elif kind == "managed-file":
        try:
            if not has_managed_marker(path.read_text(encoding="utf-8")):
                return path, f"managed-file marker is missing: {asset.get('path')}"
        except UnicodeDecodeError:
            return path, f"managed file is unreadable: {asset.get('path')}"
    elif kind not in {"staged-file", "instruction-block"}:
        return path, f"unknown managed asset kind {kind!r}: {asset.get('path')}"
    return path, None


@dataclass(frozen=True)
class InstallRequest:
    base: Path
    profiles: tuple[str, ...]
    platforms: frozenset[str]
    scope: str = "user"
    include_agents: bool = False
    stage_hooks: bool = False
    dry_run: bool = False
    force: bool = False
    verbose: bool = True
    prune_stale: bool = True


@dataclass(frozen=True)
class InstallResult:
    version: str
    skills: tuple[str, ...]
    platforms: tuple[str, ...]
    changed: bool
    command_invocations: tuple[tuple[str, str], ...] = ()


class Installer:
    def __init__(self, base: Path, dry_run: bool, force: bool, verbose: bool = True) -> None:
        self.base = base
        self.dry_run = dry_run
        self.force = force
        self.verbose = verbose
        self.timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        self.managed_assets: dict[str, dict[str, Any]] = {}
        self.changed = False

    def relative_label(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.base))
        except ValueError:
            return str(path)

    def log(self, action: str, path: Path) -> None:
        message = f"{action}: {self.relative_label(path)}"
        if self.verbose:
            print(message)

    def relative_path(self, path: Path) -> str:
        try:
            return path.relative_to(self.base).as_posix()
        except ValueError as exc:
            raise RuntimeError(f"Managed path escapes the installation root: {path}") from exc

    def preflight_path(self, path: Path) -> None:
        ensure_managed_path(self.base, path)

    @staticmethod
    def preflight_directory_contents(path: Path) -> None:
        """Reject descendant links before reading, hashing, copying, or backing up a tree."""
        try:
            for child in path.rglob("*"):
                if child.is_symlink():
                    raise RuntimeError(
                        f"Refusing skill directory with symlinked content {child}."
                    )
        except OSError as exc:
            raise RuntimeError(f"Cannot safely inspect managed directory {path}: {exc}") from exc

    def record_asset(
        self,
        path: Path,
        kind: str,
        digest: str | None,
        **metadata: Any,
    ) -> None:
        payload: dict[str, Any] = {"path": self.relative_path(path), "kind": kind}
        if digest is not None:
            payload["sha256"] = digest
        payload.update(metadata)
        self.managed_assets[payload["path"]] = payload

    def backup(self, path: Path) -> None:
        if not path.exists():
            return
        self.preflight_path(path)
        if path.is_dir():
            self.preflight_directory_contents(path)
        backup_root = self.base / ".ai-powerkit" / "backups" / self.timestamp
        self.preflight_path(backup_root)
        try:
            rel = path.relative_to(self.base)
        except ValueError:
            rel = Path(path.name)
        destination = backup_root / rel
        self.log("backup", destination)
        if self.dry_run:
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            shutil.copytree(path, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(path, destination)

    def remove_asset(self, asset: dict[str, Any]) -> None:
        path, error = verify_removable_asset(self.base, asset)
        if error:
            raise RuntimeError(error)
        if path is None or not path.exists():
            return
        self.backup(path)
        self.log("remove managed", path)
        self.changed = True
        if self.dry_run:
            return
        if asset.get("kind") == "instruction-block":
            text = path.read_text(encoding="utf-8")
            before, remainder = text.split(START, 1)
            _, after = remainder.split(END, 1)
            before = before.rstrip()
            after = after.lstrip()
            if before and after:
                updated = f"{before}\n\n{after}"
            else:
                updated = before or after
            if not updated and asset.get("created_file"):
                path.unlink()
            else:
                path.write_text(updated + ("\n" if updated else ""), encoding="utf-8")
        elif path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    def preflight_skill(self, destination: Path) -> None:
        self.preflight_path(destination)
        if destination.is_symlink():
            raise RuntimeError(
                f"Refusing to overwrite symlinked skill directory {destination}."
            )
        if not destination.exists():
            return
        if destination.is_dir():
            self.preflight_directory_contents(destination)
        if self.force:
            return
        marker = destination / ".powerkit-origin.json"
        if not destination.is_dir() or not marker.is_file():
            raise RuntimeError(
                f"Refusing to overwrite unmanaged skill directory {destination}. "
                "Use --force only after reviewing it."
            )
        payload = read_json_file(marker)
        if not payload or payload.get("source") != "ai-engineering-powerkit":
            raise RuntimeError(
                f"Refusing to overwrite skill with an invalid ownership marker {destination}. "
                "Use --force only after reviewing it."
            )

    def preflight_managed_file(self, destination: Path) -> None:
        if destination.is_symlink():
            raise RuntimeError(f"Refusing to overwrite symlinked agent file {destination}.")
        if not destination.exists() or self.force:
            return
        if not destination.is_file():
            raise RuntimeError(
                f"Refusing to overwrite unmanaged agent path {destination}. "
                "Use --force only after reviewing it."
            )
        try:
            text = destination.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError(
                f"Refusing to overwrite unreadable agent file {destination}. "
                "Use --force only after reviewing it."
            ) from exc
        if not has_managed_marker(text):
            raise RuntimeError(
                f"Refusing to overwrite unmanaged file {destination}. "
                "Use --force only after reviewing it."
            )

    def preflight_instruction(self, destination: Path) -> None:
        if not destination.exists():
            return
        if destination.is_symlink():
            raise RuntimeError(f"Refusing to modify symlinked instruction file {destination}.")
        if not destination.is_file():
            raise RuntimeError(f"Instruction path is not a file: {destination}")
        try:
            existing = destination.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"Instruction file is not valid UTF-8: {destination}") from exc
        start_count = existing.count(START)
        end_count = existing.count(END)
        if start_count == 0 and end_count == 0:
            return
        if start_count != 1 or end_count != 1 or existing.index(START) > existing.index(END):
            raise RuntimeError(
                f"Malformed PowerKit instruction markers in {destination}. "
                "Repair or remove the managed block before reinstalling."
            )

    def copy_file(self, source: Path, destination: Path) -> None:
        if destination.is_file() and source.read_bytes() == destination.read_bytes():
            self.log("unchanged", destination)
            self.record_asset(destination, "staged-file", sha256_file(destination))
            return
        if destination.exists():
            self.backup(destination)
        self.log("copy file", destination)
        self.changed = True
        if self.dry_run:
            return
        if destination.is_dir():
            shutil.rmtree(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        self.record_asset(destination, "staged-file", sha256_file(destination))

    def copy_managed_file(self, source: Path, destination: Path) -> None:
        source_text = source.read_text(encoding="utf-8")
        if not has_managed_marker(source_text):
            raise RuntimeError(f"Managed source marker is missing from {source}")
        self.preflight_managed_file(destination)
        if destination.is_file() and source.read_bytes() == destination.read_bytes():
            self.log("unchanged", destination)
            self.record_asset(destination, "managed-file", sha256_file(destination))
            return
        if destination.exists():
            self.backup(destination)
        self.log("copy file", destination)
        self.changed = True
        if self.dry_run:
            return
        if destination.is_dir():
            shutil.rmtree(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        self.record_asset(destination, "managed-file", sha256_file(destination))

    @staticmethod
    def skill_is_current(source: Path, destination: Path, version: str) -> bool:
        marker = read_json_file(destination / ".powerkit-origin.json")
        if marker != {
            "source": "ai-engineering-powerkit",
            "version": version,
            "skill": source.name,
        }:
            return False
        source_files = {
            child.relative_to(source).as_posix(): sha256_file(child)
            for child in source.rglob("*")
            if child.is_file()
        }
        destination_files = {
            child.relative_to(destination).as_posix(): sha256_file(child)
            for child in destination.rglob("*")
            if child.is_file() and child.name != ".powerkit-origin.json"
        }
        return source_files == destination_files

    def copy_skill(self, source: Path, destination: Path, version: str) -> None:
        self.preflight_skill(destination)
        marker = destination / ".powerkit-origin.json"
        if destination.is_dir() and self.skill_is_current(source, destination, version):
            self.log("unchanged", destination)
            self.record_asset(destination, "skill", sha256_tree(destination), skill=source.name)
            return
        if destination.exists():
            self.backup(destination)
            self.log("replace skill", destination)
        else:
            self.log("install skill", destination)
        self.changed = True
        if self.dry_run:
            return
        if destination.exists():
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        shutil.copytree(source, destination)
        marker.write_text(
            json.dumps(
                {
                    "source": "ai-engineering-powerkit",
                    "version": version,
                    "skill": source.name,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.record_asset(destination, "skill", sha256_tree(destination), skill=source.name)

    def merge_instruction(self, destination: Path, block: str) -> None:
        self.preflight_instruction(destination)
        wrapped = f"{START}\n{block.strip()}\n{END}"
        existing = destination.read_text(encoding="utf-8") if destination.exists() else ""
        created_file = not destination.exists() or existing.strip() == wrapped
        if START in existing:
            before, remainder = existing.split(START, 1)
            _, after = remainder.split(END, 1)
            prefix = before.rstrip()
            updated = (prefix + "\n\n" if prefix else "") + wrapped + after
        else:
            updated = existing.rstrip()
            if updated:
                updated += "\n\n"
            updated += wrapped + "\n"
        if existing == updated:
            self.log("unchanged", destination)
            self.record_asset(
                destination,
                "instruction-block",
                sha256_text(wrapped),
                created_file=created_file,
            )
            return
        if destination.exists():
            self.backup(destination)
        self.log("merge instructions", destination)
        self.changed = True
        if self.dry_run:
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(updated, encoding="utf-8")
        self.record_asset(
            destination,
            "instruction-block",
            sha256_text(wrapped),
            created_file=created_file,
        )

    def write_manifest(
        self,
        path: Path,
        payload: dict,
        *,
        preserved_assets: Iterable[dict[str, Any]] = (),
    ) -> None:
        if self.dry_run:
            self.log("would write manifest", path)
            return
        payload = dict(payload)
        current_assets = [self.managed_assets[key] for key in sorted(self.managed_assets)]
        combined_assets = {str(asset["path"]): dict(asset) for asset in preserved_assets}
        combined_assets.update({str(asset["path"]): asset for asset in current_assets})
        payload["managed_assets"] = [combined_assets[key] for key in sorted(combined_assets)]
        # Preserve the v1 fields for existing consumers, now using relocatable paths.
        payload["files"] = [str(asset["path"]) for asset in current_assets]
        payload["stale_files"] = sorted(
            set(combined_assets) - {str(asset["path"]) for asset in current_assets}
        )

        existing = read_json_file(path)
        now = utc_now()
        payload["installed_at"] = (
            str(existing.get("installed_at"))
            if isinstance(existing, dict) and existing.get("installed_at")
            else now
        )
        comparable_existing = dict(existing or {})
        comparable_existing.pop("updated_at", None)
        if existing is not None and comparable_existing == payload:
            self.log("unchanged", path)
            return

        payload["updated_at"] = now
        if path.exists():
            self.backup(path)
        self.log("write manifest", path)
        self.changed = True
        atomic_write_text(path, json.dumps(payload, indent=2) + "\n")


def csv_values(value: str) -> list[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def selected_skills(catalog: dict, profile_names: Iterable[str]) -> list[str]:
    names = list(profile_names)
    profiles = catalog["profiles"]
    if "all" in names:
        return sorted(item["name"] for item in catalog["skills"])
    unknown = sorted(set(names) - set(profiles))
    if unknown:
        raise ValueError(f"Unknown profiles: {', '.join(unknown)}")
    result: list[str] = []
    for profile in names:
        result.extend(profiles[profile]["skills"])
    return sorted(set(result))


def project_destinations(base: Path, platforms: set[str]) -> dict[str, Path]:
    destinations: dict[str, Path] = {}
    if platforms & {"codex", "copilot"}:
        destinations["canonical_skills"] = base / ".agents" / "skills"
    if "claude" in platforms:
        destinations["claude_skills"] = base / ".claude" / "skills"
    return destinations


def user_destinations(home: Path, platforms: set[str]) -> dict[str, Path]:
    destinations: dict[str, Path] = {}
    if platforms & {"codex", "copilot"}:
        destinations["canonical_skills"] = home / ".agents" / "skills"
    if "claude" in platforms:
        destinations["claude_skills"] = home / ".claude" / "skills"
    return destinations


def instruction_operations(
    base: Path, scope: str, platforms: set[str]
) -> list[tuple[Path, str]]:
    operations: list[tuple[Path, str]] = []
    codex_template = ROOT / "templates/instructions/AGENTS.block.md"
    claude_template = ROOT / "templates/instructions/CLAUDE.block.md"
    copilot_template = ROOT / "templates/instructions/copilot-instructions.block.md"
    if scope == "project":
        if "codex" in platforms:
            operations.append(
                (
                    base / "AGENTS.md",
                    read_distribution_text(codex_template),
                )
            )
        if "claude" in platforms:
            operations.append(
                (
                    base / "CLAUDE.md",
                    read_distribution_text(claude_template),
                )
            )
        if "copilot" in platforms:
            operations.append(
                (
                    base / ".github" / "copilot-instructions.md",
                    read_distribution_text(copilot_template),
                )
            )
    else:
        if "codex" in platforms:
            operations.append(
                (
                    base / ".codex" / "AGENTS.md",
                    read_distribution_text(codex_template),
                )
            )
        if "claude" in platforms:
            operations.append(
                (
                    base / ".claude" / "CLAUDE.md",
                    read_distribution_text(claude_template),
                )
            )
    return operations


def agent_operations(
    base: Path, scope: str, platforms: set[str]
) -> tuple[list[tuple[Path, Path]], list[str]]:
    if scope == "project":
        targets = {
            "codex": base / ".codex" / "agents",
            "claude": base / ".claude" / "agents",
            "copilot": base / ".github" / "agents",
        }
    else:
        targets = {
            "codex": base / ".codex" / "agents",
            "claude": base / ".claude" / "agents",
            "copilot": base / ".copilot" / "agents",
        }

    operations: list[tuple[Path, Path]] = []
    skipped: list[str] = []
    for platform in sorted(platforms):
        if platform not in targets:
            skipped.append(platform)
            continue
        source_root = ROOT / "adapters" / platform / "agents"
        preflight_distribution_source(source_root, directory=True)
        target_root = targets[platform]
        for source in sorted(source_root.iterdir()):
            if source.is_file():
                operations.append((source, target_root / source.name))
    return operations, skipped


def hook_operations(base: Path, platforms: set[str]) -> list[tuple[Path, Path]]:
    operations: list[tuple[Path, Path]] = []
    hook_root = base / ".ai-powerkit" / "hooks"
    source_hook_root = ROOT / "hooks"
    preflight_distribution_source(source_hook_root, directory=True)
    for source in sorted(source_hook_root.iterdir()):
        if source.is_file() and source.suffix in {".py", ".md"}:
            operations.append((source, hook_root / source.name))
    example_root = base / ".ai-powerkit" / "platform-examples"
    if "codex" in platforms:
        for filename in ("hooks.example.json", "config.example.toml"):
            operations.append(
                (ROOT / "adapters" / "codex" / filename, example_root / "codex" / filename)
            )
    if "claude" in platforms:
        operations.append(
            (
                ROOT / "adapters" / "claude" / "settings.hooks.example.json",
                example_root / "claude" / "settings.hooks.example.json",
            )
        )
    return operations


def confined_manifest_path(root: Path, value: str, label: str) -> Path:
    """Resolve a manifest path without allowing it to escape its owning root."""
    relative = Path(value)
    if relative.is_absolute() or any(part in {".", ".."} for part in relative.parts):
        raise RuntimeError(f"Invalid {label} path outside its root: {value}")
    resolved_root = root.resolve()
    candidate = resolved_root / relative
    current = resolved_root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise RuntimeError(f"Invalid {label} path uses a symlink: {value}")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError(f"Invalid {label} path outside its root: {value}") from exc
    return candidate


def load_command_manifest() -> dict[str, Any]:
    preflight_distribution_source(COMMAND_MANIFEST_PATH)
    manifest = read_json_file(COMMAND_MANIFEST_PATH)
    if not manifest or manifest.get("command") != "pk":
        raise RuntimeError(f"PowerKit command manifest is invalid: {COMMAND_MANIFEST_PATH}")
    return manifest


def command_operations(
    base: Path,
    scope: str,
    platforms: set[str],
    skill_names: set[str],
    manifest: dict[str, Any],
) -> list[tuple[Path, Path]]:
    """Return platform files needed beyond the canonical command skill."""
    if manifest.get("command") not in skill_names or scope != "project":
        return []

    operations: list[tuple[Path, Path]] = []
    adapters = manifest.get("adapters", {})
    copilot = adapters.get("copilot", {}) if isinstance(adapters, dict) else {}
    if "copilot" in platforms and isinstance(copilot, dict):
        source = copilot.get("project_prompt_source")
        destination = copilot.get("project_prompt_destination")
        if not isinstance(source, str) or not isinstance(destination, str):
            raise RuntimeError("Copilot command adapter paths are missing from the manifest")
        source_path = confined_manifest_path(ROOT, source, "command adapter source")
        destination_path = confined_manifest_path(
            base, destination, "command adapter destination"
        )
        if source_path.is_symlink() or not source_path.is_file():
            raise RuntimeError(f"Command adapter source does not exist or is unsafe: {source_path}")
        operations.append((source_path, destination_path))
    return operations


def command_invocations(
    scope: str,
    platforms: set[str],
    skill_names: set[str],
    manifest: dict[str, Any],
) -> dict[str, str]:
    if manifest.get("command") not in skill_names:
        return {}
    adapters = manifest.get("adapters")
    if not isinstance(adapters, dict):
        raise RuntimeError("Command adapters are missing from the manifest")
    result: dict[str, str] = {}
    for platform in sorted(platforms):
        adapter = adapters.get(platform)
        if not isinstance(adapter, dict):
            raise RuntimeError(f"Command adapter metadata is missing for {platform}")
        key = "user_invocation" if scope == "user" and platform == "copilot" else "invocation"
        invocation = adapter.get(key)
        if not isinstance(invocation, str) or not invocation.strip():
            raise RuntimeError(f"Command invocation is missing for {platform} {scope} scope")
        result[platform] = invocation
    return result


def _previous_asset(manifest: dict[str, Any] | None, relative_path: str) -> dict[str, Any] | None:
    if not manifest:
        return None
    assets = manifest.get("managed_assets", [])
    if not isinstance(assets, list):
        return None
    for asset in assets:
        if isinstance(asset, dict) and asset.get("path") == relative_path:
            return asset
    return None


def preflight_staged_file(
    installer: Installer,
    source: Path,
    destination: Path,
    previous_manifest: dict[str, Any] | None,
    legacy_inventory: set[str],
) -> None:
    if destination.is_symlink():
        raise RuntimeError(f"Refusing to overwrite symlinked staged file {destination}.")
    if not destination.exists() or installer.force:
        return
    if destination.is_file() and source.read_bytes() == destination.read_bytes():
        return
    relative = installer.relative_path(destination)
    if relative in legacy_inventory:
        return
    previous = _previous_asset(previous_manifest, relative)
    if (
        destination.is_file()
        and previous
        and previous.get("kind") == "staged-file"
        and previous.get("sha256") == sha256_file(destination)
    ):
        return
    raise RuntimeError(
        f"Refusing to overwrite unmanaged staged file {destination}. "
        "Use --force only after reviewing it."
    )


def execute_install(request: InstallRequest) -> InstallResult:
    """Install or synchronize one fully specified PowerKit state."""
    catalog_path = ROOT / "catalog.json"
    preflight_distribution_source(catalog_path)
    catalog = distribution_catalog()
    command_manifest = load_command_manifest()
    try:
        skill_names = selected_skills(catalog, request.profiles)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc

    supported = {"codex", "claude", "copilot"}
    unknown_platforms = sorted(set(request.platforms) - supported)
    if unknown_platforms:
        raise RuntimeError(f"Unknown platforms: {', '.join(unknown_platforms)}")
    if not request.platforms:
        raise RuntimeError("At least one platform is required.")
    if not request.profiles:
        raise RuntimeError("At least one profile is required.")
    if request.scope not in {"project", "user"}:
        raise RuntimeError(f"Unknown installation scope: {request.scope}")

    # For user scope, assets are managed relative to the provided base (usually Path.home()).
    base = request.base.expanduser().resolve()

    if request.scope == "project":
        if not base.is_dir():
            raise RuntimeError(f"Target directory does not exist: {base}")
        destinations = project_destinations(base, set(request.platforms))
    else:
        destinations = user_destinations(base, set(request.platforms))

    installer = Installer(
        base=base,
        dry_run=request.dry_run,
        force=request.force,
        verbose=request.verbose,
    )
    version = str(catalog["version"])

    skill_ops: list[tuple[Path, Path]] = []
    
    if request.scope == "user":
        from powerkit.home import releases_directory
        release_skills = releases_directory(base) / version / "skills"
        # Copy ALL selected skills to the central release
        for name in skill_names:
            skill_ops.append((ROOT / ".agents" / "skills" / name, release_skills / name))
        # Copy ONLY the thin 'pk' adapter to user platform directories
        if "pk" in skill_names:
            for skill_root in destinations.values():
                skill_ops.append((ROOT / ".agents" / "skills" / "pk", skill_root / "pk"))
    else:
        # Project scope: copy ALL selected skills to project destinations
        for skill_root in destinations.values():
            for name in skill_names:
                skill_ops.append((ROOT / ".agents" / "skills" / name, skill_root / name))
                
    instruction_ops = instruction_operations(base, request.scope, set(request.platforms))
    
    # Similarly, for agents and hooks, we only want them in the central release for user scope
    agent_ops: list[tuple[Path, Path]] = []
    skipped_agent_platforms: list[str] = []
    if request.include_agents:
        agent_ops, skipped_agent_platforms = agent_operations(base, request.scope, set(request.platforms))
            
    staged_ops: list[tuple[Path, Path]] = []
    if request.stage_hooks:
        if request.scope == "user":
            hook_root = releases_directory(base) / version / "hooks"
            source_hook_root = ROOT / "hooks"
            if source_hook_root.is_dir():
                for source in sorted(source_hook_root.iterdir()):
                    if source.is_file() and source.suffix in {".py", ".md"}:
                        staged_ops.append((source, hook_root / source.name))
        else:
            staged_ops = hook_operations(base, set(request.platforms))

    command_ops = command_operations(
        base,
        request.scope,
        set(request.platforms),
        set(skill_names),
        command_manifest,
    )
    installed_command_invocations = command_invocations(
        request.scope,
        set(request.platforms),
        set(skill_names),
        command_manifest,
    )
    from powerkit.home import releases_directory
    if request.scope == "user":
        manifest_path = releases_directory(base) / version / "install-manifest.json"
    else:
        manifest_path = base / MANIFEST_PATH
    print(f"DEBUG: execute_install saving manifest to {manifest_path}")
    installer.preflight_path(manifest_path)
    if manifest_path.exists() and not manifest_path.is_file():
        raise RuntimeError(f"Installation manifest path is not a file: {manifest_path}")
    previous_manifest = read_json_file(manifest_path)
    if manifest_path.exists() and (
        previous_manifest is None
        or previous_manifest.get("toolkit") != "ai-engineering-powerkit"
    ) and not request.force:
        raise RuntimeError(
            f"Refusing to overwrite invalid or foreign installation manifest {manifest_path}. "
            "Use --force only after reviewing it."
        )
    if previous_manifest and previous_manifest.get("toolkit") != "ai-engineering-powerkit":
        previous_manifest = None

    legacy_inventory: set[str] = set()
    if previous_manifest:
        schema_version = previous_manifest.get("schema_version")
        if schema_version not in {1, 2}:
            if request.force:
                previous_manifest = None
            else:
                raise RuntimeError(
                    f"Installation manifest has an unsupported schema: {schema_version!r}"
                )
        elif schema_version == 1:
            try:
                legacy_inventory = normalized_legacy_inventory(previous_manifest)
            except RuntimeError:
                if request.force:
                    previous_manifest = None
                    legacy_inventory = set()
                else:
                    raise
    desired_paths = {
        installer.relative_path(destination)
        for _, destination in skill_ops + agent_ops + staged_ops + command_ops
    }
    desired_paths.update(
        installer.relative_path(destination) for destination, _ in instruction_ops
    )
    stale_assets: list[dict[str, Any]] = []
    if previous_manifest and previous_manifest.get("schema_version") == 2:
        previous_assets = previous_manifest.get("managed_assets", [])
        if not isinstance(previous_assets, list) or not all(
            isinstance(asset, dict) for asset in previous_assets
        ):
            raise RuntimeError("Existing PowerKit manifest has invalid managed_assets.")
        previous_paths = [asset.get("path") for asset in previous_assets]
        if (
            not all(isinstance(path, str) and path for path in previous_paths)
            or len(set(previous_paths)) != len(previous_paths)
            or any(safe_asset_path(base, path) is None for path in previous_paths)
        ):
            raise RuntimeError("Existing PowerKit manifest has unsafe or duplicate asset paths.")
        stale_assets = [
            asset
            for asset in previous_assets
            if asset.get("path") not in desired_paths
        ]

    # Validate immutable distribution inputs and every detectable target conflict
    # before the first target mutation.
    for source, _ in skill_ops:
        preflight_distribution_source(source, directory=True)
        if not (source / "SKILL.md").is_file():
            raise RuntimeError(f"PowerKit distribution skill is missing SKILL.md: {source}")
    for source, _ in agent_ops:
        preflight_distribution_source(source)
        if not has_managed_marker(source.read_text(encoding="utf-8")):
            raise RuntimeError(f"PowerKit managed agent source is invalid: {source}")
    for source, _ in command_ops:
        preflight_distribution_source(source)
        if (
            not has_managed_marker(source.read_text(encoding="utf-8"))
        ):
            raise RuntimeError(f"PowerKit command adapter source is invalid: {source}")
    for source, _ in staged_ops:
        preflight_distribution_source(source)
    for _, destination in skill_ops + agent_ops + staged_ops + command_ops:
        installer.preflight_path(destination)
    for destination, _ in instruction_ops:
        installer.preflight_path(destination)
    for _, destination in skill_ops:
        installer.preflight_skill(destination)
    for destination, _ in instruction_ops:
        installer.preflight_instruction(destination)
    for _, destination in agent_ops + command_ops:
        installer.preflight_managed_file(destination)
    for source, destination in staged_ops:
        preflight_staged_file(
            installer,
            source,
            destination,
            previous_manifest,
            legacy_inventory,
        )
    for asset in stale_assets:
        _, error = verify_removable_asset(base, asset)
        if error:
            raise RuntimeError(
                f"Refusing to prune ambiguous stale asset: {error}. "
                "Restore it or uninstall the old selection explicitly."
            )

    for source, destination in skill_ops:
        installer.copy_skill(source, destination, version)
    for destination, block in instruction_ops:
        installer.merge_instruction(destination, block)
    for platform in skipped_agent_platforms:
        if request.verbose:
            print(f"note: user-scope {platform} custom agents are not installed.")
    if request.scope == "user" and "copilot" in request.platforms and request.verbose:
        print(
            "note: personal Copilot instruction files are not modified; "
            "the shared ~/.agents/skills location is installed."
        )
    for source, destination in agent_ops:
        installer.copy_managed_file(source, destination)
    for source, destination in command_ops:
        installer.copy_managed_file(source, destination)
    for source, destination in staged_ops:
        installer.copy_file(source, destination)
    if request.prune_stale:
        for asset in sorted(stale_assets, key=lambda item: str(item.get("path")), reverse=True):
            installer.remove_asset(asset)
    elif stale_assets and request.verbose:
        print(
            f"Warning: {len(stale_assets)} previously managed artifact(s) are now stale "
            "and were preserved. Review install-manifest.json before removing them."
        )

    preflight_distribution_source(ROOT / "manifests/powerkit.json")
    distribution = distribution_manifest()
    release = distribution.get("release", {})
    source = {
        "repository": distribution.get("repository"),
        "version": version,
        "ref": release.get("tag") if isinstance(release, dict) else None,
    }
    installer.write_manifest(
        manifest_path,
        {
            "schema_version": 2,
            "toolkit": "ai-engineering-powerkit",
            "version": version,
            "source": source,
            "scope": request.scope,
            "profiles": list(request.profiles),
            "skills": skill_names,
            "platforms": sorted(request.platforms),
            "commands": (
                [str(command_manifest["command"])]
                if command_manifest.get("command") in skill_names
                else []
            ),
            "command_adapters": installed_command_invocations,
            "agents": bool(request.include_agents),
            "hooks_staged": bool(request.stage_hooks),
        },
        preserved_assets=() if request.prune_stale else stale_assets,
    )

    return InstallResult(
        version=version,
        skills=tuple(skill_names),
        platforms=tuple(sorted(request.platforms)),
        changed=installer.changed,
        command_invocations=tuple(sorted(installed_command_invocations.items())),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install AI Engineering PowerKit skills and optional agents."
    )
    parser.add_argument("--target", type=Path, default=Path("."))
    parser.add_argument("--scope", choices=("project", "user"), default="project")
    parser.add_argument("--profiles", default="all")
    parser.add_argument("--platforms", default="codex,claude,copilot")
    parser.add_argument("--include-agents", action="store_true")
    parser.add_argument(
        "--stage-hooks",
        action="store_true",
        help="Copy hook scripts and examples without enabling them.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    platforms = set(csv_values(args.platforms))
    if args.scope == "project":
        base = args.target.expanduser().resolve()
        if not base.is_dir():
            parser.error(f"Target directory does not exist: {base}")
    else:
        base = Path.home().resolve()

    try:
        result = execute_install(
            InstallRequest(
                base=base,
                profiles=tuple(csv_values(args.profiles)),
                platforms=frozenset(platforms),
                scope=args.scope,
                include_agents=bool(args.include_agents),
                stage_hooks=bool(args.stage_hooks),
                dry_run=bool(args.dry_run),
                force=bool(args.force),
                verbose=True,
                prune_stale=False,
            )
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print()
    print(
        f"{'Dry run complete' if args.dry_run else 'Installation complete'}: "
        f"{len(result.skills)} skills for {', '.join(result.platforms)}"
    )
    if not args.stage_hooks:
        print("Hooks were not copied or enabled.")
    else:
        print("Hooks were staged but not enabled. Review docs/HOOKS.md.")
    if result.command_invocations:
        invocations = ", ".join(
            f"{platform} {invocation}"
            for platform, invocation in result.command_invocations
        )
        print(f"PowerKit command installed: {invocations}")
        if args.scope == "user" and "copilot" in platforms:
            print(
                "note: Copilot /pk prompt files are project-scoped; "
                "the user-scope pk skill remains available for automatic routing."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
