from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


class AgentOnboardingTests(unittest.TestCase):
    maxDiff = None

    def run_powerkit(self, *args: str, cwd: Path | None = None):
        return subprocess.run(
            [PYTHON, "-m", "powerkit", *args],
            cwd=cwd or ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )

    def init(self, target: Path, platforms: str = "codex"):
        result = self.run_powerkit(
            "init",
            "--target",
            str(target),
            "--platforms",
            platforms,
            "--yes",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    @staticmethod
    def file_snapshot(target: Path) -> dict[str, tuple[bytes, int]]:
        return {
            path.relative_to(target).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in target.rglob("*")
            if path.is_file()
        }

    def test_distribution_contract_is_agent_discoverable(self) -> None:
        distribution = json.loads(
            (ROOT / "manifests/powerkit.json").read_text(encoding="utf-8")
        )
        catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
        bootstrap = (ROOT / distribution["bootstrap"]).read_text(encoding="utf-8")
        self.assertEqual(distribution["powerkit_version"], catalog["version"])
        self.assertEqual(distribution["release"]["tag"], f"v{catalog['version']}")
        self.assertEqual(
            set(distribution["supported_platforms"]), {"codex", "claude", "copilot"}
        )
        self.assertEqual(distribution["default_setup"]["profiles"], ["all"])
        self.assertEqual(len(catalog["skills"]), 24)
        self.assertIn("python3 -m powerkit init", bootstrap)
        self.assertIn("Never recreate", bootstrap)
        self.assertIn("Continue the user's original task", bootstrap)

    def test_noninteractive_init_requires_explicit_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            result = self.run_powerkit(
                "init", "--target", str(target), "--platforms", "codex"
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("requires `--yes`", result.stderr)
            self.assertFalse((target / ".ai-powerkit").exists())

    def test_fresh_bootstrap_all_platform_combinations(self) -> None:
        combinations = (
            "codex",
            "claude",
            "copilot",
            "codex,claude",
            "codex,claude,copilot",
        )
        for platforms in combinations:
            with self.subTest(platforms=platforms), tempfile.TemporaryDirectory() as temp:
                target = Path(temp)
                self.init(target, platforms)
                configured = set(platforms.split(","))
                self.assertEqual(
                    (target / "AGENTS.md").exists(), "codex" in configured
                )
                self.assertEqual(
                    (target / "CLAUDE.md").exists(), "claude" in configured
                )
                self.assertEqual(
                    (target / ".github/copilot-instructions.md").exists(),
                    "copilot" in configured,
                )
                self.assertEqual(
                    (target / ".agents/skills/pk/SKILL.md").exists(),
                    bool(configured & {"codex", "copilot"}),
                )
                self.assertEqual(
                    (target / ".claude/skills/pk/SKILL.md").exists(),
                    "claude" in configured,
                )
                doctor = self.run_powerkit("doctor", "--target", str(target), "--json")
                self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
                self.assertTrue(json.loads(doctor.stdout)["healthy"])
                manifest = json.loads(
                    (target / ".ai-powerkit/install-manifest.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(manifest["profiles"], ["all"])
                self.assertEqual(len(manifest["skills"]), 24)

    def test_current_install_sync_is_byte_and_mtime_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, "codex,claude")
            before = self.file_snapshot(target)
            result = self.run_powerkit("sync", "--target", str(target))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("already current", result.stdout)
            self.assertEqual(self.file_snapshot(target), before)
            self.assertFalse((target / ".ai-powerkit/backups").exists())

    def test_init_never_changes_an_existing_version_pin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, "codex")
            config_path = target / ".ai-powerkit/project.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["powerkit"]["version"] = "0.1.0"
            config["powerkit"]["source"]["version"] = "0.1.0"
            config["powerkit"]["source"]["ref"] = "v0.1.0"
            config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            before = self.file_snapshot(target)
            result = self.run_powerkit(
                "init",
                "--target",
                str(target),
                "--platforms",
                "codex",
                "--yes",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("will not change that pin", result.stderr)
            self.assertEqual(self.file_snapshot(target), before)

    def test_doctor_rejects_incomplete_manifest_even_when_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, "codex")
            manifest_path = target / ".ai-powerkit/install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["managed_assets"] = [
                asset
                for asset in manifest["managed_assets"]
                if asset["path"] != ".agents/skills/pk"
            ]
            manifest["files"] = [
                path for path in manifest["files"] if path != ".agents/skills/pk"
            ]
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            doctor = self.run_powerkit("doctor", "--target", str(target), "--json")
            self.assertEqual(doctor.returncode, 1)
            report = json.loads(doctor.stdout)
            managed = next(check for check in report["checks"] if check["name"] == "managed assets")
            self.assertFalse(managed["ok"])
            self.assertIn("manifest omits expected assets", managed["detail"])

    def test_unmanaged_conflict_is_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            unmanaged = target / ".agents/skills/prompt-preflight"
            unmanaged.mkdir(parents=True)
            (unmanaged / "SKILL.md").write_text("consumer owned\n", encoding="utf-8")
            before = self.file_snapshot(target)
            result = self.run_powerkit(
                "init",
                "--target",
                str(target),
                "--platforms",
                "codex",
                "--yes",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Refusing to overwrite unmanaged skill", result.stderr)
            self.assertEqual(self.file_snapshot(target), before)
            self.assertFalse((target / "AGENTS.md").exists())
            self.assertFalse((target / ".ai-powerkit/project.json").exists())

    def test_marker_substring_does_not_claim_an_unmanaged_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            unmanaged = target / ".codex/agents/evidence-explorer.toml"
            unmanaged.parent.mkdir(parents=True)
            unmanaged.write_text(
                "description = 'mentions AI-ENGINEERING-POWERKIT-MANAGED only'\n",
                encoding="utf-8",
            )
            before = self.file_snapshot(target)

            result = self.run_powerkit(
                "init",
                "--target",
                str(target),
                "--platforms",
                "codex",
                "--yes",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("Refusing to overwrite unmanaged file", result.stderr)
            self.assertEqual(self.file_snapshot(target), before)
            self.assertFalse((target / "AGENTS.md").exists())
            self.assertFalse((target / ".ai-powerkit/project.json").exists())

    def test_foreign_install_manifest_is_an_atomic_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            manifest = target / ".ai-powerkit/install-manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text('{"toolkit": "another-tool"}\n', encoding="utf-8")
            before = self.file_snapshot(target)
            result = self.run_powerkit(
                "init",
                "--target",
                str(target),
                "--platforms",
                "codex",
                "--yes",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("foreign installation manifest", result.stderr)
            self.assertEqual(self.file_snapshot(target), before)
            self.assertFalse((target / "AGENTS.md").exists())

    def test_non_utf8_install_manifest_is_an_atomic_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            manifest = target / ".ai-powerkit/install-manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_bytes(b"\xff\xfe")
            before = self.file_snapshot(target)
            result = self.run_powerkit(
                "init",
                "--target",
                str(target),
                "--platforms",
                "codex",
                "--yes",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("invalid or foreign installation manifest", result.stderr)
            self.assertEqual(self.file_snapshot(target), before)
            self.assertFalse((target / "AGENTS.md").exists())

    def test_team_clone_reconstructs_from_committed_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as source_temp, tempfile.TemporaryDirectory() as clone_temp:
            source = Path(source_temp)
            clone = Path(clone_temp)
            self.init(source, "claude,copilot")
            clone_config = clone / ".ai-powerkit/project.json"
            clone_config.parent.mkdir(parents=True)
            shutil.copy2(source / ".ai-powerkit/project.json", clone_config)

            result = self.run_powerkit("sync", "--target", str(clone))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((clone / ".claude/skills/pk/SKILL.md").is_file())
            self.assertTrue((clone / ".agents/skills/pk/SKILL.md").is_file())
            self.assertTrue((clone / ".ai-powerkit/install-manifest.json").is_file())
            doctor = self.run_powerkit("doctor", "--target", str(clone))
            self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)

    def test_sync_upgrades_legacy_manifest_without_reconstructing_options(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, "codex,claude")
            manifest_path = target / ".ai-powerkit/install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["schema_version"] = 1
            manifest.pop("managed_assets")
            manifest["files"] = [str(target / path) for path in manifest["files"]]
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            result = self.run_powerkit("sync", "--target", str(target))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            upgraded = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(upgraded["schema_version"], 2)
            self.assertTrue(upgraded["managed_assets"])
            self.assertTrue(all(not Path(path).is_absolute() for path in upgraded["files"]))
            doctor = self.run_powerkit("doctor", "--target", str(target))
            self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)

    def test_legacy_manifest_never_silently_prunes_unproven_old_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, "codex")
            config_path = target / ".ai-powerkit/project.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["powerkit"]["profiles"] = ["foundation"]
            config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            manifest_path = target / ".ai-powerkit/install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["schema_version"] = 1
            manifest.pop("managed_assets")
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            result = self.run_powerkit("sync", "--target", str(target))
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertTrue((target / ".agents/skills/implementation-planner").is_dir())
            doctor = self.run_powerkit("doctor", "--target", str(target), "--json")
            report = json.loads(doctor.stdout)
            managed = next(check for check in report["checks"] if check["name"] == "managed assets")
            self.assertIn("owned assets are not tracked", managed["detail"])

    def test_update_repairs_outdated_state_and_preserves_consumer_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, "codex")
            instruction = target / "AGENTS.md"
            instruction.write_text(
                "# Consumer rules\n\n" + instruction.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            config_path = target / ".ai-powerkit/project.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["powerkit"]["version"] = "0.1.0"
            config["powerkit"]["source"]["version"] = "0.1.0"
            config["powerkit"]["source"]["ref"] = "v0.1.0"
            config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

            manifest_path = target / ".ai-powerkit/install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["version"] = "0.1.0"
            manifest["source"]["version"] = "0.1.0"
            manifest["source"]["ref"] = "v0.1.0"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            for marker_path in target.glob(".agents/skills/*/.powerkit-origin.json"):
                marker = json.loads(marker_path.read_text(encoding="utf-8"))
                marker["version"] = "0.1.0"
                marker_path.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")

            status = self.run_powerkit("status", "--target", str(target), "--json")
            self.assertEqual(status.returncode, 1)
            self.assertEqual(json.loads(status.stdout)["state"], "update-available")

            result = self.run_powerkit(
                "update", "--target", str(target), "--version", "0.3.0", "--yes"
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("# Consumer rules", instruction.read_text(encoding="utf-8"))
            updated_config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(updated_config["powerkit"]["version"], "0.3.0")
            doctor = self.run_powerkit("doctor", "--target", str(target))
            self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)

    def test_sync_prunes_only_stale_managed_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, "codex")
            custom = target / ".agents/skills/consumer-skill/SKILL.md"
            custom.parent.mkdir(parents=True)
            custom.write_text("consumer owned\n", encoding="utf-8")
            config_path = target / ".ai-powerkit/project.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["powerkit"]["profiles"] = ["foundation"]
            config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

            result = self.run_powerkit("sync", "--target", str(target))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(custom.is_file())
            self.assertFalse((target / ".agents/skills/implementation-planner").exists())
            self.assertTrue((target / ".agents/skills/pk").is_dir())
            doctor = self.run_powerkit("doctor", "--target", str(target))
            self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)

    def test_uninstall_dry_run_and_managed_only_removal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, "codex")
            custom = target / ".agents/skills/consumer-skill/SKILL.md"
            custom.parent.mkdir(parents=True)
            custom.write_text("consumer owned\n", encoding="utf-8")
            before = self.file_snapshot(target)

            preview = self.run_powerkit(
                "uninstall", "--target", str(target), "--dry-run"
            )
            self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
            self.assertEqual(self.file_snapshot(target), before)

            result = self.run_powerkit(
                "uninstall", "--target", str(target), "--yes"
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(custom.is_file())
            self.assertTrue((target / ".ai-powerkit/project.json").is_file())
            self.assertFalse((target / ".ai-powerkit/install-manifest.json").exists())
            self.assertFalse((target / "AGENTS.md").exists())

    def test_uninstall_conflict_refuses_all_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, "codex")
            managed = target / ".codex/agents/evidence-explorer.toml"
            managed.write_text(
                managed.read_text(encoding="utf-8") + "\n# consumer change\n",
                encoding="utf-8",
            )
            before = self.file_snapshot(target)
            result = self.run_powerkit(
                "uninstall", "--target", str(target), "--yes"
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("ownership is ambiguous", result.stderr)
            self.assertEqual(self.file_snapshot(target), before)

    def test_install_refuses_symlinked_instruction_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside_temp:
            target = Path(temp)
            outside = Path(outside_temp) / "rules.md"
            outside.write_text("# Outside rules\n", encoding="utf-8")
            (target / "AGENTS.md").symlink_to(outside)
            result = self.run_powerkit(
                "init",
                "--target",
                str(target),
                "--platforms",
                "codex",
                "--yes",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("symlinked managed path component", result.stderr)
            self.assertEqual(outside.read_text(encoding="utf-8"), "# Outside rules\n")
            self.assertFalse((target / ".ai-powerkit/project.json").exists())

    def test_install_refuses_symlinked_state_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside_temp:
            target = Path(temp)
            outside = Path(outside_temp)
            (target / ".ai-powerkit").symlink_to(outside, target_is_directory=True)
            result = self.run_powerkit(
                "init",
                "--target",
                str(target),
                "--platforms",
                "codex",
                "--yes",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("symlinked managed path component", result.stderr)
            self.assertEqual(list(outside.iterdir()), [])
            self.assertFalse((target / "AGENTS.md").exists())

    def test_uninstall_rejects_manifest_path_traversal_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, "codex")
            manifest_path = target / ".ai-powerkit/install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["managed_assets"].append(
                {"path": "../outside", "kind": "managed-file", "sha256": "0" * 64}
            )
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            before = self.file_snapshot(target)
            result = self.run_powerkit(
                "uninstall", "--target", str(target), "--yes"
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("does not exactly match validated project state", result.stderr)
            self.assertEqual(self.file_snapshot(target), before)


if __name__ == "__main__":
    unittest.main()
