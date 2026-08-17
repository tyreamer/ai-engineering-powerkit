from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
START = "<!-- AI-ENGINEERING-POWERKIT:START -->"


class ToolingTests(unittest.TestCase):
    def run_cmd(self, *args: str, cwd: Path | None = None, input_text: str | None = None):
        return subprocess.run(
            [PYTHON, *args],
            cwd=cwd or ROOT,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )

    def test_validator_passes(self) -> None:
        result = self.run_cmd("tools/validate.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Validation passed", result.stdout)

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
            self.assertEqual(len(list((target / ".codex/agents").glob("*.toml"))), 6)
            self.assertEqual(len(list((target / ".claude/agents").glob("*.md"))), 6)
            self.assertEqual(len(list((target / ".github/agents").glob("*.agent.md"))), 6)
            manifest = json.loads(
                (target / ".ai-powerkit/install-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["version"], catalog["version"])
            self.assertTrue((target / ".ai-powerkit/backups").is_dir())

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
            self.assertIn("Refusing to overwrite unmanaged agent file", result.stderr)
            self.assertEqual(agent.read_text(encoding="utf-8"), original)
            self.assertFalse((target / ".agents/skills").exists())
            self.assertFalse((target / "AGENTS.md").exists())
            self.assertFalse((target / ".ai-powerkit/install-manifest.json").exists())

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

    def test_verification_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            config_dir = target / ".ai-powerkit"
            config_dir.mkdir()
            (config_dir / "project.json").write_text(
                json.dumps(
                    {
                        "verification": {
                            "static": [f'{PYTHON} -c "print(123)"'],
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
                cwd=target,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Verification passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
