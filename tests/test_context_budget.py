from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from powerkit.context_budget import (
    ContextAuditError,
    TokenEstimator,
    audit_context,
    baseline_payload,
    render_context_report,
    safe_terminal_text,
    write_baseline,
)
from powerkit.installer import InstallRequest, execute_install


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


class ContextBudgetTests(unittest.TestCase):
    maxDiff = None

    def assert_schema_conforms(
        self,
        instance: object,
        schema: dict,
        *,
        root: dict | None = None,
        path: str = "$",
    ) -> None:
        root = schema if root is None else root
        if "$ref" in schema:
            resolved: object = root
            for part in schema["$ref"].removeprefix("#/").split("/"):
                resolved = resolved[part]  # type: ignore[index]
            self.assert_schema_conforms(instance, resolved, root=root, path=path)  # type: ignore[arg-type]
            return
        if "oneOf" in schema:
            matches = 0
            for candidate in schema["oneOf"]:
                try:
                    self.assert_schema_conforms(instance, candidate, root=root, path=path)
                except AssertionError:
                    continue
                matches += 1
            self.assertEqual(matches, 1, f"{path}: expected exactly one matching schema")
            return
        if "const" in schema:
            self.assertEqual(instance, schema["const"], f"{path}: const mismatch")
        if "enum" in schema:
            self.assertIn(instance, schema["enum"], f"{path}: enum mismatch")
        expected_types = schema.get("type")
        if expected_types is not None:
            names = [expected_types] if isinstance(expected_types, str) else expected_types
            type_matches = {
                "object": isinstance(instance, dict),
                "array": isinstance(instance, list),
                "string": isinstance(instance, str),
                "integer": isinstance(instance, int) and not isinstance(instance, bool),
                "number": isinstance(instance, (int, float)) and not isinstance(instance, bool),
                "boolean": isinstance(instance, bool),
                "null": instance is None,
            }
            self.assertTrue(any(type_matches[name] for name in names), f"{path}: wrong type")
        if isinstance(instance, dict):
            self.assertGreaterEqual(len(instance), schema.get("minProperties", 0), path)
            required = schema.get("required", [])
            self.assertTrue(set(required) <= set(instance), f"{path}: missing required fields")
            properties = schema.get("properties", {})
            additional = schema.get("additionalProperties", True)
            property_names = schema.get("propertyNames")
            for key, value in instance.items():
                if property_names:
                    self.assert_schema_conforms(key, property_names, root=root, path=f"{path}.<key>")
                if key in properties:
                    self.assert_schema_conforms(value, properties[key], root=root, path=f"{path}.{key}")
                elif additional is False:
                    self.fail(f"{path}: unexpected property {key!r}")
                elif isinstance(additional, dict):
                    self.assert_schema_conforms(value, additional, root=root, path=f"{path}.{key}")
        if isinstance(instance, list) and isinstance(schema.get("items"), dict):
            for index, value in enumerate(instance):
                self.assert_schema_conforms(value, schema["items"], root=root, path=f"{path}[{index}]")
        if isinstance(instance, (int, float)) and not isinstance(instance, bool) and "minimum" in schema:
            self.assertGreaterEqual(instance, schema["minimum"], path)

    def run_powerkit(self, *args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [PYTHON, "-m", "powerkit", *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )

    def init_project(
        self,
        target: Path,
        *,
        profiles: str = "all",
        platforms: str = "codex,claude,copilot",
    ) -> None:
        result = self.run_powerkit(
            "init",
            "--target",
            str(target),
            "--profiles",
            profiles,
            "--platforms",
            platforms,
            "--yes",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @staticmethod
    def write_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def make_source_fixture(
        self,
        target: Path,
        skills: dict[str, tuple[str, str]],
        *,
        instruction: str = "# PowerKit\n\nKeep common requests light.\n",
        budgets: dict | None = None,
    ) -> None:
        catalog_skills = []
        profile_skills = []
        for name, (description, body) in skills.items():
            profile_skills.append(name)
            catalog_skills.append(
                {
                    "name": name,
                    "title": name.title(),
                    "profile": "foundation",
                    "description": description,
                }
            )
            skill = target / ".agents/skills" / name / "SKILL.md"
            skill.parent.mkdir(parents=True, exist_ok=True)
            skill.write_text(
                "\n".join(
                    [
                        "---",
                        f"name: {name}",
                        f'description: "{description}"',
                        "license: MIT",
                        "metadata:",
                        "  author: test",
                        '  version: "1.0.0"',
                        "  profile: foundation",
                        "---",
                        "",
                        body,
                        "",
                    ]
                ),
                encoding="utf-8",
            )
        self.write_json(
            target / "catalog.json",
            {
                "schema_version": 1,
                "name": "AI Engineering PowerKit",
                "version": "1.0.0",
                "canonical_skill_root": ".agents/skills",
                "profiles": {
                    "foundation": {
                        "description": "test",
                        "skills": profile_skills,
                    }
                },
                "skills": catalog_skills,
            },
        )
        self.write_json(
            target / "manifests/powerkit.json",
            {
                "schema_version": 1,
                "powerkit_version": "1.0.0",
                "repository": "https://github.com/tyreamer/ai-engineering-powerkit",
            },
        )
        (target / "AGENTS.md").write_text(instruction, encoding="utf-8")
        if budgets is not None:
            self.write_json(
                target / ".ai-powerkit/project.json",
                {
                    "schema_version": 1,
                    "powerkit": {
                        "platforms": ["codex"],
                        "context_budgets": budgets,
                    },
                },
            )

    def test_fallback_estimator_is_deterministic_for_ascii_and_unicode(self) -> None:
        estimator = TokenEstimator()
        ascii_count = estimator.measure("abcdefgh")
        unicode_count = estimator.measure("éé")
        self.assertEqual(ascii_count.bytes, 8)
        self.assertEqual(ascii_count.characters, 8)
        self.assertEqual(ascii_count.tokens, 2)
        self.assertEqual(unicode_count.bytes, 4)
        self.assertEqual(unicode_count.characters, 2)
        self.assertEqual(unicode_count.tokens, 1)
        self.assertEqual(estimator.measure("abcdefgh"), ascii_count)

    def test_source_inventory_classifies_all_context_layers(self) -> None:
        result = audit_context(ROOT, platforms=("codex", "claude", "copilot"))
        categories = {artifact["category"] for artifact in result.payload["artifacts"]}
        self.assertEqual(
            categories,
            {
                "always_on_instruction",
                "skill_discovery_metadata",
                "selected_skill_body",
                "skill_reference",
                "agent_instruction",
                "platform_adapter",
            },
        )
        self.assertEqual(result.payload["scope"]["kind"], "distribution-source")
        self.assertTrue(result.payload["summary"]["powerkit_attributable_only"])

    def test_platform_models_do_not_claim_observed_context(self) -> None:
        report = audit_context(ROOT, platforms=("codex", "claude", "copilot")).payload
        by_name = {platform["name"]: platform for platform in report["platforms"]}
        self.assertEqual(set(by_name), {"codex", "claude", "copilot"})
        self.assertTrue(all(item["observation"]["status"] == "unsupported" for item in by_name.values()))
        self.assertGreater(by_name["copilot"]["totals"]["adapter_tokens"], 0)
        self.assertEqual(by_name["codex"]["totals"]["adapter_tokens"], 0)
        self.assertEqual(by_name["claude"]["totals"]["adapter_tokens"], 0)
        for platform in by_name.values():
            for depth in ("fast", "standard", "deep"):
                generated = platform["paths"][depth]["components"]["generated_task_context"]
                self.assertIsInstance(generated, int)
                self.assertLessEqual(generated, 180)

    def test_unconfigured_platform_is_not_given_fake_parity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init_project(target, platforms="codex")
            report = audit_context(
                target,
                platforms=("codex", "claude", "copilot"),
            ).payload
            by_name = {platform["name"]: platform for platform in report["platforms"]}
            self.assertEqual(by_name["codex"]["configuration_status"], "configured")
            self.assertEqual(by_name["claude"]["configuration_status"], "not_configured")
            self.assertEqual(by_name["copilot"]["configuration_status"], "not_configured")
            self.assertIsNone(by_name["claude"]["paths"]["fast"]["tokens"])
            self.assertEqual(
                next(
                    item
                    for item in report["budgets"]["evaluations"]
                    if item["platform"] == "claude" and item["metric"] == "always_on_tokens"
                )["status"],
                "not_measurable",
            )

    def test_unknown_platform_is_controlled(self) -> None:
        result = self.run_powerkit("context", "audit", "--platform", "unknown")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown context audit platform", result.stderr)

    def test_unconfigured_repository_is_not_modeled_as_installed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            (target / "AGENTS.md").write_text("# unrelated project rules\n", encoding="utf-8")
            with self.assertRaisesRegex(ContextAuditError, "No PowerKit source tree"):
                audit_context(target, platforms=("codex",))

    def test_unrelated_skill_catalog_is_not_powerkit_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            (target / ".agents/skills/example").mkdir(parents=True)
            self.write_json(
                target / "catalog.json",
                {
                    "schema_version": 1,
                    "name": "Another Toolkit",
                    "version": "1.0.0",
                    "canonical_skill_root": ".agents/skills",
                },
            )
            self.write_json(
                target / "manifests/powerkit.json",
                {
                    "schema_version": 1,
                    "powerkit_version": "1.0.0",
                    "repository": "https://example.com/another-toolkit",
                },
            )
            with self.assertRaisesRegex(ContextAuditError, "not a recognized PowerKit"):
                audit_context(target, platforms=("codex",))

    def test_json_schema_separates_machine_output_from_human_report(self) -> None:
        result = self.run_powerkit(
            "context",
            "audit",
            "--target",
            str(ROOT),
            "--platform",
            "codex",
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        schema = json.loads(
            (ROOT / "schemas/context-audit-v1.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload["schema_version"], 1)
        self.assertTrue(set(schema["required"]) <= set(payload))
        self.assertIn("scope", payload)
        self.assertIn("estimator", payload)
        self.assertIn("artifacts", payload)
        self.assertIn("recommendations", payload)
        self.assertNotIn("Top opportunities", result.stdout)
        self.assert_schema_conforms(payload, schema)
        human = render_context_report(payload)
        self.assertIn("PowerKit Context Audit", human)
        self.assertIn("What I'd change", human)
        self.assertIn("Estimated, not provider-billed", human)
        baseline = baseline_payload(payload)
        baseline_schema = json.loads(
            (ROOT / "schemas/context-baseline-v1.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(baseline_schema["required"]), set(baseline))
        self.assert_schema_conforms(baseline, baseline_schema)

    def test_actual_source_audit_keeps_fast_routing_lazy_and_reports_adapter_parity(self) -> None:
        findings = {
            item["class"]
            for item in audit_context(
                ROOT, platforms=("codex", "claude", "copilot")
            ).payload["recommendations"]
        }
        self.assertNotIn("reference_loaded_too_eagerly", findings)
        self.assertIn("adapter_duplication", findings)
        codex = audit_context(ROOT, platforms=("codex",)).payload["platforms"][0]
        self.assertLess(
            codex["paths"]["fast"]["components"]["skill_references"],
            codex["paths"]["standard"]["components"]["skill_references"],
        )
        routing = (ROOT / ".agents/skills/pk/references/routing.md").read_text(encoding="utf-8")
        self.assertIn("powerkit context audit", routing)

    def test_eager_reference_recommendation_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.make_source_fixture(
                target,
                {
                    "pk": (
                        "Use for explicit fixture routing; do not use for ordinary requests.",
                        "# Router\n\nFor every other request, always read references/routing.md.",
                    )
                },
            )
            references = target / ".agents/skills/pk/references"
            references.mkdir()
            (references / "routing.md").write_text("Detailed rare mode. " * 260, encoding="utf-8")
            self.write_json(
                references / "command-manifest.json",
                {
                    "schema_version": 1,
                    "command": "pk",
                    "global_skills": ["prompt-preflight", "workload-router"],
                    "modes": {
                        "feature": {
                            "primary_skills": [
                                "engineering-task-orchestrator",
                                "repository-cartographer",
                                "task-contract"
                            ],
                            "conditional_skills": []
                        },
                        "deep": {
                            "primary_skills": [
                                "engineering-task-orchestrator",
                                "verification-loop",
                                "adversarial-review",
                                "decision-handoff"
                            ],
                            "conditional_skills": []
                        },
                    },
                },
            )
            classes = {
                item["class"]
                for item in audit_context(target, platforms=("codex",)).payload[
                    "recommendations"
                ]
            }
            self.assertIn("reference_loaded_too_eagerly", classes)

    def test_recommendations_cover_description_reference_duplicate_overlap_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            shared = (
                "Gather the repository evidence, compare the execution path, record the exact "
                "behavior, and return a compact decision with deterministic verification. "
                "Preserve the bounded scope, connect each claim to a concrete source, and state "
                "which runtime behavior remains unverified for the next accountable maintainer."
            )
            safety = (
                "Never overwrite security or authorization policy without review because the "
                "permission boundary protects tenant data and secrets."
            )
            long_description = (
                "Maps repository behavior, execution paths, deterministic verification, and exact "
                "evidence for complex delivery workflows. Use for repository analysis and review; "
                "do not use for tiny edits or unrelated research. Includes detailed evidence "
                "collection, validation sequencing, handoff procedure, and acceptance reporting "
                "that belongs in the selected skill body rather than discovery metadata."
            )
            skills = {
                "large-guide": (long_description, "# Guide\n\n" + ("Deep provider guidance. " * 400)),
                "overlap-guide": (
                    long_description.replace("Maps", "Reviews"),
                    f"# Overlap\n\n{shared}\n\n{safety}",
                ),
                "duplicate-guide": (
                    "Use for duplicate fixture analysis; do not use elsewhere.",
                    f"# Duplicate\n\n{shared}\n\n{safety}",
                ),
            }
            for index in range(47):
                skills[f"extra-{index}"] = (
                    f"Use for bounded fixture capability {index}; do not use for other work.",
                    f"# Extra {index}\n\nKeep this fixture bounded.",
                )
            self.make_source_fixture(target, skills)
            agent = target / "adapters/codex/agents/oversized.toml"
            agent.parent.mkdir(parents=True)
            agent.write_text(
                'name = "oversized"\ndeveloper_instructions = """\n'
                + ("Generic engineering checklist. " * 150)
                + '\n"""\n',
                encoding="utf-8",
            )
            report = audit_context(target, platforms=("codex",)).payload
            classes = {item["class"] for item in report["recommendations"]}
            self.assertIn("oversized_skill_description", classes)
            self.assertIn("reference_candidate", classes)
            self.assertIn("duplicate_instruction", classes)
            self.assertIn("cross_skill_overlap", classes)
            self.assertIn("metadata_explosion", classes)
            self.assertIn("agent_prompt_bloat", classes)
            self.assertGreaterEqual(report["protected_repetitions"], 1)

    def test_malformed_utf8_is_counted_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.make_source_fixture(
                target,
                {"fixture": ("Use for fixture audits; do not use elsewhere.", "# Fixture")},
            )
            skill = target / ".agents/skills/fixture/SKILL.md"
            skill.write_bytes(skill.read_bytes() + b"\n\xff\xfe\n")
            report = audit_context(target, platforms=("codex",)).payload
            self.assertTrue(any("malformed UTF-8" in warning for warning in report["warnings"]))
            body = next(
                item for item in report["artifacts"] if item["category"] == "selected_skill_body"
            )
            self.assertEqual(body["measurement"]["bytes"], skill.stat().st_size)
            self.assertEqual(body["measurement"]["quality"], "estimated")

    def test_fresh_install_and_minimal_profile_are_measurable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init_project(target, profiles="foundation", platforms="codex")
            report = audit_context(target, platforms=("codex",)).payload
            platform = report["platforms"][0]
            self.assertEqual(report["scope"]["kind"], "installed")
            self.assertEqual(platform["totals"]["discoverable_skills"], 8)
            self.assertEqual(platform["paths"]["fast"]["status"], "estimated")
            self.assertEqual(platform["paths"]["standard"]["status"], "partial")
            self.assertGreater(platform["totals"]["always_on_tokens"], 0)

    def test_all_profile_install_remains_auditable_after_sync(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init_project(target, profiles="all", platforms="codex,claude,copilot")
            sync = self.run_powerkit("sync", "--target", str(target))
            self.assertEqual(sync.returncode, 0, sync.stdout + sync.stderr)
            report = audit_context(
                target,
                platforms=("codex", "claude", "copilot"),
            ).payload
            self.assertTrue(
                all(platform["totals"]["discoverable_skills"] == 24 for platform in report["platforms"])
            )
            self.assertTrue(
                all(platform["paths"]["deep"]["status"] == "estimated" for platform in report["platforms"])
            )
            self.assertNotIn(
                "duplicate_instruction",
                {item["class"] for item in report["recommendations"]},
            )

    def test_missing_manifest_owned_instruction_is_not_reported_as_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init_project(target, platforms="codex")
            (target / "AGENTS.md").unlink()
            with self.assertRaisesRegex(ContextAuditError, "artifact is missing"):
                audit_context(target, platforms=("codex",))

    def test_team_clone_uses_desired_state_without_competing_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as source_temp, tempfile.TemporaryDirectory() as clone_temp:
            source = Path(source_temp)
            clone = Path(clone_temp)
            self.init_project(source, profiles="foundation", platforms="claude")
            config = source / ".ai-powerkit/project.json"
            destination = clone / ".ai-powerkit/project.json"
            destination.parent.mkdir(parents=True)
            shutil.copy2(config, destination)
            report = audit_context(clone, platforms=("claude",)).payload
            self.assertEqual(report["scope"]["kind"], "desired-installation")
            self.assertEqual(report["scope"]["inventory_source"], ".ai-powerkit/project.json + pinned distribution")
            self.assertEqual(report["platforms"][0]["totals"]["discoverable_skills"], 8)
            self.assertTrue(any("static potential" in item["evidence"] for item in report["artifacts"]))

    def test_relocated_install_uses_relative_manifest_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            original = base / "original"
            relocated = base / "relocated"
            original.mkdir()
            self.init_project(original, platforms="copilot")
            shutil.copytree(original, relocated)
            report = audit_context(relocated, platforms=("copilot",)).payload
            self.assertEqual(report["scope"]["target"], str(relocated.resolve()))
            self.assertGreater(report["platforms"][0]["totals"]["adapter_tokens"], 0)

    def test_user_scope_models_platform_instruction_differences(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            execute_install(
                InstallRequest(
                    base=home,
                    profiles=("foundation",),
                    platforms=frozenset({"codex", "claude", "copilot"}),
                    scope="user",
                    include_agents=True,
                    verbose=False,
                )
            )
            report = audit_context(
                home,
                platforms=("codex", "claude", "copilot"),
            ).payload
            by_name = {platform["name"]: platform for platform in report["platforms"]}
            self.assertEqual(report["scope"]["install_scope"], "user")
            self.assertGreater(by_name["codex"]["totals"]["always_on_tokens"], 0)
            self.assertGreater(by_name["claude"]["totals"]["always_on_tokens"], 0)
            self.assertEqual(by_name["copilot"]["totals"]["always_on_tokens"], 0)

    def test_doctor_prints_only_concise_context_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init_project(target, platforms="codex")
            result = self.run_powerkit("doctor", "--target", str(target))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("context budget", result.stdout)
            self.assertIn("powerkit context audit", result.stdout)
            self.assertNotIn("Top opportunities", result.stdout)

    def test_low_budget_warns_and_ci_flag_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            budgets = {
                "policy": "warn",
                "always_on_tokens": 0,
                "discovery_tokens": 0,
                "fast_path_tokens": 0,
                "standard_path_tokens": 0,
                "deep_path_tokens": 0,
                "regression_percent": 10,
                "regression_tokens": 10,
            }
            self.make_source_fixture(
                target,
                {"fixture": ("Use for fixture audits; do not use elsewhere.", "# Fixture")},
                budgets=budgets,
            )
            interactive = audit_context(target, platforms=("codex",))
            enforced = audit_context(target, platforms=("codex",), ci=True)
            self.assertFalse(interactive.ci_failed)
            self.assertTrue(enforced.ci_failed)
            self.assertEqual(interactive.payload["summary"]["status"], "needs_attention")
            self.assertIn(
                "oversized_always_on",
                {item["class"] for item in interactive.payload["recommendations"]},
            )
            cli = self.run_powerkit(
                "context",
                "audit",
                "--target",
                str(target),
                "--platform",
                "codex",
                "--ci",
                "--json",
            )
            self.assertEqual(cli.returncode, 1, cli.stdout + cli.stderr)
            self.assertTrue(json.loads(cli.stdout)["budgets"]["ci_failed"])

    def test_disabled_budget_policy_never_fails_ci(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            budgets = {
                "policy": "disabled",
                "always_on_tokens": 0,
                "discovery_tokens": 0,
                "fast_path_tokens": 0,
                "standard_path_tokens": 0,
                "deep_path_tokens": 0,
                "regression_percent": 0,
                "regression_tokens": 0,
            }
            self.make_source_fixture(
                target,
                {"fixture": ("Use for fixture audits; do not use elsewhere.", "# Fixture")},
                budgets=budgets,
            )
            result = audit_context(target, platforms=("codex",), ci=True)
            self.assertFalse(result.ci_failed)
            self.assertEqual(result.payload["budgets"]["evaluations"], [])

    def test_baseline_detects_meaningful_always_on_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            budgets = {
                "policy": "fail_ci",
                "always_on_tokens": 10000,
                "discovery_tokens": 10000,
                "fast_path_tokens": 10000,
                "standard_path_tokens": 10000,
                "deep_path_tokens": 10000,
                "regression_percent": 10,
                "regression_tokens": 100,
            }
            self.make_source_fixture(
                target,
                {"fixture": ("Use for fixture audits; do not use elsewhere.", "# Fixture")},
                budgets=budgets,
            )
            first = audit_context(target, platforms=("codex",))
            write_baseline(target, Path(".ai-powerkit/context-baseline.json"), first.payload)
            (target / "AGENTS.md").write_text("# PowerKit\n\n" + ("Always present detail. " * 120), encoding="utf-8")
            second = audit_context(target, platforms=("codex",))
            regressions = [
                item
                for item in second.payload["baseline_comparison"]["comparisons"]
                if item["meaningful_regression"]
            ]
            self.assertTrue(second.ci_failed)
            self.assertTrue(any(item["metric"] == "always_on_tokens" for item in regressions))

    def test_cli_writes_content_free_static_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.make_source_fixture(
                target,
                {"fixture": ("Use for fixture audits; do not use elsewhere.", "# Fixture")},
            )
            result = self.run_powerkit(
                "context",
                "audit",
                "--target",
                str(target),
                "--platform",
                "codex",
                "--write-baseline",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            path = target / ".ai-powerkit/context-baseline.json"
            baseline = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(baseline["schema_version"], 1)
            self.assertEqual(set(baseline), {"schema_version", "powerkit_version", "estimator", "platforms"})
            self.assertNotIn("artifacts", baseline)
            self.assertEqual(json.loads(result.stdout)["baseline_written"], ".ai-powerkit/context-baseline.json")

    def test_baseline_omits_explicit_unconfigured_platforms(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init_project(target, profiles="foundation", platforms="codex")
            report = audit_context(target, platforms=("codex", "claude", "copilot"))
            path = write_baseline(target, Path(".ai-powerkit/context-baseline.json"), report.payload)
            baseline = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(set(baseline["platforms"]), {"codex"})
            self.assertNotIn("standard_path_tokens", baseline["platforms"]["codex"])
            unconfigured_only = audit_context(target, platforms=("claude",))
            with self.assertRaisesRegex(ContextAuditError, "no requested platform is configured"):
                write_baseline(
                    target,
                    Path(".ai-powerkit/unconfigured-baseline.json"),
                    unconfigured_only.payload,
                )
            cli = self.run_powerkit(
                "context",
                "audit",
                "--target",
                str(target),
                "--platform",
                "claude",
                "--write-baseline",
                ".ai-powerkit/unconfigured-baseline.json",
                "--json",
            )
            self.assertEqual(cli.returncode, 2)
            self.assertFalse((target / ".ai-powerkit/unconfigured-baseline.json").exists())

    def test_boolean_baseline_metric_is_not_treated_as_an_integer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            budgets = {
                "policy": "fail_ci",
                "always_on_tokens": 10000,
                "discovery_tokens": 10000,
                "fast_path_tokens": 10000,
                "standard_path_tokens": 10000,
                "deep_path_tokens": 10000,
                "regression_percent": 10,
                "regression_tokens": 10,
            }
            self.make_source_fixture(
                target,
                {"fixture": ("Use for fixture audits; do not use elsewhere.", "# Fixture")},
                instruction="# PowerKit\n\n" + ("Persistent context. " * 200),
                budgets=budgets,
            )
            report = audit_context(target, platforms=("codex",))
            baseline = baseline_payload(report.payload)
            baseline["platforms"]["codex"]["always_on_tokens"] = True
            self.write_json(target / ".ai-powerkit/context-baseline.json", baseline)
            with self.assertRaisesRegex(ContextAuditError, "must be a non-negative integer"):
                audit_context(target, platforms=("codex",))

    def test_explicit_missing_or_incompatible_baseline_cannot_disable_ci(self) -> None:
        class AlternateEstimator(TokenEstimator):
            identifier = "fixture-exact-v1"
            label = "fixture exact estimator"
            quality = "exact"

        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.make_source_fixture(
                target,
                {"fixture": ("Use for fixture audits; do not use elsewhere.", "# Fixture")},
            )
            with self.assertRaisesRegex(ContextAuditError, "Requested context baseline does not exist"):
                audit_context(
                    target,
                    platforms=("codex",),
                    baseline_path=Path(".ai-powerkit/missing.json"),
                    ci=True,
                )
            initial = audit_context(target, platforms=("codex",))
            write_baseline(target, Path(".ai-powerkit/context-baseline.json"), initial.payload)
            incomplete_payload = baseline_payload(initial.payload)
            incomplete_payload["platforms"]["codex"] = {"deep_path_tokens": 0}
            self.write_json(
                target / ".ai-powerkit/context-baseline.json",
                incomplete_payload,
            )
            incomplete = audit_context(target, platforms=("codex",), ci=True)
            self.assertEqual(
                incomplete.payload["baseline_comparison"]["status"],
                "incomplete_baseline",
            )
            self.assertTrue(incomplete.ci_failed)
            write_baseline(target, Path(".ai-powerkit/context-baseline.json"), initial.payload)
            incompatible = audit_context(
                target,
                platforms=("codex",),
                estimator=AlternateEstimator(),
                ci=True,
            )
            self.assertEqual(
                incompatible.payload["baseline_comparison"]["status"],
                "incompatible_estimator",
            )
            self.assertTrue(incompatible.ci_failed)

    def test_selected_skill_growth_does_not_fail_unrelated_global_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            budgets = {
                "policy": "fail_ci",
                "always_on_tokens": 10000,
                "discovery_tokens": 10000,
                "fast_path_tokens": 10000,
                "standard_path_tokens": 10000,
                "deep_path_tokens": 10000,
                "regression_percent": 10,
                "regression_tokens": 100,
            }
            self.make_source_fixture(
                target,
                {"rare-capability": ("Use for rare work; do not use for common tasks.", "# Rare")},
                budgets=budgets,
            )
            first = audit_context(target, platforms=("codex",))
            write_baseline(target, Path(".ai-powerkit/context-baseline.json"), first.payload)
            skill = target / ".agents/skills/rare-capability/SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + ("Deep rare detail. " * 500), encoding="utf-8")
            second = audit_context(target, platforms=("codex",))
            self.assertFalse(second.ci_failed)
            comparisons = second.payload["baseline_comparison"]["comparisons"]
            self.assertFalse(any(item["meaningful_regression"] for item in comparisons))

    def test_manifest_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.write_json(
                target / ".ai-powerkit/install-manifest.json",
                {
                    "schema_version": 2,
                    "toolkit": "ai-engineering-powerkit",
                    "version": "0.5.1",
                    "source": {
                        "repository": "https://github.com/tyreamer/ai-engineering-powerkit",
                        "version": "0.5.1",
                        "ref": "v0.5.1"
                    },
                    "scope": "project",
                    "profiles": ["foundation"],
                    "platforms": ["codex"],
                    "skills": ["pk"],
                    "agents": False,
                    "hooks_staged": False,
                    "managed_assets": [
                        {"path": "../outside", "kind": "instruction-block", "sha256": "x"}
                    ],
                },
            )
            with self.assertRaisesRegex(ContextAuditError, "Unsafe managed asset path"):
                audit_context(target, platforms=("codex",))

    @unittest.skipIf(not hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlinked_skill_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as external_temp:
            target = Path(temp)
            external = Path(external_temp)
            self.init_project(target, profiles="foundation", platforms="codex")
            shutil.rmtree(target / ".agents/skills")
            (target / ".agents/skills").symlink_to(external, target_is_directory=True)
            with self.assertRaisesRegex(ContextAuditError, "Unsafe managed asset path"):
                audit_context(target, platforms=("codex",))

    def test_foreign_and_unsupported_install_manifests_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            manifest = target / ".ai-powerkit/install-manifest.json"
            self.write_json(manifest, {"schema_version": 2, "toolkit": "another-tool"})
            with self.assertRaisesRegex(ContextAuditError, "not owned by PowerKit"):
                audit_context(target, platforms=("codex",))
            self.write_json(manifest, {"schema_version": 999, "toolkit": "ai-engineering-powerkit"})
            with self.assertRaisesRegex(ContextAuditError, "(?i)unsupported.*schema"):
                audit_context(target, platforms=("codex",))

    def test_installed_manifest_and_desired_platform_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init_project(target, profiles="foundation", platforms="codex")
            config_path = target / ".ai-powerkit/project.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["powerkit"]["platforms"] = ["claude"]
            self.write_json(config_path, config)
            with self.assertRaisesRegex(ContextAuditError, "project configuration and installed manifest disagree"):
                audit_context(target, platforms=("codex", "claude"))

    def test_manifest_context_omissions_cannot_create_healthy_undercounts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init_project(target, profiles="foundation", platforms="codex")
            manifest_path = target / ".ai-powerkit/install-manifest.json"
            original = json.loads(manifest_path.read_text(encoding="utf-8"))

            missing_instruction = json.loads(json.dumps(original))
            missing_instruction["managed_assets"] = [
                asset for asset in missing_instruction["managed_assets"]
                if asset.get("path") != "AGENTS.md"
            ]
            self.write_json(manifest_path, missing_instruction)
            with self.assertRaisesRegex(ContextAuditError, "omits expected PowerKit context artifacts"):
                audit_context(target, platforms=("codex",), ci=True)

            missing_skill = json.loads(json.dumps(original))
            missing_skill["skills"].remove("task-contract")
            self.write_json(manifest_path, missing_skill)
            with self.assertRaisesRegex(ContextAuditError, "skill selection disagrees"):
                audit_context(target, platforms=("codex",), ci=True)

            missing_agent = json.loads(json.dumps(original))
            missing_agent["managed_assets"] = [
                asset for asset in missing_agent["managed_assets"]
                if asset.get("path") != ".codex/agents/system-architect.toml"
            ]
            self.write_json(manifest_path, missing_agent)
            with self.assertRaisesRegex(ContextAuditError, "omits expected PowerKit context artifacts"):
                audit_context(target, platforms=("codex",), ci=True)

    def test_legacy_schema_one_inventory_remains_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init_project(target, profiles="foundation", platforms="codex")
            manifest_path = target / ".ai-powerkit/install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["schema_version"] = 1
            manifest.pop("managed_assets")
            manifest["files"] = [str(target / path) for path in manifest["files"]]
            self.write_json(manifest_path, manifest)
            report = audit_context(target, platforms=("codex",)).payload
            self.assertEqual(report["scope"]["kind"], "installed")
            self.assertGreater(report["platforms"][0]["totals"]["always_on_tokens"], 0)
            self.assertEqual(report["platforms"][0]["totals"]["discoverable_skills"], 8)

    def test_manifest_platform_alias_cannot_bypass_expected_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init_project(target, profiles="foundation", platforms="codex")
            config_path = target / ".ai-powerkit/project.json"
            config_path.unlink()
            manifest_path = target / ".ai-powerkit/install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["platforms"] = ["all"]
            manifest["managed_assets"] = []
            self.write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ContextAuditError, "platforms must use canonical"):
                audit_context(target, platforms=("codex",), ci=True)

    def test_corrupt_installed_command_manifest_cannot_undercount_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init_project(target, profiles="all", platforms="codex")
            command_manifest = target / ".agents/skills/pk/references/command-manifest.json"
            original = command_manifest.read_text(encoding="utf-8")
            command_manifest.write_text("{not-json\n", encoding="utf-8")
            with self.assertRaisesRegex(ContextAuditError, "command manifest is invalid JSON"):
                audit_context(target, platforms=("codex",))
            semantic = json.loads(original)
            semantic["global_skills"] = []
            command_manifest.write_text(json.dumps(semantic), encoding="utf-8")
            with self.assertRaisesRegex(ContextAuditError, "omits required global routing skills"):
                audit_context(target, platforms=("codex",))
            semantic = json.loads(original)
            semantic["modes"]["feature"]["primary_skills"] = []
            command_manifest.write_text(json.dumps(semantic), encoding="utf-8")
            with self.assertRaisesRegex(ContextAuditError, "mode 'feature' omits required routing skills"):
                audit_context(target, platforms=("codex",))
            command_manifest.write_text(original, encoding="utf-8")
            command_manifest.unlink()
            with self.assertRaisesRegex(ContextAuditError, "command manifest is missing"):
                audit_context(target, platforms=("codex",))

    def test_hostile_labels_are_terminal_safe(self) -> None:
        rendered = safe_terminal_text("evil\x1b[31m\nname")
        self.assertNotIn("\x1b", rendered)
        self.assertNotIn("\n", rendered)
        self.assertIn("\\u001b", rendered)
        self.assertIn("\\u000a", rendered)

    def test_doctor_sanitizes_hostile_audit_errors_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.init_project(target, profiles="foundation", platforms="codex")
            manifest_path = target / ".ai-powerkit/install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["version"] = "0.3.0\x1b[31m"
            manifest["source"]["version"] = manifest["version"]
            self.write_json(manifest_path, manifest)
            result = self.run_powerkit("doctor", "--target", str(target))
            self.assertNotIn("\x1b", result.stdout + result.stderr)
            self.assertIn("\\u001b", result.stdout)

    def test_intentional_keep_is_not_presented_as_an_action(self) -> None:
        report = audit_context(ROOT, platforms=("codex", "claude", "copilot")).payload
        rendered = render_context_report(report)
        self.assertIsNone(report["summary"]["highest_value_opportunity"])
        self.assertIn("No material static context waste detected", rendered)
        self.assertIn("Reviewed tradeoffs", rendered)
        self.assertIn("No prompt changes recommended", rendered)

    def test_instruction_content_is_never_executed_or_exposed_in_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            marker = target / "executed"
            hostile = f"__import__('pathlib').Path({str(marker)!r}).write_text('bad')"
            self.make_source_fixture(
                target,
                {"hostile": ("Use for hostile fixtures; do not use elsewhere.", hostile)},
            )
            report = audit_context(target, platforms=("codex",)).payload
            rendered = json.dumps(report)
            self.assertFalse(marker.exists())
            self.assertNotIn("__import__", rendered)
            self.assertNotIn(str(marker), rendered)


if __name__ == "__main__":
    unittest.main()
