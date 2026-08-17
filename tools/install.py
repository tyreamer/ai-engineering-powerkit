#!/usr/bin/env python3
"""Install selected PowerKit profiles into a project or user scope."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- AI-ENGINEERING-POWERKIT:START -->"
END = "<!-- AI-ENGINEERING-POWERKIT:END -->"
MANAGED_MARKER = "AI-ENGINEERING-POWERKIT-MANAGED"


class Installer:
    def __init__(self, base: Path, dry_run: bool, force: bool) -> None:
        self.base = base
        self.dry_run = dry_run
        self.force = force
        self.timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.manifest_files: list[str] = []
        self.messages: list[str] = []

    def relative_label(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.base))
        except ValueError:
            return str(path)

    def log(self, action: str, path: Path) -> None:
        message = f"{action}: {self.relative_label(path)}"
        self.messages.append(message)
        print(message)

    def backup(self, path: Path) -> None:
        if not path.exists():
            return
        backup_root = self.base / ".ai-powerkit" / "backups" / self.timestamp
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

    def preflight_skill(self, destination: Path) -> None:
        if not destination.exists() or self.force:
            return
        marker = destination / ".powerkit-origin.json"
        if not destination.is_dir() or not marker.is_file():
            raise RuntimeError(
                f"Refusing to overwrite unmanaged skill directory {destination}. "
                "Use --force only after reviewing it."
            )

    def preflight_managed_file(self, destination: Path) -> None:
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
        if MANAGED_MARKER not in text:
            raise RuntimeError(
                f"Refusing to overwrite unmanaged agent file {destination}. "
                "Use --force only after reviewing it."
            )

    def preflight_instruction(self, destination: Path) -> None:
        if not destination.exists():
            return
        if not destination.is_file():
            raise RuntimeError(f"Instruction path is not a file: {destination}")
        existing = destination.read_text(encoding="utf-8")
        start_count = existing.count(START)
        end_count = existing.count(END)
        if start_count == 0 and end_count == 0:
            return
        if start_count != 1 or end_count != 1 or existing.index(START) > existing.index(END):
            raise RuntimeError(
                f"Malformed PowerKit instruction markers in {destination}. "
                "Repair or remove the managed block before reinstalling."
            )

    def copy_file(self, source: Path, destination: Path, overwrite: bool = True) -> None:
        if destination.exists() and not overwrite:
            self.log("skip existing", destination)
            return
        if destination.exists():
            self.backup(destination)
        self.log("copy file", destination)
        self.manifest_files.append(str(destination))
        if self.dry_run:
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    def copy_managed_file(self, source: Path, destination: Path) -> None:
        source_text = source.read_text(encoding="utf-8")
        if MANAGED_MARKER not in source_text:
            raise RuntimeError(f"Managed source marker is missing from {source}")
        self.preflight_managed_file(destination)
        self.copy_file(source, destination)

    def copy_skill(self, source: Path, destination: Path, version: str) -> None:
        self.preflight_skill(destination)
        marker = destination / ".powerkit-origin.json"
        if destination.exists():
            self.backup(destination)
            self.log("replace skill", destination)
        else:
            self.log("install skill", destination)
        self.manifest_files.append(str(destination))
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

    def merge_instruction(self, destination: Path, block: str) -> None:
        self.preflight_instruction(destination)
        wrapped = f"{START}\n{block.strip()}\n{END}"
        existing = destination.read_text(encoding="utf-8") if destination.exists() else ""
        if START in existing:
            before, remainder = existing.split(START, 1)
            _, after = remainder.split(END, 1)
            updated = before.rstrip() + "\n\n" + wrapped + after
        else:
            updated = existing.rstrip()
            if updated:
                updated += "\n\n"
            updated += wrapped + "\n"
        if existing == updated:
            self.log("unchanged", destination)
            return
        if destination.exists():
            self.backup(destination)
        self.log("merge instructions", destination)
        self.manifest_files.append(str(destination))
        if self.dry_run:
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(updated, encoding="utf-8")

    def write_manifest(self, path: Path, payload: dict) -> None:
        if path.exists():
            self.backup(path)
        self.log("write manifest", path)
        if self.dry_run:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(payload)
        payload["installed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        payload["files"] = sorted(set(self.manifest_files))
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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
    if scope == "project":
        if "codex" in platforms:
            operations.append(
                (
                    base / "AGENTS.md",
                    (ROOT / "templates/instructions/AGENTS.block.md").read_text(encoding="utf-8"),
                )
            )
        if "claude" in platforms:
            operations.append(
                (
                    base / "CLAUDE.md",
                    (ROOT / "templates/instructions/CLAUDE.block.md").read_text(encoding="utf-8"),
                )
            )
        if "copilot" in platforms:
            operations.append(
                (
                    base / ".github" / "copilot-instructions.md",
                    (ROOT / "templates/instructions/copilot-instructions.block.md").read_text(
                        encoding="utf-8"
                    ),
                )
            )
    else:
        if "codex" in platforms:
            operations.append(
                (
                    base / ".codex" / "AGENTS.md",
                    (ROOT / "templates/instructions/AGENTS.block.md").read_text(encoding="utf-8"),
                )
            )
        if "claude" in platforms:
            operations.append(
                (
                    base / ".claude" / "CLAUDE.md",
                    (ROOT / "templates/instructions/CLAUDE.block.md").read_text(encoding="utf-8"),
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
        }

    operations: list[tuple[Path, Path]] = []
    skipped: list[str] = []
    for platform in sorted(platforms):
        if platform not in targets:
            skipped.append(platform)
            continue
        source_root = ROOT / "adapters" / platform / "agents"
        target_root = targets[platform]
        for source in sorted(source_root.iterdir()):
            if source.is_file():
                operations.append((source, target_root / source.name))
    return operations, skipped


def hook_operations(base: Path, platforms: set[str]) -> list[tuple[Path, Path]]:
    operations: list[tuple[Path, Path]] = []
    hook_root = base / ".ai-powerkit" / "hooks"
    for source in sorted((ROOT / "hooks").iterdir()):
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install AI Engineering PowerKit skills and optional agents."
    )
    parser.add_argument("--target", type=Path, default=Path("."))
    parser.add_argument("--scope", choices=("project", "user"), default="project")
    parser.add_argument("--profiles", default="foundation")
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

    catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    try:
        skill_names = selected_skills(catalog, csv_values(args.profiles))
    except ValueError as exc:
        parser.error(str(exc))

    platforms = set(csv_values(args.platforms))
    supported = {"codex", "claude", "copilot"}
    unknown_platforms = sorted(platforms - supported)
    if unknown_platforms:
        parser.error(f"Unknown platforms: {', '.join(unknown_platforms)}")
    if not platforms:
        parser.error("At least one platform is required.")

    if args.scope == "project":
        base = args.target.expanduser().resolve()
        if not base.is_dir():
            parser.error(f"Target directory does not exist: {base}")
        destinations = project_destinations(base, platforms)
    else:
        base = Path.home().resolve()
        destinations = user_destinations(base, platforms)

    installer = Installer(base=base, dry_run=args.dry_run, force=args.force)
    version = str(catalog["version"])

    skill_ops: list[tuple[Path, Path]] = []
    for skill_root in destinations.values():
        for name in skill_names:
            skill_ops.append((ROOT / ".agents" / "skills" / name, skill_root / name))
    instruction_ops = instruction_operations(base, args.scope, platforms)
    agent_ops, skipped_agent_platforms = (
        agent_operations(base, args.scope, platforms) if args.include_agents else ([], [])
    )
    staged_ops = hook_operations(base, platforms) if args.stage_hooks else []

    try:
        # Refuse all detectable conflicts before mutating the target. This avoids
        # half-installed toolkits when a later destination belongs to the user.
        for _, destination in skill_ops:
            installer.preflight_skill(destination)
        for destination, _ in instruction_ops:
            installer.preflight_instruction(destination)
        for _, destination in agent_ops:
            installer.preflight_managed_file(destination)

        for source, destination in skill_ops:
            installer.copy_skill(source, destination, version)
        for destination, block in instruction_ops:
            installer.merge_instruction(destination, block)
        for platform in skipped_agent_platforms:
            print(f"note: user-scope {platform} custom agents are not installed.")
        if args.scope == "user" and "copilot" in platforms:
            print(
                "note: personal Copilot instruction files are not modified; "
                "the shared ~/.agents/skills location is installed."
            )
        for source, destination in agent_ops:
            installer.copy_managed_file(source, destination)
        for source, destination in staged_ops:
            installer.copy_file(source, destination)

        manifest_path = base / ".ai-powerkit" / "install-manifest.json"
        installer.write_manifest(
            manifest_path,
            {
                "schema_version": 1,
                "toolkit": "ai-engineering-powerkit",
                "version": version,
                "scope": args.scope,
                "profiles": csv_values(args.profiles),
                "skills": skill_names,
                "platforms": sorted(platforms),
                "agents": bool(args.include_agents),
                "hooks_staged": bool(args.stage_hooks),
                "dry_run": bool(args.dry_run),
            },
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print()
    print(
        f"{'Dry run complete' if args.dry_run else 'Installation complete'}: "
        f"{len(skill_names)} skills for {', '.join(sorted(platforms))}"
    )
    if not args.stage_hooks:
        print("Hooks were not copied or enabled.")
    else:
        print("Hooks were staged but not enabled. Review docs/HOOKS.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
