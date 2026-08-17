from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from powerkit import broker


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


class ExecutionBrokerTests(unittest.TestCase):
    maxDiff = None

    def run_powerkit(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [PYTHON, "-m", "powerkit", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )

    def resolve(self, **overrides: object) -> dict:
        arguments: dict[str, object] = {
            "effort": "STANDARD",
            "risk": "NORMAL",
            "platform": "codex",
            "surface": "app",
        }
        arguments.update(overrides)
        return broker.resolve_policy(**arguments)  # type: ignore[arg-type]

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
        if "const" in schema:
            self.assertEqual(instance, schema["const"], path)
        if "enum" in schema:
            self.assertIn(instance, schema["enum"], path)
        expected = schema.get("type")
        if expected is not None:
            names = [expected] if isinstance(expected, str) else expected
            matches = {
                "object": isinstance(instance, dict),
                "array": isinstance(instance, list),
                "string": isinstance(instance, str),
                "integer": isinstance(instance, int) and not isinstance(instance, bool),
                "number": isinstance(instance, (int, float)) and not isinstance(instance, bool),
                "boolean": isinstance(instance, bool),
                "null": instance is None,
            }
            self.assertTrue(any(matches[name] for name in names), f"{path}: wrong type")
        if isinstance(instance, str):
            self.assertGreaterEqual(len(instance), schema.get("minLength", 0), path)
            if "pattern" in schema:
                self.assertRegex(instance, re.compile(schema["pattern"]), path)
        if isinstance(instance, (int, float)) and not isinstance(instance, bool):
            if "minimum" in schema:
                self.assertGreaterEqual(instance, schema["minimum"], path)
            if "maximum" in schema:
                self.assertLessEqual(instance, schema["maximum"], path)
        if isinstance(instance, dict):
            self.assertGreaterEqual(len(instance), schema.get("minProperties", 0), path)
            self.assertTrue(set(schema.get("required", ())) <= set(instance), path)
            properties = schema.get("properties", {})
            additional = schema.get("additionalProperties", True)
            for key, value in instance.items():
                if key in properties:
                    self.assert_schema_conforms(
                        value, properties[key], root=root, path=f"{path}.{key}"
                    )
                elif additional is False:
                    self.fail(f"{path}: unexpected property {key!r}")
                elif isinstance(additional, dict):
                    self.assert_schema_conforms(
                        value, additional, root=root, path=f"{path}.{key}"
                    )
        if isinstance(instance, list) and isinstance(schema.get("items"), dict):
            for index, value in enumerate(instance):
                self.assert_schema_conforms(
                    value, schema["items"], root=root, path=f"{path}[{index}]"
                )

    def test_effort_controls_resources_without_conflating_risk(self) -> None:
        expected = {
            "FAST": ("ECONOMY", "LOW", 1, "MINIMAL", "TARGETED", "FAST"),
            "STANDARD": ("BALANCED", "MEDIUM", 2, "FOCUSED", "STANDARD", "STANDARD"),
            "DEEP": ("STRONG", "HIGH", 4, "EXPANDED", "DEEP", "DEEP"),
        }
        for effort, values in expected.items():
            with self.subTest(effort=effort):
                report = self.resolve(effort=effort)
                desired = report["desired_policy"]
                actual = (
                    desired["intelligence"]["model_tier"],
                    desired["intelligence"]["reasoning"],
                    desired["agents"]["max_parallel"],
                    desired["context"]["budget"],
                    desired["verification"]["depth"],
                    desired["proof"]["compatibility_depth"],
                )
                self.assertEqual(actual, values)
                self.assertEqual(report["classification"]["effective_risk"], "NORMAL")

    def test_high_risk_deepens_safety_not_unrelated_reasoning(self) -> None:
        report = self.resolve(
            effort="FAST",
            risk="HIGH",
            traits=("SECURITY_SENSITIVE",),
        )
        desired = report["desired_policy"]
        self.assertEqual(desired["intelligence"]["reasoning"], "LOW")
        self.assertEqual(desired["agents"]["max_parallel"], 1)
        self.assertEqual(desired["verification"]["depth"], "DEEP")
        self.assertTrue(desired["verification"]["security"])
        self.assertTrue(desired["safety"]["checkpoint"])
        self.assertEqual(desired["proof"]["compatibility_depth"], "HIGH_RISK")

    def test_user_constraints_are_preserved(self) -> None:
        report = self.resolve(
            effort="DEEP",
            constraints=(
                "PLAN_ONLY",
                "NO_NETWORK",
                "NO_DEPENDENCIES",
                "NO_PARALLEL",
                "NO_SHELL",
                "BOUNDED_SCOPE",
            ),
            control_plane="LAUNCHER",
        )
        desired = report["desired_policy"]
        self.assertEqual(desired["permissions"]["write"], "READ_ONLY")
        self.assertEqual(desired["permissions"]["network"], "DENY")
        self.assertEqual(desired["permissions"]["dependency_changes"], "DENY")
        self.assertEqual(desired["permissions"]["shell"], "DENY")
        self.assertEqual(desired["permissions"]["external_writes"], "DENY")
        self.assertEqual(desired["agents"]["max_parallel"], 1)
        self.assertEqual(desired["context"]["repository_scope"], "BOUNDED")

    def test_cost_override_does_not_reduce_verification_or_safety(self) -> None:
        report = self.resolve(
            effort="DEEP",
            risk="HIGH",
            constraints=("COST_SENSITIVE",),
        )
        desired = report["desired_policy"]
        self.assertEqual(desired["intelligence"]["model_tier"], "BALANCED")
        self.assertEqual(desired["verification"]["depth"], "DEEP")
        self.assertTrue(desired["safety"]["checkpoint"])
        estimated = report["telemetry"]["estimated"]
        self.assertIn(estimated["relative_cost"], {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"})
        self.assertIn(estimated["likely_latency"], {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"})
        self.assertTrue(any("COST_SENSITIVE" in item for item in estimated["override_impact"]))

    def test_fast_latency_preference_never_increases_parallelism(self) -> None:
        policy = broker.default_execution_policy()
        policy["latency_preference"] = "FASTEST"
        report = self.resolve(effort="FAST", project_policy=policy)
        self.assertEqual(report["desired_policy"]["agents"]["max_parallel"], 1)

    def test_one_writer_and_distinct_review_roles_are_invariants(self) -> None:
        report = self.resolve(
            effort="DEEP",
            traits=("ARCHITECTURE", "MIGRATION"),
        )
        agents = report["desired_policy"]["agents"]
        self.assertTrue(agents["one_writer"])
        self.assertIn("bounded-implementer", agents["roles"])
        self.assertIn("independent-verifier", agents["roles"])
        self.assertIn("adversarial-critic", agents["roles"])
        sequential = self.resolve(
            effort="DEEP",
            constraints=("NO_PARALLEL",),
        )["desired_policy"]["agents"]
        self.assertEqual(sequential["max_parallel"], 1)
        self.assertTrue(sequential["independent_verifier"])

    def test_capability_contracts_cover_every_control_and_source(self) -> None:
        for platform in ("codex", "claude", "copilot"):
            with self.subTest(platform=platform):
                manifest = broker.load_capability_manifest(platform)
                self.assertTrue(manifest["sources"])
                self.assertTrue(
                    all(source["url"].startswith("https://") for source in manifest["sources"].values())
                )
                for surface in manifest["surfaces"].values():
                    self.assertTrue(surface["validation_detail"])
                    self.assertEqual(set(surface["controls"]), set(broker.CAPABILITY_CONTROLS))
                    for control in surface["controls"].values():
                        self.assertIn(control["support"], broker.SUPPORT_STATES)
                        self.assertIn(control["current_session"]["state"], broker.SUPPORT_STATES)
                        self.assertIn(control["launcher"]["state"], broker.SUPPORT_STATES)

    def test_capability_negotiation_distinguishes_lifecycle_and_stops_unsafe_gaps(self) -> None:
        current = self.resolve(control_plane="CURRENT_SESSION")
        launched = self.resolve(control_plane="LAUNCHER")
        self.assertEqual(current["negotiation"]["controls"]["model_selection"]["state"], "PARTIAL")
        self.assertEqual(launched["negotiation"]["controls"]["model_selection"]["state"], "NATIVE")
        checkpoint = self.resolve(risk="HIGH")
        self.assertEqual(checkpoint["negotiation"]["decision"], "CHECKPOINT")
        stopped = self.resolve(
            effort="FAST",
            risk="HIGH",
            platform="copilot",
            surface="ide",
            constraints=("NO_NETWORK",),
        )
        self.assertEqual(stopped["negotiation"]["decision"], "STOP")
        self.assertEqual(len(stopped["negotiation"]["blocking_reasons"]), 1)

    def test_hard_constraint_gaps_checkpoint_or_stop_instead_of_failing_open(self) -> None:
        current = self.resolve(constraints=("NO_WRITE",))
        self.assertEqual(current["negotiation"]["decision"], "CHECKPOINT")
        launched = self.resolve(
            constraints=("NO_WRITE",),
            control_plane="LAUNCHER",
        )
        self.assertEqual(launched["negotiation"]["decision"], "CHECKPOINT")
        unavailable = self.resolve(
            platform="copilot",
            surface="ide",
            constraints=("NO_WRITE",),
        )
        self.assertEqual(unavailable["negotiation"]["decision"], "STOP")
        no_dependencies = self.resolve(constraints=("NO_DEPENDENCIES",))
        self.assertEqual(no_dependencies["negotiation"]["decision"], "CHECKPOINT")
        ordinary_ide = self.resolve(platform="copilot", surface="ide")
        self.assertEqual(ordinary_ide["negotiation"]["decision"], "PROCEED")
        high_codex = self.resolve(
            risk="HIGH", surface="cli", control_plane="LAUNCHER"
        )
        self.assertEqual(high_codex["negotiation"]["decision"], "STOP")
        high_claude = self.resolve(
            risk="HIGH", platform="claude", surface="cli", control_plane="LAUNCHER"
        )
        self.assertEqual(high_claude["negotiation"]["decision"], "STOP")

    def test_project_never_network_policy_is_enforced_as_a_hard_boundary(self) -> None:
        policy = broker.default_execution_policy()
        policy["allow_network"] = "NEVER"
        report = self.resolve(project_policy=policy)
        self.assertEqual(report["desired_policy"]["permissions"]["network"], "DENY")
        self.assertEqual(report["negotiation"]["decision"], "STOP")
        self.assertIn("project network policy", report["negotiation"]["blocking_reasons"][0])

    def test_vendor_model_identifiers_are_confined_to_adapter_translation(self) -> None:
        report = self.resolve(control_plane="LAUNCHER")
        desired_text = json.dumps(report["desired_policy"]).lower()
        self.assertNotIn("gpt-", desired_text)
        self.assertNotIn("claude-", desired_text)
        settings = report["negotiation"]["native_settings"]
        self.assertTrue(any(setting["control"] == "model_selection" for setting in settings))

    def test_pass_through_launcher_settings_are_not_silently_dropped(self) -> None:
        codex = self.resolve(effort="DEEP", control_plane="LAUNCHER")
        codex_settings = {
            item["setting"]: item["value"]
            for item in codex["negotiation"]["native_settings"]
        }
        self.assertEqual(codex_settings["agents.max_concurrent_threads_per_session"], 4)
        claude = self.resolve(
            effort="DEEP", platform="claude", surface="cli", control_plane="LAUNCHER"
        )
        claude_settings = {
            item["setting"]: item["value"]
            for item in claude["negotiation"]["native_settings"]
        }
        self.assertEqual(claude_settings["CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS"], 4)
        self.assertEqual(claude_settings["--max-turns"], 16)

    def test_unmapped_native_claim_is_downgraded(self) -> None:
        report = self.resolve(effort="FAST", risk="HIGH", control_plane="LAUNCHER")
        filesystem = report["negotiation"]["controls"]["filesystem_scope"]
        self.assertEqual(filesystem["availability_state"], "NATIVE")
        self.assertEqual(filesystem["state"], "PARTIAL")
        self.assertEqual(filesystem["application"], "UNMAPPED")
        self.assertEqual(filesystem["enforcement_status"], "NOT_APPLIED")
        copilot = self.resolve(
            platform="copilot", surface="cli", control_plane="LAUNCHER"
        )
        self.assertFalse(
            any(
                item["control"] == "model_selection"
                for item in copilot["negotiation"]["native_settings"]
            )
        )
        policy = broker.default_execution_policy()
        policy["adapter_overrides"] = {
            "copilot": {"model_tiers": {"BALANCED": "approved-model"}}
        }
        overridden = self.resolve(
            platform="copilot",
            surface="cli",
            control_plane="LAUNCHER",
            project_policy=policy,
        )
        self.assertTrue(
            any(
                item["control"] == "model_selection"
                and item["value"] == "approved-model"
                for item in overridden["negotiation"]["native_settings"]
            )
        )

    def test_dogfood_cases_match_expected_policy(self) -> None:
        payload = json.loads((ROOT / "evals/execution-broker-cases.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(payload["cases"]), 7)
        for case in payload["cases"]:
            with self.subTest(case=case["id"]):
                report = self.resolve(
                    effort=case["effort"],
                    risk=case["risk"],
                    traits=case["traits"],
                    constraints=case["constraints"],
                )
                desired = report["desired_policy"]
                actual = {
                    "model_tier": desired["intelligence"]["model_tier"],
                    "reasoning": desired["intelligence"]["reasoning"],
                    "max_parallel": desired["agents"]["max_parallel"],
                    "roles": desired["agents"]["roles"],
                    "one_writer": desired["agents"]["one_writer"],
                    "context_budget": desired["context"]["budget"],
                    "repository_scope": desired["context"]["repository_scope"],
                    "write": desired["permissions"]["write"],
                    "shell": desired["permissions"]["shell"],
                    "network": desired["permissions"]["network"],
                    "dependency_changes": desired["permissions"]["dependency_changes"],
                    "checkpoint": desired["safety"]["checkpoint"],
                    "isolation": desired["safety"]["isolation"],
                    "max_iterations": desired["limits"]["max_iterations"],
                    "verification": desired["verification"]["depth"],
                    "proof": desired["proof"]["depth"],
                    "compatibility_depth": desired["proof"]["compatibility_depth"],
                    "decision": report["negotiation"]["decision"],
                    "platform": report["platform"]["name"],
                    "surface": report["platform"]["surface"],
                    "control_plane": report["platform"]["control_plane"],
                }
                self.assertEqual(actual, case["expected"])

    def test_report_conforms_to_versioned_schema(self) -> None:
        schema = json.loads(
            (ROOT / "schemas/execution-broker-v1.schema.json").read_text(encoding="utf-8")
        )
        self.assert_schema_conforms(self.resolve(), schema)
        trace_pattern = schema["properties"]["trace"]["properties"]["path"]["pattern"]
        self.assertIsNone(re.fullmatch(trace_pattern, ".ai-powerkit/traces/../outside.json"))

    def test_compact_output_is_small_and_observation_is_honest(self) -> None:
        report = self.resolve()
        compact = broker.render_compact_policy(report)
        self.assertLessEqual(report["telemetry"]["estimated"]["broker_compact_tokens"], 180)
        self.assertEqual(report["telemetry"]["observed"], {})
        self.assertIn("decision=PROCEED", compact)
        self.assertIn("shell=SCOPED", compact)
        self.assertIn("agents=2[bounded-implementer]", compact)
        self.assertIn("checkpoint=0", compact)
        self.assertIn("cap=CONTRACT", compact)
        self.assertIn("controls=fs:", compact)

    def test_compact_checkpoint_includes_reason_and_boundary(self) -> None:
        report = self.resolve(constraints=("NO_DEPENDENCIES", "NO_SHELL"))
        compact = broker.render_compact_policy(report)
        self.assertEqual(report["negotiation"]["decision"], "CHECKPOINT")
        self.assertIn("deps=DENY", compact)
        self.assertIn("shell=DENY", compact)
        self.assertIn("checkpoint=", compact)
        self.assertIn("boundary=", compact)
        self.assertIn("checkpoint=1", compact)

    def test_cli_supports_json_compact_trace_and_stop_exit(self) -> None:
        compact = self.run_powerkit(
            "broker", "explain", "--effort", "FAST", "--risk", "NORMAL",
            "--platform", "codex", "--surface", "app", "--compact",
        )
        self.assertEqual(compact.returncode, 0, compact.stderr)
        self.assertIn("FAST/NORMAL", compact.stdout)
        capabilities = self.run_powerkit(
            "broker", "capabilities", "--platform", "claude", "--json"
        )
        self.assertEqual(capabilities.returncode, 0, capabilities.stderr)
        self.assertEqual(json.loads(capabilities.stdout)["entries"][0]["platform"], "claude")
        lifecycle = json.loads(capabilities.stdout)["entries"][0]["controls"]["filesystem_scope"]
        self.assertIn("current_session", lifecycle)
        self.assertIn("launcher", lifecycle)
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            relative = Path(".ai-powerkit/traces/decision.json")
            traced = self.run_powerkit(
                "broker", "explain", "--target", str(target),
                "--effort", "FAST", "--risk", "NORMAL", "--platform", "codex",
                "--surface", "app", "--trace", str(relative),
                "--task-id", "cli-trace", "--json",
            )
            self.assertEqual(traced.returncode, 0, traced.stderr)
            saved = json.loads((target / relative).read_text(encoding="utf-8"))
            self.assertEqual(saved["trace"]["path"], relative.as_posix())
            self.assertEqual(saved["trace"]["task_id"], "cli-trace")
        stopped = self.run_powerkit(
            "broker", "explain", "--effort", "FAST", "--risk", "HIGH",
            "--platform", "copilot", "--surface", "ide",
            "--constraint", "NO_NETWORK", "--json",
        )
        self.assertEqual(stopped.returncode, 3, stopped.stderr)
        self.assertEqual(json.loads(stopped.stdout)["negotiation"]["decision"], "STOP")
        checkpoint = self.run_powerkit(
            "broker", "explain", "--effort", "FAST", "--risk", "NORMAL",
            "--platform", "codex", "--surface", "app", "--constraint", "NO_WRITE",
            "--compact",
        )
        self.assertEqual(checkpoint.returncode, 4, checkpoint.stderr)
        self.assertIn("boundary=", checkpoint.stdout)

    def test_trace_rejects_paths_outside_managed_trace_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, "under .ai-powerkit/traces"):
                broker.write_trace(Path(temp), Path("elsewhere/trace.json"), self.resolve())

    def test_trace_permissions_reason_validation_and_proof_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            relative = Path(".ai-powerkit/traces/decision.json")
            report = self.resolve()
            report["trace"] = {
                "path": relative.as_posix(),
                "task_id": "broker-test",
            }
            broker.write_trace(target, relative, report)
            self.assertEqual(os.stat(target / relative).st_mode & 0o777, 0o600)
            binding = broker.load_trace_binding(
                target, relative, "STANDARD", "broker-test"
            )
            self.assertEqual(binding.payload["decision"], "PROCEED")
            self.assertRegex(binding.payload["trace_sha256"], r"^[a-f0-9]{64}$")
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                broker.load_trace_binding(target, relative, "FAST", "broker-test")
            tampered = json.loads((target / relative).read_text(encoding="utf-8"))
            tampered["desired_policy"]["limits"]["max_iterations"] = 999
            (target / relative).write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "deterministic policy"):
                broker.load_trace_binding(target, relative, "STANDARD", "broker-test")
        with self.assertRaisesRegex(RuntimeError, "control characters"):
            self.resolve(reasons=("looks safe\nspoofed",))
        with self.assertRaisesRegex(RuntimeError, "at most"):
            self.resolve(reasons=("x" * 201,))

    def test_missing_capability_contract_uses_explicit_fail_closed_fallback(self) -> None:
        with mock.patch.object(
            broker, "load_capability_manifest", side_effect=RuntimeError("missing contract")
        ):
            normal = self.resolve()
            self.assertEqual(normal["platform"]["capability_status"], "FALLBACK")
            self.assertEqual(normal["negotiation"]["decision"], "CHECKPOINT")
            stopped = self.resolve(constraints=("NO_NETWORK",))
            self.assertEqual(stopped["negotiation"]["decision"], "STOP")

    def test_unvalidated_client_version_degrades_to_safe_fallback(self) -> None:
        report = self.resolve(client_version="999.0.0")
        self.assertEqual(report["platform"]["capability_status"], "VERSION_MISMATCH")
        self.assertEqual(report["negotiation"]["decision"], "CHECKPOINT")

    def test_manifest_validation_rejects_empty_sources_and_bad_translation(self) -> None:
        source = json.loads(broker.capability_manifest_path("codex").read_text(encoding="utf-8"))
        original_source_ids = list(
            source["defaults"]["controls"]["model_selection"]["source_ids"]
        )
        source["defaults"]["controls"]["model_selection"]["source_ids"] = []
        source["defaults"]["translations"][0]["applies_to"] = "SOMEDAY"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "capabilities.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            with mock.patch.object(broker, "capability_manifest_path", return_value=path):
                with self.assertRaisesRegex(RuntimeError, "references unknown sources"):
                    broker.load_capability_manifest("codex")
            source["defaults"]["controls"]["model_selection"]["source_ids"] = original_source_ids
            path.write_text(json.dumps(source), encoding="utf-8")
            with mock.patch.object(broker, "capability_manifest_path", return_value=path):
                with self.assertRaisesRegex(RuntimeError, "invalid applies_to"):
                    broker.load_capability_manifest("codex")

    def test_launcher_plan_applies_settings_and_withholds_passthrough(self) -> None:
        report = self.resolve(effort="FAST", surface="cli", control_plane="LAUNCHER")
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(
                broker, "_trusted_client_path", return_value=Path("/bin/echo")
            ):
                plan = broker.build_launch_plan(
                    report, Path(temp), ("private prompt",), client=Path("/bin/echo")
                )
            public = broker.public_launch_plan(plan)
            self.assertNotIn("private prompt", json.dumps(public))
            self.assertEqual(public["passthrough_arg_count"], 1)
            self.assertEqual(public["prompt_transport"], "stdin")
            self.assertEqual(public["local_session_persistence"], "disabled")
            self.assertIn("--ephemeral", public["command_preview"])
            self.assertEqual(plan["_argv"][-1], "-")
            self.assertIn("private prompt", plan["_stdin"])
            self.assertTrue(any(item["setting"] == "model" for item in public["settings"]))
            report["application"] = public
            schema = json.loads(
                (ROOT / "schemas/execution-broker-v1.schema.json").read_text(encoding="utf-8")
            )
            self.assert_schema_conforms(report, schema)
            with self.assertRaisesRegex(RuntimeError, "exactly one prompt"):
                with mock.patch.object(
                    broker, "_trusted_client_path", return_value=Path("/bin/echo")
                ):
                    broker.build_launch_plan(
                        report, Path(temp), ("--model", "unsafe"), client=Path("/bin/echo")
                    )
            claude_report = self.resolve(
                effort="FAST",
                platform="claude",
                surface="cli",
                control_plane="LAUNCHER",
                constraints=("NO_WRITE",),
            )
            with mock.patch.object(
                broker, "_trusted_client_path", return_value=Path("/bin/echo")
            ):
                claude_plan = broker.build_launch_plan(
                    claude_report,
                    Path(temp),
                    ("private prompt",),
                    client=Path("/bin/echo"),
                    checkpoint_acknowledged=True,
                )
            self.assertIn("--disable-slash-commands", claude_plan["command_preview"])
            self.assertIn("--no-session-persistence", claude_plan["command_preview"])

    def test_launcher_command_records_attempt_without_claiming_enforcement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "repo"
            target.mkdir()
            client = root / "codex"
            client.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"--version\" ]; then echo 'codex-cli 0.147.0-alpha.6.5'; fi\n"
                "exit 0\n",
                encoding="utf-8",
            )
            client.chmod(0o700)
            stopped = self.run_powerkit(
                "broker", "launch", "--target", str(target),
                "--effort", "FAST", "--risk", "NORMAL", "--platform", "codex",
                "--surface", "cli", "--constraint", "NO_NETWORK",
                "--client", str(root / "missing-client"), "--", "Do not run.",
            )
            self.assertEqual(stopped.returncode, 3, stopped.stderr)
            checkpoint = self.run_powerkit(
                "broker", "launch", "--target", str(target),
                "--effort", "FAST", "--risk", "NORMAL", "--platform", "codex",
                "--surface", "cli", "--constraint", "NO_DEPENDENCIES",
                "--client", str(client), "--", "Do the bounded task.",
            )
            self.assertEqual(checkpoint.returncode, 4, checkpoint.stderr)
            trace = Path(".ai-powerkit/traces/launcher.json")
            launched = self.run_powerkit(
                "broker", "launch", "--target", str(target),
                "--effort", "FAST", "--risk", "NORMAL", "--platform", "codex",
                "--surface", "cli", "--constraint", "NO_DEPENDENCIES",
                "--client", str(client), "--ack-checkpoint", "--trace", str(trace),
                "--task-id", "launcher-test",
                "--", "Do the bounded task.",
            )
            self.assertEqual(launched.returncode, 0, launched.stdout + launched.stderr)
            saved = json.loads((target / trace).read_text(encoding="utf-8"))
            self.assertEqual(saved["application"]["status"], "CLIENT_SUCCEEDED")
            self.assertTrue(saved["application"]["checkpoint_acknowledged"])
            self.assertTrue(
                all(
                    item["status"] == "SETTINGS_PASSED"
                    for item in saved["application"]["settings"]
                )
            )
            self.assertTrue(
                all(
                    saved["negotiation"]["controls"][item["control"]]["enforcement_status"]
                    == "APPLICATION_ATTEMPTED"
                    for item in saved["application"]["settings"]
                )
            )
            self.assertNotIn("Do the bounded task", json.dumps(saved))

    def test_client_probe_reports_live_success_and_unavailable(self) -> None:
        with mock.patch.object(broker, "_probe_candidates", return_value=[["client", "--version"]]), mock.patch.object(
            broker, "_run_version_probe", return_value=(0, "client 1.2.3\n", None)
        ):
            result = broker.probe_clients(("codex",))[0]
        self.assertEqual(result["status"], "VERSION_PROBED")
        with mock.patch.object(broker, "_probe_candidates", return_value=[["client", "--version"]]), mock.patch.object(
            broker, "_run_version_probe", return_value=(0, "client \x1b[2J1.2.3\n", None)
        ):
            sanitized = broker.probe_clients(("codex",))[0]
        self.assertNotIn("\x1b", sanitized["version"])
        self.assertIn("\\u001b", sanitized["version"])
        with mock.patch.object(broker, "_probe_candidates", return_value=[]):
            result = broker.probe_clients(("copilot",))[0]
        self.assertEqual(result["status"], "UNAVAILABLE")
        _, output, error = broker._run_version_probe(
            [PYTHON, "-c", "print('x' * 5000)"]
        )
        self.assertLessEqual(len(output.encode("utf-8")), 4096)
        self.assertEqual(error, "output exceeded 4096 bytes")

    def test_project_policy_validation_rejects_unknown_or_malformed_controls(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Unknown execution_policy fields"):
            broker.validate_project_policy({"imaginary": True})
        payload = broker.default_execution_policy()
        payload["max_parallel_agents"] = 0
        with self.assertRaisesRegex(RuntimeError, "integer from 1 to 16"):
            broker.validate_project_policy(payload)


if __name__ == "__main__":
    unittest.main()
