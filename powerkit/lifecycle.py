"""Safe removal of PowerKit-managed consumer assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from powerkit.installer import (
    MANIFEST_PATH,
    Installer,
    ensure_managed_path,
    read_json_file,
    selected_skills,
    verify_removable_asset,
)
from powerkit.health import expected_asset_kinds
from powerkit.resources import catalog
from powerkit.state import (
    PROJECT_CONFIG_PATH,
    load_project_config,
    settings_from_config,
)


@dataclass(frozen=True)
class UninstallResult:
    removed: tuple[str, ...]
    preserved_config: bool


def execute_uninstall(
    target: Path,
    *,
    dry_run: bool,
    purge_config: bool,
    verbose: bool,
) -> UninstallResult:
    target = target.expanduser().resolve()
    manifest_path = target / MANIFEST_PATH
    ensure_managed_path(target, manifest_path)
    manifest = read_json_file(manifest_path)
    if not manifest or manifest.get("toolkit") != "ai-engineering-powerkit":
        raise RuntimeError("No valid PowerKit installation manifest was found.")
    if manifest.get("schema_version") != 2:
        raise RuntimeError(
            "The legacy installation manifest cannot prove safe removal. "
            "Run the pinned release's `powerkit sync` first."
        )
    assets = manifest.get("managed_assets")
    if not isinstance(assets, list) or not all(isinstance(asset, dict) for asset in assets):
        raise RuntimeError("The installation manifest has invalid managed_assets.")
    paths = [asset.get("path") for asset in assets]
    if not all(isinstance(path, str) and path for path in paths) or len(set(paths)) != len(paths):
        raise RuntimeError("The installation manifest has invalid or duplicate asset paths.")
    config = load_project_config(target)
    assert config is not None
    try:
        settings = settings_from_config(config, target)
    except RuntimeError as exc:
        raise RuntimeError(f"Failed to load project settings: {exc}")
    if manifest.get("version") != settings.version:
        raise RuntimeError("Project and installation versions disagree; repair state before uninstalling.")
    expected_skills = selected_skills(catalog(), settings.profiles)
    expected_kinds = expected_asset_kinds(target, settings, expected_skills)
    manifest_kinds = {str(asset["path"]): asset.get("kind") for asset in assets}
    if manifest_kinds != expected_kinds:
        raise RuntimeError(
            "The installation manifest does not exactly match validated project state; "
            "run doctor and repair state before uninstalling."
        )
    config_path = target / PROJECT_CONFIG_PATH
    if purge_config and config_path.is_symlink():
        raise RuntimeError(
            f"Refusing to purge symlinked PowerKit project configuration: {config_path}"
        )

    # Verify every deletion target before the first mutation.
    for asset in assets:
        _, error = verify_removable_asset(target, asset)
        if error:
            raise RuntimeError(
                f"Refusing to uninstall because ownership is ambiguous: {error}. "
                "Restore or review the asset before retrying."
            )

    installer = Installer(base=target, dry_run=dry_run, force=False, verbose=verbose)
    removed: list[str] = []
    for asset in sorted(
        assets,
        key=lambda item: (str(item.get("path", "")).count("/"), str(item.get("path", ""))),
        reverse=True,
    ):
        path, _ = verify_removable_asset(target, asset)
        if path is not None and path.exists():
            removed.append(str(asset["path"]))
        installer.remove_asset(asset)

    if manifest_path.exists():
        installer.backup(manifest_path)
        installer.log("remove manifest", manifest_path)
        installer.changed = True
        if not dry_run:
            manifest_path.unlink()

    preserved_config = config_path.exists() and not purge_config
    if purge_config and config_path.exists():
        installer.backup(config_path)
        installer.log("remove project config", config_path)
        installer.changed = True
        if not dry_run:
            config_path.unlink()

    if not dry_run:
        # Only remove known empty integration directories; never recurse into user content.
        candidates = [
            target / ".codex/agents",
            target / ".claude/agents",
            target / ".claude/skills",
            target / ".github/agents",
            target / ".github/prompts",
            target / ".agents/skills",
        ]
        for directory in candidates:
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()

    return UninstallResult(
        removed=tuple(removed),
        preserved_config=preserved_config,
    )
