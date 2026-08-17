from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from powerkit.proof import (
    build_proof,
    configured_proof_root,
    load_proof,
    load_task_spec,
    proof_freshness,
    refresh_report,
    render_completion_brief,
    snapshot_changes,
)
from powerkit.verification import repository_fingerprint, run_verification


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class ProofPackTests(unittest.TestCase):
    maxDiff = None

    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        (repo / ".gitignore").write_text(
            ".ai-powerkit/proofs/\n.ai-powerkit/verification/\n", encoding="utf-8"
        )
        (repo / "app.py").write_text("print('before')\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "proof@example.invalid"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Proof Test"], cwd=repo, check=True)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo, check=True)
        (repo / "app.py").write_text("print('after')\n", encoding="utf-8")
        return repo

    def spec(
        self,
        *,
        task_id: str = "feature-proof",
        depth: str = "STANDARD",
        task_types: list[str] | None = None,
        modules: dict | None = None,
        caveats: list[str] | None = None,
        artifacts: list[dict] | None = None,
        independent_path: str | None = None,
    ) -> dict:
        return {
            "schema_version": 1,
            "task": {
                "id": task_id,
                "title": "Proof Pack feature",
                "summary": "Added a comprehensible, execution-backed completion proof.",
                "depth": depth,
                "types": task_types or ["feature"],
                "implementation_state": "complete",
                "requested": ["Make completed work understandable and trustworthy."],
                "delivered": ["Created a canonical proof manifest and human brief."],
                "not_included": ["No hosted dashboard."],
            },
            "changes": [
                {
                    "path": "app.py",
                    "summary": "Changed the representative application behavior.",
                    "change_type": "modified",
                    "component": "application",
                }
            ],
            "understand": [
                {
                    "name": "Proof builder",
                    "responsibility": "Derives status from execution evidence.",
                    "maintenance_note": "Change status rules here first.",
                }
            ],
            "preserved": ["Existing verification command configuration is unchanged."],
            "caveats": caveats or [],
            "risks": [],
            "modules": modules
            or {
                "feature": {
                    "capability": "Developers now receive a completion proof.",
                    "experience_change": "Evidence is progressively disclosed.",
                    "before": ["Raw file and test lists"],
                    "after": ["Outcome first", "Evidence on demand"],
                }
            },
            "artifacts": artifacts or [],
            "independent_verification_path": independent_path,
        }

    @staticmethod
    def evidence(repo: Path, *statuses: str, levels: list[str] | None = None) -> dict:
        if levels is None:
            if not statuses:
                levels = ["targeted"]
                statuses = ("skipped",)
            elif len(statuses) == 1:
                levels = ["static", "targeted", "broader", "runtime"]
                statuses = statuses * 4
            else:
                levels = ["static", "targeted", "broader", "runtime"][: len(statuses)]
        if len(levels) != len(statuses):
            raise AssertionError("Test evidence levels and statuses must align.")
        records = []
        for index, (level, status) in enumerate(zip(levels, statuses, strict=True)):
            records.append(
                {
                    "level": level,
                    "label": f"Behavior check {index + 1}",
                    "status": status,
                    "reason": None if status != "skipped" else "Not configured.",
                    "command": f"check-{index + 1}",
                    "exit_code": 0 if status == "passed" else (1 if status == "failed" else None),
                    "duration_seconds": 0.01 if status != "skipped" else None,
                    "started_at": "2026-08-17T12:00:00+00:00" if status != "skipped" else None,
                    "provenance": "configured-command-runner",
                }
            )
        return {
            "format": "powerkit-verification-evidence",
            "schema_version": 1,
            "generated_at": "2026-08-17T12:00:01+00:00",
            "repository": repository_fingerprint(repo),
            "requested_levels": list(dict.fromkeys(levels)),
            "records": records,
            "summary": {
                "executed": sum(status != "skipped" for status in statuses),
                "passed": sum(status == "passed" for status in statuses),
                "failed": sum(status in {"failed", "timed_out"} for status in statuses),
                "skipped": sum(status == "skipped" for status in statuses),
            },
        }

    def build(self, repo: Path, spec: dict, evidence: dict, **kwargs):
        return build_proof(
            repo,
            spec,
            evidence,
            output_root=repo / ".ai-powerkit/proofs",
            trust_current_run=True,
            **kwargs,
        )

    def test_execution_evidence_derives_truthful_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            _, passed = self.build(repo, self.spec(task_id="passed"), self.evidence(repo, "passed"))
            _, failed = self.build(repo, self.spec(task_id="failed"), self.evidence(repo, "failed"))
            _, partial = self.build(
                repo, self.spec(task_id="partial"), self.evidence(repo, "passed", "skipped")
            )
            self.assertEqual(passed["outcome"]["status"], "VERIFIED")
            self.assertEqual(failed["outcome"]["status"], "FAILED_VERIFICATION")
            self.assertEqual(partial["outcome"]["status"], "PARTIALLY_VERIFIED")
            self.assertNotIn("Complete and verified", render_completion_brief(failed))

    def test_depth_policy_controls_html_and_high_risk_independence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            fast_dir, fast = self.build(repo, self.spec(task_id="fast", depth="FAST"), self.evidence(repo))
            standard_dir, _ = self.build(repo, self.spec(task_id="standard"), self.evidence(repo, "passed"))
            deep_dir, _ = self.build(repo, self.spec(task_id="deep", depth="DEEP"), self.evidence(repo, "passed"))
            _, risk = self.build(repo, self.spec(task_id="risk", depth="HIGH_RISK"), self.evidence(repo, "passed"))
            self.assertEqual(fast["outcome"]["status"], "IMPLEMENTED")
            self.assertFalse((fast_dir / "report.html").exists())
            self.assertFalse((standard_dir / "report.html").exists())
            self.assertTrue((deep_dir / "report.html").is_file())
            self.assertEqual(risk["outcome"]["status"], "PARTIALLY_VERIFIED")

            verifier_dir = repo / ".ai-powerkit/verification"
            verifier_dir.mkdir(parents=True)
            verifier = verifier_dir / "verifier.json"
            verified_spec = self.spec(
                task_id="risk-verified",
                depth="HIGH_RISK",
                independent_path=".ai-powerkit/verification/verifier.json",
            )
            verifier.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "role": "independent-verifier",
                        "task_id": "risk-verified",
                        "repository": repository_fingerprint(repo),
                        "source_snapshot_digest": snapshot_changes(
                            repo, verified_spec["changes"]
                        )["digest"],
                        "verdict": "pass",
                        "summary": "Independently reproduced the protected behavior.",
                        "checks": [{"name": "Negative path", "status": "passed"}],
                    }
                ),
                encoding="utf-8",
            )
            _, verified = self.build(
                repo,
                verified_spec,
                self.evidence(repo, "passed"),
            )
            self.assertEqual(verified["outcome"]["status"], "VERIFIED")
            self.assertEqual(verified["independent_verification"]["provenance"]["role"], "independent-verifier")

    def test_standard_ui_generates_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            proof_dir, _ = self.build(
                repo,
                self.spec(task_id="ui", task_types=["ui"], modules={"ui": {"states": []}}),
                self.evidence(repo, "passed"),
            )
            self.assertTrue((proof_dir / "report.html").is_file())

    def test_stale_detection_survives_relocation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            proof_dir, proof = self.build(repo, self.spec(task_id="fresh"), self.evidence(repo, "passed"))
            self.assertEqual(proof_freshness(repo, proof)["status"], "current")
            moved = root / "moved"
            relative_proof = proof_dir.relative_to(repo)
            repo.rename(moved)
            relocated = load_proof(moved / relative_proof)
            self.assertEqual(proof_freshness(moved, relocated)["status"], "current")
            (moved / "app.py").write_text("print('later')\n", encoding="utf-8")
            self.assertEqual(
                proof_freshness(moved, relocated)["changed_files"],
                ["repository worktree", "app.py"],
            )

    def test_imported_stale_evidence_cannot_verify(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            evidence = self.evidence(repo, "passed")
            (repo / "other.py").write_text("changed after test\n", encoding="utf-8")
            _, proof = build_proof(
                repo,
                self.spec(task_id="stale-evidence"),
                evidence,
                output_root=repo / ".ai-powerkit/proofs",
                trust_current_run=False,
            )
            self.assertFalse(proof["verification_evidence"]["fresh"])
            self.assertEqual(proof["outcome"]["status"], "PARTIALLY_VERIFIED")

    def test_html_escapes_hostile_content_and_redacts_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            spec = self.spec(task_id="hostile", depth="DEEP")
            spec["task"]["title"] = '<script src="https://evil.invalid/x.js">alert(1)</script>'
            spec["task"]["summary"] = "password=hunter2 <img src=x onerror=alert(1)>"
            path = repo / "spec.json"
            path.write_text(json.dumps(spec), encoding="utf-8")
            normalized = load_task_spec(path)
            proof_dir, proof = self.build(repo, normalized, self.evidence(repo, "passed"))
            report = (proof_dir / "report.html").read_text(encoding="utf-8")
            self.assertNotIn("<script", report.lower())
            self.assertNotIn('src="https://evil.invalid', report)
            self.assertNotIn("<img src=x", report)
            self.assertIn("&lt;script", report)
            self.assertNotIn("hunter2", report + json.dumps(proof))
            self.assertIn("default-src 'none'", report)

    def test_command_output_and_environment_are_not_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            (repo / "command-output.txt").write_text("DO_NOT_STORE_OUTPUT\n", encoding="utf-8")
            config = repo / "project.json"
            config.write_text(
                json.dumps(
                    {
                        "verification": {
                            "static": [{"label": "Static proof", "command": f'{PYTHON} -c "print(open(\'command-output.txt\').read())"'}],
                            "targeted": [],
                            "broader": [],
                            "runtime": [],
                        }
                    }
                ),
                encoding="utf-8",
            )
            evidence, code = run_verification(repo, config, ["static"], stream=False)
            self.assertEqual(code, 0)
            proof_dir, proof = self.build(repo, self.spec(task_id="privacy"), evidence)
            serialized = (proof_dir / "proof.json").read_text(encoding="utf-8")
            self.assertNotIn("DO_NOT_STORE_OUTPUT", serialized)
            self.assertFalse(proof["privacy"]["environment_captured"])
            self.assertFalse(proof["privacy"]["prompt_history_captured"])

    def test_artifacts_handle_missing_sensitive_raster_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            repo = self.make_repo(Path(temp))
            (repo / "secret.log").write_text("api_key=super-secret-value\n", encoding="utf-8")
            (repo / "after.png").write_bytes(PNG_1X1)
            artifacts = [
                {"id": "missing", "label": "Missing", "kind": "screenshot", "path": "missing.png"},
                {"id": "secret", "label": "Sensitive", "kind": "log", "path": "secret.log", "sensitivity": "sensitive"},
                {"id": "after", "label": "After", "kind": "screenshot", "path": "after.png"},
            ]
            proof_dir, proof = self.build(
                repo,
                self.spec(
                    task_id="artifacts",
                    task_types=["ui"],
                    modules={"ui": {"after_artifact": "after"}},
                    artifacts=artifacts,
                ),
                self.evidence(repo, "passed"),
            )
            statuses = {item["id"]: item["status"] for item in proof["artifacts"]}
            self.assertEqual(statuses, {"missing": "missing", "secret": "withheld", "after": "available"})
            report = (proof_dir / "report.html").read_text(encoding="utf-8")
            self.assertIn("data:image/png;base64,", report)
            self.assertNotIn("super-secret-value", (proof_dir / "proof.json").read_text(encoding="utf-8"))

            external = Path(outside) / "outside.png"
            external.write_bytes(PNG_1X1)
            link = repo / "linked.png"
            try:
                link.symlink_to(external)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            with self.assertRaisesRegex(RuntimeError, "symlinked artifact path"):
                self.build(
                    repo,
                    self.spec(
                        task_id="symlink",
                        artifacts=[{"id": "linked", "label": "Linked", "kind": "screenshot", "path": "linked.png"}],
                    ),
                    self.evidence(repo, "passed"),
                )

    def test_all_adaptive_modules_render_only_when_selected(self) -> None:
        scenarios = {
            "feature": ({"feature": {"capability": "Capability marker"}}, "Capability marker"),
            "bug": ({"bug": {"root_cause": "Root cause marker"}}, "Root cause marker"),
            "ui": ({"ui": {"limitation": "UI limitation marker"}}, "UI limitation marker"),
            "architecture": ({"architecture": {"after": "Architecture marker"}}, "Architecture marker"),
            "migration": ({"migration": {"rollback": "Rollback marker"}}, "Rollback marker"),
            "database": ({"database": {"new_state": "Database marker"}}, "Database marker"),
            "security": ({"security": {"controls": ["Security marker"]}}, "Security marker"),
            "performance": ({"performance": {"measurements": [{"scenario": "Performance marker", "before": "2s", "after": "1s"}]}}, "Performance marker"),
            "dependency": ({"dependency": {"decision": "Dependency marker"}}, "Dependency marker"),
            "review": ({"review": {"criteria": [{"name": "Review marker"}]}}, "Review marker"),
            "refactor": ({"refactor": {"compatibility": "Refactor marker"}}, "Refactor marker"),
            "general": ({"general": {"notes": ["General marker"]}}, "General marker"),
        }
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            for index, (task_type, (modules, marker)) in enumerate(scenarios.items()):
                proof_dir, _ = self.build(
                    repo,
                    self.spec(task_id=f"module-{index}", depth="DEEP", task_types=[task_type], modules=modules),
                    self.evidence(repo, "passed"),
                )
                self.assertIn(marker, (proof_dir / "report.html").read_text(encoding="utf-8"), task_type)

    def test_unknown_future_module_keeps_common_shell_without_core_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            spec_path = repo / "future.json"
            spec = self.spec(
                task_id="future-module",
                depth="DEEP",
                task_types=["future-proof"],
                modules={"future-proof": {"notes": ["Future module detail"]}},
            )
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            normalized = load_task_spec(spec_path)
            proof_dir, _ = self.build(repo, normalized, self.evidence(repo, "passed"))
            report = (proof_dir / "report.html").read_text(encoding="utf-8")
            self.assertIn("Proof Pack feature", report)
            self.assertNotIn("Future module detail", report)

    def test_imported_evidence_invariants_coverage_privacy_and_failure_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            one_level = self.evidence(repo, "passed", levels=["static"])
            _, partial = self.build(
                repo,
                self.spec(task_id="coverage", depth="DEEP"),
                one_level,
            )
            self.assertEqual(partial["outcome"]["status"], "PARTIALLY_VERIFIED")

            contradictory = json.loads(json.dumps(one_level))
            contradictory["records"][0]["exit_code"] = 23
            with self.assertRaisesRegex(RuntimeError, "exit code 0"):
                self.build(
                    repo,
                    self.spec(task_id="contradictory"),
                    contradictory,
                )

            private_fields = self.evidence(repo, "passed")
            private_fields["records"][0].update(
                {
                    "stdout": "DO_NOT_PERSIST_STDOUT",
                    "environment": {"TOKEN": "DO_NOT_PERSIST_ENV"},
                    "prompt": "DO_NOT_PERSIST_PROMPT",
                }
            )
            proof_dir, _ = self.build(
                repo,
                self.spec(task_id="private-import"),
                private_fields,
            )
            serialized = (proof_dir / "proof.json").read_text(encoding="utf-8")
            self.assertNotIn("DO_NOT_PERSIST", serialized)

            secret_spec = self.spec(
                task_id="key-redaction",
                depth="DEEP",
                task_types=["security"],
                modules={
                    "security": {
                        "controls": [
                            {
                                "api_key": "NESTED_SECRET_SENTINEL",
                                "contact": "private.person@example.com",
                            }
                        ]
                    }
                },
            )
            spec_path = repo / "secret-spec.json"
            spec_path.write_text(json.dumps(secret_spec), encoding="utf-8")
            normalized = load_task_spec(spec_path)
            proof_dir, _ = self.build(repo, normalized, self.evidence(repo, "passed"))
            serialized = (proof_dir / "proof.json").read_text(encoding="utf-8")
            self.assertNotIn("NESTED_SECRET_SENTINEL", serialized)
            self.assertNotIn("private.person@example.com", serialized)
            self.assertIn("[REDACTED]", serialized)
            self.assertIn("[REDACTED_EMAIL]", serialized)

            partial_spec = self.spec(task_id="partial-failure")
            partial_spec["task"]["implementation_state"] = "partial"
            _, failed = self.build(repo, partial_spec, self.evidence(repo, "failed"))
            self.assertEqual(failed["outcome"]["status"], "FAILED_VERIFICATION")

    def test_module_claims_require_canonical_evidence_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            (repo / "after.png").write_bytes(PNG_1X1)
            unlinked_modules = {
                "ui": {
                    "states": [
                        {"name": "Keyboard accessibility", "status": "verified"}
                    ]
                }
            }
            proof_dir, proof = self.build(
                repo,
                self.spec(
                    task_id="unlinked-claim",
                    task_types=["ui"],
                    modules=unlinked_modules,
                ),
                self.evidence(repo, "passed"),
            )
            self.assertEqual(
                proof["modules"]["ui"]["states"][0]["evidence_status"],
                "not_verified",
            )
            report = (proof_dir / "report.html").read_text(encoding="utf-8")
            self.assertIn(
                "<strong>Keyboard accessibility</strong><span>Not verified</span>",
                report,
            )

            linked_modules = {
                "ui": {
                    "after_artifact": "after",
                    "states": [
                        {
                            "name": "Captured desktop viewport",
                            "status": "verified",
                            "evidence_refs": ["artifact:after"],
                        },
                        {
                            "name": "Targeted behavior",
                            "evidence_refs": ["verification:targeted"],
                        },
                    ],
                }
            }
            _, linked = self.build(
                repo,
                self.spec(
                    task_id="linked-claim",
                    task_types=["ui"],
                    modules=linked_modules,
                    artifacts=[
                        {
                            "id": "after",
                            "label": "After",
                            "kind": "screenshot",
                            "path": "after.png",
                        }
                    ],
                ),
                self.evidence(repo, "passed"),
            )
            self.assertEqual(
                [item["evidence_status"] for item in linked["modules"]["ui"]["states"]],
                ["verified", "verified"],
            )

            contradictory_review = self.spec(
                task_id="review-contradiction",
                depth="DEEP",
                task_types=["review"],
                modules={
                    "review": {
                        "verdict": "Ready to merge",
                        "criteria": [{"name": "Review complete", "status": "passed"}],
                    }
                },
            )
            review_dir, review = self.build(
                repo,
                contradictory_review,
                self.evidence(repo, "passed", levels=["static"]),
            )
            self.assertEqual(review["outcome"]["status"], "PARTIALLY_VERIFIED")
            report = (review_dir / "report.html").read_text(encoding="utf-8")
            self.assertNotIn("Ready to merge", report)
            self.assertIn("Additional verification is required before merge.", report)
            self.assertIn("<strong>Review complete</strong><span>Not verified</span>", report)

    def test_repository_bundle_and_verifier_freshness_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            (repo / "after.png").write_bytes(PNG_1X1)
            proof_dir, proof = self.build(
                repo,
                self.spec(
                    task_id="bundle-integrity",
                    depth="DEEP",
                    task_types=["ui"],
                    modules={"ui": {"after_artifact": "after"}},
                    artifacts=[
                        {
                            "id": "after",
                            "label": "After",
                            "kind": "screenshot",
                            "path": "after.png",
                        }
                    ],
                ),
                self.evidence(repo, "passed"),
            )
            (repo / "undeclared.py").write_text("changed later\n", encoding="utf-8")
            freshness = proof_freshness(repo, proof, proof_dir)
            self.assertEqual(freshness["status"], "stale")
            self.assertIn("repository worktree", freshness["changed_files"])
            (repo / "undeclared.py").unlink()

            stored = proof_dir / proof["artifacts"][0]["stored_path"]
            stored.write_bytes(b"tampered image bytes")
            freshness = proof_freshness(repo, proof, proof_dir)
            self.assertIn("artifact: After", freshness["changed_files"])
            refresh_report(repo, proof_dir, proof)
            report = (proof_dir / "report.html").read_text(encoding="utf-8")
            self.assertIn("Artifact unavailable: integrity check failed", report)

            outside = proof_dir.parent / "outside.png"
            outside.write_bytes(b"OUTSIDE_BUNDLE_SENTINEL")
            proof["artifacts"][0]["stored_path"] = "../outside.png"
            refresh_report(repo, proof_dir, proof)
            report = (proof_dir / "report.html").read_text(encoding="utf-8")
            self.assertNotIn(base64.b64encode(b"OUTSIDE_BUNDLE_SENTINEL").decode(), report)
            self.assertIn("Artifact unavailable: integrity check failed", report)

    def test_independent_verifier_binding_and_consistency(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            verifier_dir = repo / ".ai-powerkit/verification"
            verifier_dir.mkdir(parents=True)
            spec = self.spec(
                task_id="bound-risk",
                depth="HIGH_RISK",
                independent_path=".ai-powerkit/verification/verifier.json",
            )
            snapshot = snapshot_changes(repo, spec["changes"])
            payload = {
                "schema_version": 1,
                "role": "independent-verifier",
                "task_id": "bound-risk",
                "repository": repository_fingerprint(repo),
                "source_snapshot_digest": snapshot["digest"],
                "verdict": "pass",
                "summary": "Independent check completed.",
                "checks": [{"name": "Negative path", "status": "passed"}],
            }
            verifier = verifier_dir / "verifier.json"

            wrong_task = dict(payload, task_id="another-task")
            verifier.write_text(json.dumps(wrong_task), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "different task"):
                self.build(repo, spec, self.evidence(repo, "passed"))

            empty_checks = dict(payload, checks=[])
            verifier.write_text(json.dumps(empty_checks), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "non-empty"):
                self.build(repo, spec, self.evidence(repo, "passed"))

            verifier.write_text(json.dumps(payload), encoding="utf-8")
            (repo / "later.py").write_text("repository changed\n", encoding="utf-8")
            _, stale = self.build(repo, spec, self.evidence(repo, "passed"))
            self.assertEqual(stale["outcome"]["status"], "PARTIALLY_VERIFIED")
            self.assertFalse(stale["independent_verification"]["fresh"])
            self.assertTrue(
                any("task-bound independent" in caveat for caveat in stale["caveats"])
            )

    def test_timeout_stops_descendants_and_config_symlinks_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            repo = self.make_repo(Path(temp))
            parent = repo / "parent.py"
            marker = repo / "late-marker.txt"
            child_code = (
                "import pathlib,signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                "time.sleep(2); "
                "pathlib.Path('late-marker.txt').write_text('survived')"
            )
            parent.write_text(
                "import subprocess,sys,time\n"
                f"subprocess.Popen([sys.executable, '-c', {child_code!r}])\n"
                "time.sleep(10)\n",
                encoding="utf-8",
            )
            config = repo / "timeout.json"
            config.write_text(
                json.dumps(
                    {
                        "verification": {
                            "static": [f"{PYTHON} parent.py"],
                            "targeted": [],
                            "broader": [],
                            "runtime": [],
                        }
                    }
                ),
                encoding="utf-8",
            )
            evidence, code = run_verification(
                repo, config, ["static"], timeout=1, stream=False
            )
            self.assertNotEqual(code, 0)
            self.assertEqual(evidence["records"][0]["status"], "timed_out")
            time.sleep(2.2)
            self.assertFalse(marker.exists())

            external = Path(outside) / "config.json"
            external.write_text(config.read_text(encoding="utf-8"), encoding="utf-8")
            linked = repo / "linked-config.json"
            try:
                linked.symlink_to(external)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            with self.assertRaisesRegex(RuntimeError, "symlinked verification config"):
                run_verification(repo, linked, ["static"], stream=False)

            external_dir = Path(outside) / "config-parent"
            external_dir.mkdir()
            (external_dir / "project.json").write_text(
                config.read_text(encoding="utf-8"), encoding="utf-8"
            )
            linked_parent = repo / "linked-parent"
            linked_parent.symlink_to(external_dir, target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, "symlinked verification config path"):
                run_verification(
                    repo,
                    linked_parent / "project.json",
                    ["static"],
                    stream=False,
                )

    def test_custom_proof_output_is_excluded_from_repository_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            config_dir = repo / ".ai-powerkit"
            config_dir.mkdir()
            (config_dir / "project.json").write_text(
                json.dumps(
                    {
                        "proof": {
                            "output_directory": ".ai-powerkit/custom-proofs"
                        }
                    }
                ),
                encoding="utf-8",
            )
            before = repository_fingerprint(repo)
            generated = config_dir / "custom-proofs/example"
            generated.mkdir(parents=True)
            (generated / "proof.json").write_text("generated state\n", encoding="utf-8")
            self.assertEqual(repository_fingerprint(repo), before)

            tracked = config_dir / "custom-proofs/README.md"
            tracked.write_text("tracked guidance\n", encoding="utf-8")
            subprocess.run(["git", "add", str(tracked)], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "track proof guidance"], cwd=repo, check=True)
            tracked_before = repository_fingerprint(repo)
            tracked.write_text("changed tracked guidance\n", encoding="utf-8")
            self.assertNotEqual(repository_fingerprint(repo), tracked_before)

            (config_dir / "project.json").write_text(
                json.dumps({"proof": {"output_directory": "src"}}),
                encoding="utf-8",
            )
            source_dir = repo / "src"
            source_dir.mkdir()
            source = source_dir / "app.py"
            source.write_text("before = True\n", encoding="utf-8")
            subprocess.run(["git", "add", "src/app.py"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "track source"], cwd=repo, check=True)
            unsafe_before = repository_fingerprint(repo)
            source.write_text("before = False\n", encoding="utf-8")
            self.assertNotEqual(repository_fingerprint(repo), unsafe_before)
            with self.assertRaisesRegex(RuntimeError, "dedicated generated state"):
                configured_proof_root(repo)

    def test_report_failure_preserves_machine_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            with mock.patch("powerkit.proof_render.render_html_report", side_effect=RuntimeError("template broke")):
                proof_dir, proof = self.build(
                    repo, self.spec(task_id="render-failure", depth="DEEP"), self.evidence(repo, "passed")
                )
            self.assertEqual(proof["outcome"]["status"], "VERIFIED")
            self.assertEqual(proof["presentation"]["report"]["status"], "failed")
            self.assertTrue((proof_dir / "proof.json").is_file())

    def test_spec_config_schema_and_cleanup_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            path = repo / "spec.json"
            path.write_text(json.dumps(self.spec()), encoding="utf-8")
            self.assertEqual(load_task_spec(path)["task"]["id"], "feature-proof")
            config_dir = repo / ".ai-powerkit"
            config_dir.mkdir()
            (config_dir / "project.json").write_text(
                json.dumps({"proof": {"output_directory": ".ai-powerkit/custom-proofs"}}), encoding="utf-8"
            )
            self.assertEqual(
                configured_proof_root(repo).resolve(),
                (repo / ".ai-powerkit/custom-proofs").resolve(),
            )
            schema = json.loads((ROOT / "schemas/proof-manifest.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(schema["properties"]["schema_version"]["const"], 1)
            self.assertTrue((ROOT / ".git").is_dir())

            unmanaged = repo / ".ai-powerkit/proofs/feature-proof"
            unmanaged.mkdir(parents=True)
            sentinel = unmanaged / "user-owned.txt"
            sentinel.write_text("preserve me\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "proof manifest"):
                self.build(repo, self.spec(), self.evidence(repo, "passed"), replace=True)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve me\n")

    def test_failed_atomic_replacement_restores_the_previous_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            spec = self.spec(task_id="atomic-replace")
            proof_dir, _ = self.build(repo, spec, self.evidence(repo, "passed"))
            before = (proof_dir / "proof.json").read_bytes()
            real_replace = os.replace
            calls = 0

            def fail_new_proof(source, destination):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated destination failure")
                return real_replace(source, destination)

            with mock.patch("powerkit.proof.os.replace", side_effect=fail_new_proof):
                with self.assertRaisesRegex(OSError, "simulated destination failure"):
                    self.build(
                        repo,
                        spec,
                        self.evidence(repo, "passed"),
                        replace=True,
                    )
            self.assertEqual((proof_dir / "proof.json").read_bytes(), before)
            self.assertEqual(load_proof(proof_dir)["task"]["id"], "atomic-replace")

    def test_cli_list_show_delete_and_unsupported_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            self.build(repo, self.spec(task_id="lifecycle"), self.evidence(repo, "passed"))
            for args in (
                ("list", "--target", str(repo)),
                ("show", "lifecycle", "--target", str(repo)),
                ("delete", "lifecycle", "--target", str(repo), "--yes"),
            ):
                result = subprocess.run(
                    [PYTHON, "-m", "powerkit", "proof", *args],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((repo / ".ai-powerkit/proofs/lifecycle").exists())

            malformed, _ = self.build(
                repo,
                self.spec(task_id="malformed"),
                self.evidence(repo, "passed"),
            )
            malformed_path = malformed / "proof.json"
            malformed_payload = json.loads(malformed_path.read_text(encoding="utf-8"))
            malformed_payload["task"]["delivered"] = 7
            malformed_path.write_text(json.dumps(malformed_payload), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "task delivered"):
                load_proof(malformed)
            result = subprocess.run(
                [
                    PYTHON,
                    "-m",
                    "powerkit",
                    "proof",
                    "show",
                    "malformed",
                    "--target",
                    str(repo),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stderr)

            invalid = repo / ".ai-powerkit/proofs/invalid"
            invalid.mkdir()
            path = invalid / "proof.json"
            path.write_text(json.dumps({"kind": "powerkit-proof", "schema_version": 99}), encoding="utf-8")
            before = path.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "Unsupported proof schema"):
                load_proof(invalid)
            self.assertEqual(path.read_bytes(), before)
            result = subprocess.run(
                [
                    PYTHON,
                    "-m",
                    "powerkit",
                    "proof",
                    "delete",
                    "invalid",
                    "--target",
                    str(repo),
                    "--yes",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
