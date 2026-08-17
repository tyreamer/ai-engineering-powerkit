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
EXPLICIT_MODES = {
    "feature",
    "bug",
    "review",
    "resume",
    "architecture",
    "ui",
    "dependency",
    "deep",
}
PK_FILES = (
    "SKILL.md",
    "evals/routing-cases.json",
    "references/command-manifest.json",
    "references/execution-broker.md",
    "references/proof-pack.md",
    "references/modes.md",
    "references/routing.md",
)


class IntegratedReleaseCandidateTests(unittest.TestCase):
    maxDiff = None

    def run_powerkit(self, *args: str):
        return subprocess.run(
            [PYTHON, "-m", "powerkit", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )

    def init(
        self,
        target: Path,
        *,
        platforms: str = "codex,claude,copilot",
        profiles: str | None = None,
    ) -> None:
        args = [
            "init",
            "--target",
            str(target),
            "--platforms",
            platforms,
            "--yes",
        ]
        if profiles is not None:
            args.extend(("--profiles", profiles))
        result = self.run_powerkit(*args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @staticmethod
    def read_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def pk_snapshot(target: Path) -> dict[str, tuple[bytes, int]]:
        roots = (
            target / ".agents/skills/pk",
            target / ".claude/skills/pk",
            target / ".github/prompts/pk.prompt.md",
        )
        files: list[Path] = []
        for root in roots:
            if root.is_file():
                files.append(root)
            elif root.is_dir():
                files.extend(path for path in root.rglob("*") if path.is_file())
        return {
            path.relative_to(target).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in files
        }

    def assert_complete_pk(self, skill_root: Path) -> None:
        for relative in PK_FILES:
            self.assertTrue((skill_root / relative).is_file(), relative)

    def test_fresh_agent_native_install_makes_pk_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target)
            self.assert_complete_pk(target / ".agents/skills/pk")
            self.assert_complete_pk(target / ".claude/skills/pk")
            self.assertTrue((target / ".github/prompts/pk.prompt.md").is_file())
            manifest = self.read_json(target / ".ai-powerkit/install-manifest.json")
            self.assertEqual(manifest["commands"], ["pk"])
            config = self.read_json(target / ".ai-powerkit/project.json")
            self.assertEqual(
                config["proof"]["output_directory"], ".ai-powerkit/proofs"
            )
            self.assertEqual(config["execution_policy"]["max_parallel_agents"], 4)

    def test_fresh_install_ignores_generated_local_state_and_preserves_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            subprocess.run(["git", "init", "-q", str(target)], check=True)
            ignore = target / ".ai-powerkit/.gitignore"
            ignore.parent.mkdir(parents=True)
            ignore.write_text("custom-cache/\n", encoding="utf-8")
            self.init(target)
            content = ignore.read_text(encoding="utf-8")
            self.assertIn("custom-cache/", content)
            for rule in ("backups/", "proofs/", "traces/", "verification/"):
                self.assertIn(rule, content)
            generated = (
                target / ".ai-powerkit/traces/task.json",
                target / ".ai-powerkit/proofs/task/proof.json",
                target / ".ai-powerkit/verification/result.json",
            )
            for path in generated:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}\n", encoding="utf-8")
            status = subprocess.run(
                ["git", "status", "--ignored", "--short"],
                cwd=target,
                text=True,
                capture_output=True,
                check=True,
            ).stdout
            self.assertIn("!! .ai-powerkit/traces/", status)
            self.assertIn("!! .ai-powerkit/proofs/", status)
            self.assertIn("!! .ai-powerkit/verification/", status)

    def test_all_eight_explicit_pk_modes_survive_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, profiles="all")
            skill_root = target / ".agents/skills/pk"
            command = self.read_json(skill_root / "references/command-manifest.json")
            self.assertEqual(set(command["modes"]) - {command["default_mode"]}, EXPLICIT_MODES)
            installed_skills = {
                path.name for path in (target / ".agents/skills").iterdir() if path.is_dir()
            }
            referenced = {
                skill
                for mode in command["modes"].values()
                for key in ("primary_skills", "conditional_skills")
                for skill in mode[key]
            }
            self.assertTrue(referenced <= installed_skills)

    def test_auto_routing_contract_survives_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, platforms="codex", profiles="all")
            skill_root = target / ".agents/skills/pk"
            command = self.read_json(skill_root / "references/command-manifest.json")
            cases = self.read_json(skill_root / "evals/routing-cases.json")["cases"]
            self.assertEqual(command["default_mode"], "auto")
            self.assertTrue(any(case["command_mode"] == "auto" for case in cases))
            self.assertIn(
                "automatic intent signals",
                (skill_root / "references/routing.md").read_text(encoding="utf-8").lower(),
            )

    def test_team_clone_sync_preserves_complete_pk(self) -> None:
        with tempfile.TemporaryDirectory() as source_temp, tempfile.TemporaryDirectory() as clone_temp:
            source = Path(source_temp)
            clone = Path(clone_temp)
            self.init(source, profiles="all")
            clone_config = clone / ".ai-powerkit/project.json"
            clone_config.parent.mkdir(parents=True)
            shutil.copy2(source / ".ai-powerkit/project.json", clone_config)

            result = self.run_powerkit("sync", "--target", str(clone))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assert_complete_pk(clone / ".agents/skills/pk")
            self.assert_complete_pk(clone / ".claude/skills/pk")
            self.assertTrue((clone / ".github/prompts/pk.prompt.md").is_file())
            manifest = self.read_json(clone / ".ai-powerkit/install-manifest.json")
            self.assertEqual(
                manifest["command_adapters"],
                {"claude": "/pk", "codex": "$pk", "copilot": "/pk"},
            )
            doctor = self.run_powerkit("doctor", "--target", str(clone), "--json")
            self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)

    def test_version_update_preserves_pk_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, profiles="all")
            config_path = target / ".ai-powerkit/project.json"
            config = self.read_json(config_path)
            expected_profiles = list(config["powerkit"]["profiles"])
            expected_platforms = list(config["powerkit"]["platforms"])
            config["powerkit"]["version"] = "0.1.0"
            config["powerkit"]["source"]["version"] = "0.1.0"
            config["powerkit"]["source"]["ref"] = "v0.1.0"
            config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

            manifest_path = target / ".ai-powerkit/install-manifest.json"
            manifest = self.read_json(manifest_path)
            manifest["version"] = "0.1.0"
            manifest["source"]["version"] = "0.1.0"
            manifest["source"]["ref"] = "v0.1.0"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            for marker_path in target.glob(".agents/skills/*/.powerkit-origin.json"):
                marker = self.read_json(marker_path)
                marker["version"] = "0.1.0"
                marker_path.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
            for marker_path in target.glob(".claude/skills/*/.powerkit-origin.json"):
                marker = self.read_json(marker_path)
                marker["version"] = "0.1.0"
                marker_path.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")

            result = self.run_powerkit(
                "update", "--target", str(target), "--version", "0.4.0", "--yes"
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            updated_config = self.read_json(config_path)
            self.assertEqual(updated_config["powerkit"]["profiles"], expected_profiles)
            self.assertEqual(updated_config["powerkit"]["platforms"], expected_platforms)
            self.assert_complete_pk(target / ".agents/skills/pk")
            updated_manifest = self.read_json(manifest_path)
            self.assertEqual(updated_manifest["commands"], ["pk"])
            self.assertEqual(updated_manifest["command_adapters"]["copilot"], "/pk")

    def test_noop_sync_does_not_mutate_installed_pk_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, profiles="all")
            before = self.pk_snapshot(target)
            result = self.run_powerkit("sync", "--target", str(target))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("already current", result.stdout)
            self.assertEqual(self.pk_snapshot(target), before)
            self.assertFalse((target / ".ai-powerkit/backups").exists())

    def test_uninstall_removes_only_managed_pk_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, profiles="all")
            consumer_prompt = target / ".github/prompts/team.prompt.md"
            consumer_prompt.write_text("# team-owned\n", encoding="utf-8")
            proof = target / ".ai-powerkit/proofs/keep-me/proof.json"
            proof.parent.mkdir(parents=True)
            proof.write_text("{\"schema_version\": 1}\n", encoding="utf-8")

            result = self.run_powerkit("uninstall", "--target", str(target), "--yes")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((target / ".agents/skills/pk").exists())
            self.assertFalse((target / ".claude/skills/pk").exists())
            self.assertFalse((target / ".github/prompts/pk.prompt.md").exists())
            self.assertTrue(consumer_prompt.is_file())
            self.assertTrue((target / ".ai-powerkit/project.json").is_file())
            self.assertTrue(proof.is_file())

    def test_sync_prunes_only_proven_pk_assets_when_command_is_deselected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, platforms="copilot", profiles="all")
            consumer_prompt = target / ".github/prompts/team.prompt.md"
            consumer_prompt.write_text("# team-owned\n", encoding="utf-8")
            config_path = target / ".ai-powerkit/project.json"
            config = self.read_json(config_path)
            config["powerkit"]["profiles"] = ["quality"]
            config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

            result = self.run_powerkit("sync", "--target", str(target))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((target / ".agents/skills/pk").exists())
            self.assertFalse((target / ".github/prompts/pk.prompt.md").exists())
            self.assertTrue(consumer_prompt.is_file())
            manifest = self.read_json(target / ".ai-powerkit/install-manifest.json")
            self.assertEqual(manifest["commands"], [])
            self.assertEqual(manifest["command_adapters"], {})
            doctor = self.run_powerkit("doctor", "--target", str(target))
            self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)

    def test_fast_requests_remain_lightweight_after_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, platforms="codex", profiles="all")
            cases = self.read_json(
                target / ".agents/skills/pk/evals/routing-cases.json"
            )["cases"]
            fast = next(case for case in cases if case["category"] == "no_heavyweight")
            self.assertEqual(fast["expected_depth"], "FAST")
            self.assertIn("engineering-task-orchestrator", fast["must_not_activate"])
            self.assertIn("parallel-investigator", fast["must_not_activate"])

    def test_architecture_and_deep_requests_retain_deep_routing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, platforms="codex", profiles="all")
            skill_root = target / ".agents/skills/pk"
            cases = self.read_json(skill_root / "evals/routing-cases.json")["cases"]
            by_category = {case["category"]: case for case in cases}
            self.assertEqual(by_category["architecture_migration"]["expected_depth"], "DEEP")
            self.assertEqual(by_category["architecture_migration"]["command_mode"], "architecture")
            self.assertEqual(by_category["deep_cross_cutting"]["command_mode"], "deep")
            self.assertIn(
                by_category["deep_cross_cutting"]["expected_depth"],
                {"DEEP", "HIGH_RISK"},
            )
            command = self.read_json(skill_root / "references/command-manifest.json")
            self.assertIn("migration-planner", command["modes"]["architecture"]["primary_skills"])
            self.assertIn("adversarial-review", command["modes"]["deep"]["primary_skills"])

    def test_plan_only_and_no_write_constraints_survive_installed_adapters(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, profiles="all")
            skill_root = target / ".agents/skills/pk"
            cases = self.read_json(skill_root / "evals/routing-cases.json")["cases"]
            by_category = {case["category"]: case for case in cases}
            self.assertIn("plan_only", by_category["plan_only"]["preserved_constraints"])
            self.assertIn("no_write", by_category["no_write"]["preserved_constraints"])
            skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
            prompt = (target / ".github/prompts/pk.prompt.md").read_text(encoding="utf-8")
            for expected in ("--plan-only", "--no-write"):
                self.assertIn(expected, skill)
            self.assertIn("plan-only or no-write constraints", prompt)

    def test_bootstrap_metadata_is_not_injected_into_runtime_prompt_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init(target, profiles="all")
            runtime_files = (
                target / "AGENTS.md",
                target / "CLAUDE.md",
                target / ".github/copilot-instructions.md",
                target / ".github/prompts/pk.prompt.md",
                target / ".agents/skills/pk/SKILL.md",
            )
            forbidden = (
                "BOOTSTRAP.md",
                "manifests/powerkit.json",
                ".ai-powerkit/project.json",
                ".ai-powerkit/install-manifest.json",
                "pipx install",
            )
            for path in runtime_files:
                text = path.read_text(encoding="utf-8")
                for value in forbidden:
                    self.assertNotIn(value, text, f"{value} leaked into {path}")


if __name__ == "__main__":
    unittest.main()
