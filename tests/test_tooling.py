from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from powerkit import installer as installer_tool
from powerkit import resources as resources_tool
from tools import package as package_tool
from tools import validate as validate_tool
from tools.release_inventory import select_distribution_files

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
START = "<!-- AI-ENGINEERING-POWERKIT:START -->"


class ToolingTests(unittest.TestCase):
    def run_cmd(
        self,
        *args: str,
        cwd: Path | None = None,
        input_text: str | None = None,
        env: dict[str, str] | None = None,
    ):
        return subprocess.run(
            [PYTHON, *args],
            cwd=cwd or ROOT,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
            env=env,
        )

    def test_validator_passes(self) -> None:
        result = self.run_cmd("tools/validate.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Validation passed", result.stdout)

    def test_distribution_json_decode_failure_is_controlled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "catalog.json").write_bytes(b"\xff\xfe")
            with mock.patch.object(resources_tool, "distribution_root", return_value=root):
                with self.assertRaisesRegex(
                    RuntimeError, "Unable to read PowerKit distribution data"
                ):
                    resources_tool.read_json("catalog.json")

    def test_guard_self_test(self) -> None:
        result = self.run_cmd("hooks/catastrophic_command_guard.py", "--self-test")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_codex_hook_example_uses_current_shape_and_git_root(self) -> None:
        payload = json.loads((ROOT / "adapters/codex/hooks.example.json").read_text(encoding="utf-8"))
        self.assertIn("hooks", payload)
        pre_tool = payload["hooks"]["PreToolUse"]
        self.assertTrue(pre_tool)
        command = pre_tool[0]["hooks"][0]["command"]
        self.assertIn("git rev-parse --show-toplevel", command)

    def test_claude_hook_example_covers_bash_and_powershell(self) -> None:
        payload = json.loads(
            (ROOT / "adapters/claude/settings.hooks.example.json").read_text(encoding="utf-8")
        )
        groups = {group["matcher"]: group["hooks"][0] for group in payload["hooks"]["PreToolUse"]}
        self.assertEqual(set(groups), {"Bash", "PowerShell"})
        self.assertEqual(groups["Bash"]["command"], "python3")
        self.assertEqual(groups["PowerShell"]["command"], "py")
        for handler in groups.values():
            self.assertIn(
                "${CLAUDE_PROJECT_DIR}/.ai-powerkit/hooks/catastrophic_command_guard.py",
                handler["args"],
            )

    def test_copilot_agents_declare_explicit_tools(self) -> None:
        for path in (ROOT / "adapters/copilot/agents").glob("*.agent.md"):
            text = path.read_text(encoding="utf-8")
            frontmatter = text.split("---", 2)[1]
            self.assertIn("tools:", frontmatter, path.name)

    def test_guard_blocks_catastrophic_command(self) -> None:
        payload = json.dumps({"tool_input": {"command": "sudo rm -rf /"}})
        result = self.run_cmd("hooks/catastrophic_command_guard.py", input_text=payload)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Blocked by AI Engineering PowerKit", result.stderr)

    def test_guard_allows_normal_cleanup(self) -> None:
        payload = json.dumps({"tool_input": {"command": "rm -rf ./build"}})
        result = self.run_cmd("hooks/catastrophic_command_guard.py", input_text=payload)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_guard_fails_closed_on_invalid_event(self) -> None:
        malformed = self.run_cmd(
            "hooks/catastrophic_command_guard.py", input_text="{not-json"
        )
        self.assertEqual(malformed.returncode, 2)
        self.assertIn("invalid hook event JSON", malformed.stderr)

        missing_command = self.run_cmd(
            "hooks/catastrophic_command_guard.py", input_text=json.dumps({"tool_input": {}})
        )
        self.assertEqual(missing_command.returncode, 2)
        self.assertIn("contains no shell command", missing_command.stderr)

    def test_project_dry_run_does_not_mutate_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            result = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "foundation",
                "--platforms",
                "codex,claude,copilot",
                "--include-agents",
                "--stage-hooks",
                "--dry-run",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(list(target.iterdir()), [])

    def test_legacy_installer_defaults_to_all_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            result = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--platforms",
                "codex",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads(
                (target / ".ai-powerkit/install-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["profiles"], ["all"])
            self.assertEqual(len(manifest["skills"]), 24)

    def test_each_project_platform_installs_in_isolation(self) -> None:
        expected_paths = {
            "codex": (".agents/skills", "AGENTS.md", ".codex/agents"),
            "claude": (".claude/skills", "CLAUDE.md", ".claude/agents"),
            "copilot": (".agents/skills", ".github/copilot-instructions.md", ".github/agents"),
        }
        for platform, paths in expected_paths.items():
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as temp:
                target = Path(temp)
                result = self.run_cmd(
                    "tools/install.py",
                    "--target",
                    str(target),
                    "--profiles",
                    "foundation",
                    "--platforms",
                    platform,
                    "--include-agents",
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                for relative in paths:
                    self.assertTrue((target / relative).exists(), relative)

    def test_user_scope_copilot_agents_use_supported_location(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fake_home = Path(temp)
            env = dict(os.environ)
            env["HOME"] = str(fake_home)
            result = self.run_cmd(
                "tools/install.py",
                "--scope",
                "user",
                "--profiles",
                "foundation",
                "--platforms",
                "copilot",
                "--include-agents",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len(list((fake_home / ".copilot/agents").glob("*.agent.md"))), 6)
            self.assertTrue((fake_home / ".agents/skills/prompt-preflight/SKILL.md").is_file())

    def test_project_install_and_managed_reinstall(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            command = (
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "foundation",
                "--platforms",
                "codex,claude,copilot",
                "--include-agents",
            )
            result = self.run_cmd(*command)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            # A second run must safely update PowerKit-managed artifacts.
            result = self.run_cmd(*command)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
            expected = len(catalog["profiles"]["foundation"]["skills"])
            canonical = list((target / ".agents/skills").glob("*/SKILL.md"))
            claude = list((target / ".claude/skills").glob("*/SKILL.md"))
            self.assertEqual(len(canonical), expected)
            self.assertEqual(len(claude), expected)
            self.assertTrue((target / "AGENTS.md").is_file())
            self.assertTrue((target / "CLAUDE.md").is_file())
            self.assertTrue((target / ".github/copilot-instructions.md").is_file())
            self.assertTrue((target / ".agents/skills/pk/SKILL.md").is_file())
            self.assertTrue((target / ".claude/skills/pk/SKILL.md").is_file())
            copilot_prompt = target / ".github/prompts/pk.prompt.md"
            self.assertTrue(copilot_prompt.is_file())
            self.assertIn(
                "../../.agents/skills/pk/SKILL.md",
                copilot_prompt.read_text(encoding="utf-8"),
            )
            self.assertTrue(
                (copilot_prompt.parent / "../../.agents/skills/pk/SKILL.md").resolve().is_file()
            )
            self.assertEqual(len(list((target / ".codex/agents").glob("*.toml"))), 6)
            self.assertEqual(len(list((target / ".claude/agents").glob("*.md"))), 6)
            self.assertEqual(len(list((target / ".github/agents").glob("*.agent.md"))), 6)
            manifest = json.loads(
                (target / ".ai-powerkit/install-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["version"], catalog["version"])
            self.assertEqual(manifest["schema_version"], 2)
            self.assertTrue(manifest["managed_assets"])
            self.assertTrue(all(not Path(item).is_absolute() for item in manifest["files"]))
            self.assertEqual(manifest["commands"], ["pk"])
            self.assertEqual(
                manifest["command_adapters"],
                {"claude": "/pk", "codex": "$pk", "copilot": "/pk"},
            )
            self.assertFalse(
                (target / ".ai-powerkit/backups").exists(),
                "a no-op reinstall must not create backups or mutate managed pk assets",
            )

    def test_install_refuses_unmanaged_skill_before_any_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            unmanaged = target / ".agents/skills/prompt-preflight"
            unmanaged.mkdir(parents=True)
            (unmanaged / "SKILL.md").write_text("unmanaged", encoding="utf-8")
            result = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "foundation",
                "--platforms",
                "codex",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Refusing to overwrite unmanaged skill", result.stderr)
            installed_dirs = {path.name for path in (target / ".agents/skills").iterdir()}
            self.assertEqual(installed_dirs, {"prompt-preflight"})
            self.assertFalse((target / "AGENTS.md").exists())
            self.assertFalse((target / ".ai-powerkit/install-manifest.json").exists())

    def test_install_refuses_unmanaged_agent_before_any_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            agent = target / ".codex/agents/evidence-explorer.toml"
            agent.parent.mkdir(parents=True)
            original = 'name = "my-private-agent"\n'
            agent.write_text(original, encoding="utf-8")
            result = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "foundation",
                "--platforms",
                "codex",
                "--include-agents",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Refusing to overwrite unmanaged file", result.stderr)
            self.assertEqual(agent.read_text(encoding="utf-8"), original)
            self.assertFalse((target / ".agents/skills").exists())
            self.assertFalse((target / "AGENTS.md").exists())
            self.assertFalse((target / ".ai-powerkit/install-manifest.json").exists())

    def test_install_refuses_unmanaged_command_adapter_before_any_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            prompt = target / ".github/prompts/pk.prompt.md"
            prompt.parent.mkdir(parents=True)
            original = "# Team-owned pk prompt\n"
            prompt.write_text(original, encoding="utf-8")
            result = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "foundation",
                "--platforms",
                "copilot",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Refusing to overwrite unmanaged file", result.stderr)
            self.assertEqual(prompt.read_text(encoding="utf-8"), original)
            self.assertFalse((target / ".agents/skills").exists())
            self.assertFalse((target / ".github/copilot-instructions.md").exists())
            self.assertFalse((target / ".ai-powerkit/install-manifest.json").exists())

    def test_platform_relevant_pk_adapters(self) -> None:
        expected = {
            "codex": {
                ".agents/skills/pk/SKILL.md",
                "AGENTS.md",
            },
            "claude": {
                ".claude/skills/pk/SKILL.md",
                "CLAUDE.md",
            },
            "copilot": {
                ".agents/skills/pk/SKILL.md",
                ".github/copilot-instructions.md",
                ".github/prompts/pk.prompt.md",
            },
        }
        forbidden = {
            "codex": {".claude/skills/pk/SKILL.md", ".github/prompts/pk.prompt.md"},
            "claude": {".agents/skills/pk/SKILL.md", ".github/prompts/pk.prompt.md"},
            "copilot": {".claude/skills/pk/SKILL.md"},
        }
        for platform in ("codex", "claude", "copilot"):
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as temp:
                target = Path(temp)
                result = self.run_cmd(
                    "tools/install.py",
                    "--target",
                    str(target),
                    "--profiles",
                    "foundation",
                    "--platforms",
                    platform,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                for relative in expected[platform]:
                    self.assertTrue((target / relative).is_file(), relative)
                for relative in forbidden[platform]:
                    self.assertFalse((target / relative).exists(), relative)

    def test_command_adapter_is_not_installed_when_pk_is_not_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            result = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "quality",
                "--platforms",
                "copilot",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((target / ".agents/skills/pk").exists())
            self.assertFalse((target / ".github/prompts/pk.prompt.md").exists())
            manifest = json.loads(
                (target / ".ai-powerkit/install-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["commands"], [])
            self.assertEqual(manifest["command_adapters"], {})

    def test_command_manifest_paths_cannot_escape_install_roots(self) -> None:
        spec = importlib.util.spec_from_file_location("powerkit_install", ROOT / "tools/install.py")
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaisesRegex(RuntimeError, "outside its root"):
            module.confined_manifest_path(ROOT, "../outside.md", "test")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            destination = root / "real"
            destination.mkdir()
            link = root / "linked"
            try:
                link.symlink_to(destination, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            with self.assertRaisesRegex(RuntimeError, "uses a symlink"):
                module.confined_manifest_path(root, "linked/prompt.md", "test")

    def test_user_scope_copilot_does_not_claim_literal_prompt_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            env = os.environ.copy()
            env["HOME"] = str(target)
            result = self.run_cmd(
                "tools/install.py",
                "--scope",
                "user",
                "--profiles",
                "foundation",
                "--platforms",
                "codex,claude,copilot",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((target / ".agents/skills/pk/SKILL.md").is_file())
            self.assertTrue((target / ".claude/skills/pk/SKILL.md").is_file())
            self.assertFalse((target / ".github/prompts/pk.prompt.md").exists())
            manifest = json.loads(
                (target / ".ai-powerkit/install-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["command_adapters"]["copilot"],
                "ask Copilot to use the pk skill",
            )

    def test_pk_routing_eval_coverage_and_constraints(self) -> None:
        root = ROOT / ".agents/skills/pk"
        manifest = json.loads(
            (root / "references/command-manifest.json").read_text(encoding="utf-8")
        )
        routing = json.loads((root / "evals/routing-cases.json").read_text(encoding="utf-8"))
        self.assertEqual(
            set(manifest["modes"]),
            {"auto", "feature", "bug", "review", "resume", "architecture", "ui", "dependency", "deep"},
        )
        by_category = {case["category"]: case for case in routing["cases"]}
        self.assertGreaterEqual(len(by_category), 17)
        self.assertIn("plan_only", by_category["plan_only"]["preserved_constraints"])
        self.assertIn("no_write", by_category["no_write"]["preserved_constraints"])
        self.assertEqual(by_category["explicit_override"]["command_mode"], "review")
        self.assertEqual(by_category["no_heavyweight"]["expected_depth"], "FAST")
        self.assertIn(
            "engineering-task-orchestrator",
            by_category["no_heavyweight"]["must_not_activate"],
        )
        self.assertEqual(by_category["photohelm_vertical_slice"]["expected_intent"], "feature")
        self.assertIn(
            "vertical-slice-planner",
            by_category["photohelm_vertical_slice"]["must_activate"],
        )

    def test_pk_help_matches_explicit_modes(self) -> None:
        root = ROOT / ".agents/skills/pk"
        manifest = json.loads(
            (root / "references/command-manifest.json").read_text(encoding="utf-8")
        )
        skill = (root / "SKILL.md").read_text(encoding="utf-8")
        for mode in set(manifest["modes"]) - {manifest["default_mode"]}:
            self.assertIn(f"/pk {mode}", skill)
        self.assertIn("/pk help", skill)
        self.assertLessEqual(len(skill.splitlines()), 200)

    def test_install_dry_run_reports_command_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            result = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "foundation",
                "--platforms",
                "copilot",
                "--dry-run",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("copy file: .github/prompts/pk.prompt.md", result.stdout)
            self.assertIn("PowerKit command installed: copilot /pk", result.stdout)
            self.assertEqual(list(target.iterdir()), [])

    def test_install_refuses_malformed_instruction_markers_before_any_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            instruction = target / "AGENTS.md"
            original = f"# Existing rules\n\n{START}\nbroken managed block\n"
            instruction.write_text(original, encoding="utf-8")
            result = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "foundation",
                "--platforms",
                "codex",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Malformed PowerKit instruction markers", result.stderr)
            self.assertEqual(instruction.read_text(encoding="utf-8"), original)
            self.assertFalse((target / ".agents/skills").exists())
            self.assertFalse((target / ".ai-powerkit/install-manifest.json").exists())

    def test_install_rejects_symlinked_instruction_without_external_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target"
            target.mkdir()
            external = root / "external.txt"
            external.write_text("user-owned\n", encoding="utf-8")
            try:
                (target / "AGENTS.md").symlink_to(external)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            result = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "foundation",
                "--platforms",
                "codex",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Refusing symlinked installation destination", result.stderr)
            self.assertEqual(external.read_text(encoding="utf-8"), "user-owned\n")
            self.assertFalse((target / ".agents").exists())

    def test_install_rejects_symlinked_parent_without_external_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target"
            external = root / "external"
            target.mkdir()
            external.mkdir()
            try:
                (target / ".agents").symlink_to(external, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            result = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "foundation",
                "--platforms",
                "codex",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Refusing symlinked installation destination", result.stderr)
            self.assertEqual(list(external.iterdir()), [])
            self.assertFalse((target / "AGENTS.md").exists())

    def test_install_rejects_nested_skill_symlink_without_reading_external_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target"
            target.mkdir()
            first = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "foundation",
                "--platforms",
                "codex",
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            external = root / "external-secret.txt"
            external.write_text("must not enter backups\n", encoding="utf-8")
            nested_link = target / ".agents/skills/prompt-preflight/external-secret.txt"
            try:
                nested_link.symlink_to(external)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")

            result = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "foundation",
                "--platforms",
                "codex",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("symlinked content", result.stderr)
            self.assertEqual(
                external.read_text(encoding="utf-8"), "must not enter backups\n"
            )
            backup_root = target / ".ai-powerkit/backups"
            if backup_root.exists():
                self.assertEqual(list(backup_root.rglob("external-secret.txt")), [])

    def test_distribution_source_preflight_rejects_symlinked_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside_temp:
            root = Path(temp)
            outside = Path(outside_temp)
            source = outside / "agent.toml"
            source.write_text("external\n", encoding="utf-8")
            try:
                (root / "adapters").symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            with mock.patch.object(installer_tool, "ROOT", root):
                with self.assertRaisesRegex(RuntimeError, "must not use a symlink"):
                    installer_tool.preflight_distribution_source(
                        root / "adapters/agent.toml"
                    )

    def test_stage_hooks_refuses_unmanaged_destination_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            hook = target / ".ai-powerkit/hooks/catastrophic_command_guard.py"
            hook.parent.mkdir(parents=True)
            hook.write_text("# private guard\n", encoding="utf-8")
            result = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "foundation",
                "--platforms",
                "claude",
                "--stage-hooks",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Refusing to overwrite unmanaged staged file", result.stderr)
            self.assertEqual(hook.read_text(encoding="utf-8"), "# private guard\n")
            self.assertFalse((target / ".claude").exists())

    def test_staged_hook_reinstall_and_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "repo-a"
            target.mkdir()
            command = (
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "foundation",
                "--platforms",
                "codex,claude",
                "--stage-hooks",
            )
            first = self.run_cmd(*command)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            first_manifest = json.loads(
                (target / ".ai-powerkit/install-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(first_manifest["schema_version"], 2)
            self.assertTrue(all(not Path(item).is_absolute() for item in first_manifest["files"]))

            moved = Path(temp) / "repo-b"
            target.rename(moved)
            moved_command = tuple(
                str(moved) if item == str(target) else item for item in command
            )
            second = self.run_cmd(*moved_command)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)

            manifest_path = moved / ".ai-powerkit/install-manifest.json"
            legacy_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            legacy_manifest["schema_version"] = 1
            for field in ("files", "stale_files"):
                legacy_manifest[field] = [
                    str(moved / item) for item in legacy_manifest[field]
                ]
            manifest_path.write_text(
                json.dumps(legacy_manifest, indent=2) + "\n", encoding="utf-8"
            )

            legacy_moved = Path(temp) / "repo-c"
            moved.rename(legacy_moved)
            legacy_command = tuple(
                str(legacy_moved) if item == str(moved) else item
                for item in moved_command
            )
            third = self.run_cmd(*legacy_command)
            self.assertEqual(third.returncode, 0, third.stdout + third.stderr)
            migrated_manifest = json.loads(
                (legacy_moved / ".ai-powerkit/install-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(migrated_manifest["schema_version"], 2)
            self.assertTrue(
                all(not Path(item).is_absolute() for item in migrated_manifest["files"])
            )

            without_hooks = tuple(
                item for item in legacy_command if item != "--stage-hooks"
            )
            deselected = self.run_cmd(*without_hooks)
            self.assertEqual(
                deselected.returncode, 0, deselected.stdout + deselected.stderr
            )
            deselected_manifest = json.loads(
                (legacy_moved / ".ai-powerkit/install-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn(
                ".ai-powerkit/hooks/catastrophic_command_guard.py",
                deselected_manifest["stale_files"],
            )
            reselected = self.run_cmd(*legacy_command)
            self.assertEqual(
                reselected.returncode, 0, reselected.stdout + reselected.stderr
            )

            guard = legacy_moved / ".ai-powerkit/hooks/catastrophic_command_guard.py"
            result = self.run_cmd(
                str(guard),
                input_text=json.dumps(
                    {"tool_name": "Bash", "tool_input": {"command": "rm -r -f /"}}
                ),
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Blocked by AI Engineering PowerKit", result.stderr)

    def test_install_reports_stale_managed_artifacts_without_deleting(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            first = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "all",
                "--platforms",
                "codex",
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            stale_skill = target / ".agents/skills/runtime-ux-review/SKILL.md"
            self.assertTrue(stale_skill.is_file())
            second = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "foundation",
                "--platforms",
                "codex",
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("previously managed artifact", second.stdout)
            self.assertTrue(stale_skill.is_file())
            manifest = json.loads(
                (target / ".ai-powerkit/install-manifest.json").read_text(encoding="utf-8")
            )
            self.assertTrue(manifest["stale_files"])
            third = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "foundation",
                "--platforms",
                "codex",
            )
            self.assertEqual(third.returncode, 0, third.stdout + third.stderr)
            third_manifest = json.loads(
                (target / ".ai-powerkit/install-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(third_manifest["stale_files"], manifest["stale_files"])
            self.assertTrue(stale_skill.is_file())

    def test_install_backup_preserves_exact_previous_instruction(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            instruction = target / "AGENTS.md"
            original = "# Private instructions\n\nKeep this text.\n"
            instruction.write_text(original, encoding="utf-8")
            result = self.run_cmd(
                "tools/install.py",
                "--target",
                str(target),
                "--profiles",
                "foundation",
                "--platforms",
                "codex",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            backups = list((target / ".ai-powerkit/backups").glob("*/AGENTS.md"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), original)

    def test_verification_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            config_dir = target / ".ai-powerkit"
            config_dir.mkdir()
            (target / "verification-output.txt").write_text(
                "OUTPUT_MUST_NOT_BE_STORED\n", encoding="utf-8"
            )
            (config_dir / "project.json").write_text(
                json.dumps(
                    {
                        "verification": {
                            "static": [
                                f'{PYTHON} -c "print(open(\'verification-output.txt\').read())"'
                            ],
                            "targeted": [],
                            "broader": [],
                            "runtime": [],
                        }
                    }
                ),
                encoding="utf-8",
            )
            result = self.run_cmd(
                str(ROOT / "tools/run_verification.py"),
                "--target",
                str(target),
                "--levels",
                "static",
                "--evidence-out",
                ".ai-powerkit/verification/result.json",
                cwd=target,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Verification passed", result.stdout)
            evidence = json.loads(
                (target / ".ai-powerkit/verification/result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(evidence["records"][0]["status"], "passed")
            self.assertNotIn("OUTPUT_MUST_NOT_BE_STORED", json.dumps(evidence))

    def test_verification_runner_rejects_empty_proof_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            config_dir = target / ".ai-powerkit"
            config_dir.mkdir()
            (config_dir / "project.json").write_text(
                json.dumps({"verification": {level: [] for level in ("static", "targeted", "broader", "runtime")}}),
                encoding="utf-8",
            )
            result = self.run_cmd(
                str(ROOT / "tools/run_verification.py"),
                "--target",
                str(target),
                cwd=target,
            )
            self.assertEqual(result.returncode, 2)
            allowed = self.run_cmd(
                str(ROOT / "tools/run_verification.py"),
                "--target",
                str(target),
                "--allow-empty",
                cwd=target,
            )
            self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)

    def test_frontmatter_parser_rejects_duplicate_and_malformed_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "SKILL.md"
            path.write_text("---\nname: one\nname: two\ndescription: ok\n---\nbody\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate YAML key"):
                validate_tool.parse_frontmatter(path)
            path.write_text("---\nname: one\ndescription: [broken\n---\nbody\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "malformed YAML scalar"):
                validate_tool.parse_frontmatter(path)

    def test_validator_rejects_version_and_canonical_source_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            copy = Path(temp) / "powerkit"
            shutil.copytree(
                ROOT,
                copy,
                ignore=shutil.ignore_patterns(".git", "dist", "__pycache__", "*.pyc"),
            )
            project = (copy / "pyproject.toml").read_text(encoding="utf-8")
            version = json.loads((copy / "catalog.json").read_text(encoding="utf-8"))["version"]
            (copy / "pyproject.toml").write_text(
                project.replace(f'version = "{version}"', 'version = "9.9.9"'),
                encoding="utf-8",
            )
            duplicate = copy / ".claude/skills/fake/SKILL.md"
            duplicate.parent.mkdir(parents=True)
            duplicate.write_text("---\nname: fake\ndescription: use fake\n---\nbody\n", encoding="utf-8")
            template_path = copy / "templates/project-config.example.json"
            template = json.loads(template_path.read_text(encoding="utf-8"))
            template["powerkit"]["profiles"] = ["foundation"]
            template_path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
            result = self.run_cmd(str(copy / "tools/validate.py"), cwd=copy)
            self.assertEqual(result.returncode, 1)
            self.assertIn("versions differ", result.stdout)
            self.assertIn("canonical skill bodies belong only", result.stdout)
            self.assertIn("profiles must match distribution defaults", result.stdout)

    def test_validator_accepts_copilot_web_alias_and_rejects_unknown_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            copy = Path(temp) / "powerkit"
            shutil.copytree(
                ROOT,
                copy,
                ignore=shutil.ignore_patterns(".git", "dist", "__pycache__", "*.pyc"),
            )
            agent = copy / "adapters/copilot/agents/evidence-explorer.agent.md"
            original = agent.read_text(encoding="utf-8")
            with_web = original.replace(
                'tools: ["read", "search"]',
                'tools: ["read", "search", "web"]',
                1,
            )
            agent.write_text(with_web, encoding="utf-8")
            accepted = self.run_cmd(str(copy / "tools/validate.py"), cwd=copy)
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

            agent.write_text(
                with_web.replace('"web"', '"unknown-tool"', 1),
                encoding="utf-8",
            )
            rejected = self.run_cmd(str(copy / "tools/validate.py"), cwd=copy)
            self.assertEqual(rejected.returncode, 1)
            self.assertIn("unknown Copilot tool aliases: unknown-tool", rejected.stdout)

    def test_package_contains_only_git_tracked_regular_files(self) -> None:
        untracked = ROOT / ".package-secret-test"
        untracked.write_text("must not ship\n", encoding="utf-8")
        try:
            result = self.run_cmd("tools/package.py")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            archive_path = Path(result.stdout.strip().splitlines()[-1])
            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())
            self.assertNotIn("ai-engineering-powerkit/.package-secret-test", names)
            tracked = subprocess.run(
                ["git", "ls-files"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.splitlines()
            self.assertEqual(
                names,
                {f"ai-engineering-powerkit/{path}" for path in tracked},
            )
        finally:
            untracked.unlink(missing_ok=True)

    def test_source_archive_runs_broker_in_fresh_directory(self) -> None:
        result = self.run_cmd("tools/package.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        archive_path = Path(result.stdout.strip().splitlines()[-1])
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp)
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(destination)
            source = destination / "ai-engineering-powerkit"
            for relative in (
                "powerkit/broker.py",
                "schemas/execution-broker-v1.schema.json",
                "adapters/codex/capabilities.json",
                "adapters/claude/capabilities.json",
                "adapters/copilot/capabilities.json",
            ):
                self.assertTrue((source / relative).is_file(), relative)
            smoke = subprocess.run(
                [
                    PYTHON,
                    "-m",
                    "powerkit",
                    "broker",
                    "explain",
                    "--effort",
                    "FAST",
                    "--risk",
                    "NORMAL",
                    "--platform",
                    "codex",
                    "--surface",
                    "app",
                    "--compact",
                ],
                cwd=source,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(smoke.returncode, 0, smoke.stdout + smoke.stderr)
            self.assertIn("decision=PROCEED", smoke.stdout)

    def test_package_rejects_tracked_symlink_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            external = Path(temp) / "secret"
            external.write_text("secret\n", encoding="utf-8")
            link = ROOT / ".package-link-test"
            try:
                link.symlink_to(external)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            completed = subprocess.CompletedProcess(
                args=["git", "ls-files"], returncode=0, stdout=b".package-link-test\0", stderr=b""
            )
            try:
                with mock.patch.object(package_tool.subprocess, "run", return_value=completed):
                    with self.assertRaisesRegex(RuntimeError, "refusing tracked symlink"):
                        package_tool.tracked_release_files()
            finally:
                link.unlink(missing_ok=True)

    def test_wheel_inventory_excludes_untracked_files_and_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            top = root / "catalog.json"
            tracked = root / "assets/tracked.txt"
            untracked = root / "assets/untracked-secret.txt"
            tracked.parent.mkdir(parents=True)
            top.write_text("{}\n", encoding="utf-8")
            tracked.write_text("tracked\n", encoding="utf-8")
            untracked.write_text("secret\n", encoding="utf-8")
            selected = select_distribution_files(
                root,
                (Path("catalog.json"),),
                (Path("assets"),),
                {Path("catalog.json"), Path("assets/tracked.txt")},
            )
            self.assertEqual(selected, [Path("catalog.json"), Path("assets/tracked.txt")])

            external = root / "outside.txt"
            external.write_text("outside\n", encoding="utf-8")
            link = root / "assets/tracked-link.txt"
            try:
                link.symlink_to(external)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            external.unlink()
            try:
                with self.assertRaisesRegex(RuntimeError, "symlinked wheel source"):
                    select_distribution_files(
                        root,
                        (Path("catalog.json"),),
                        (Path("assets"),),
                        {
                            Path("catalog.json"),
                            Path("assets/tracked.txt"),
                            Path("assets/tracked-link.txt"),
                        },
                    )
            finally:
                link.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
