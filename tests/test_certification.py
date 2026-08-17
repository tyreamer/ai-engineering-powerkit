from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from powerkit import certification


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


class CertificationTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.corpus = certification.load_case_corpus()
        self.cases = {case["id"]: case for case in self.corpus["cases"]}

    def run_powerkit(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [PYTHON, "-m", "powerkit", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )

    def trace(
        self,
        case_id: str,
        condition: str,
        *,
        run_id: str | None = None,
        writes: list[str] | None = None,
        verification_status: str = "PASSED",
        adapter_version: str | None = None,
    ) -> dict:
        case = self.cases[case_id]
        if adapter_version is None and condition == "POWERKIT":
            adapter_version = "0.4.0"
        assertion_records = []
        for assertion in case["assertions"]:
            evidence = "verification:targeted"
            check_ids = [item["id"] for item in case["expected"]["verification_checks"]]
            if check_ids:
                evidence = f"verification:{check_ids[0]}"
            assertion_records.append(
                {"id": assertion["id"], "status": "PASS", "evidence_refs": [evidence]}
            )
        return {
            "kind": "powerkit-certification-trace",
            "schema_version": 1,
            "run_id": run_id or f"{case_id}-{condition.lower()}",
            "case_id": case_id,
            "condition": condition,
            "repetition": 1,
            "client": {
                "platform": "codex",
                "surface": "cli",
                "version": "test-client",
                "adapter_version": adapter_version,
            },
            "fixture": {
                "repository": case["fixture"]["repository"],
                "revision": case["fixture"]["revision"],
                "start_digest": case["fixture"]["sha256"],
                "end_digest": "b" * 64,
            },
            "environment": {
                "isolation_id": f"{condition.lower()}-isolation",
                "powerkit_assets_present": condition == "POWERKIT",
            },
            "routing": (
                None
                if condition == "VANILLA"
                else {
                    "intent": case["expected"]["intent"],
                    "effort": case["expected"]["effort"],
                    "risk": case["expected"]["risk"],
                    "workflows": ["verification-loop"],
                }
            ),
            "assertions": assertion_records,
            "effects": {"write_paths": writes or []},
            "verification": [
                {"id": item["id"], "status": verification_status}
                for item in case["expected"]["verification_checks"]
            ],
            "events": [
                {"id": "verification", "type": "VERIFICATION", "occurred_at": "2026-08-17T12:00:00Z"}
            ],
            "safety_events": [],
            "metrics": {
                "duration_ms": {"status": "OBSERVED", "value": 100},
                "turns": {"status": "OBSERVED", "value": 1},
                "context_tokens": {"status": "UNSUPPORTED", "value": None},
                "input_tokens": {"status": "UNOBSERVED", "value": None},
                "output_tokens": {"status": "UNOBSERVED", "value": None},
            },
            "final_status": "SUCCEEDED",
        }

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
            self.assertEqual(matches, 1, path)
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
            if "maxLength" in schema:
                self.assertLessEqual(len(instance), schema["maxLength"], path)
            if "pattern" in schema:
                self.assertRegex(instance, re.compile(schema["pattern"]), path)
        if isinstance(instance, (int, float)) and not isinstance(instance, bool):
            if "minimum" in schema:
                self.assertGreaterEqual(instance, schema["minimum"], path)
            if "maximum" in schema:
                self.assertLessEqual(instance, schema["maximum"], path)
        if isinstance(instance, dict):
            self.assertTrue(set(schema.get("required", ())) <= set(instance), path)
            properties = schema.get("properties", {})
            additional = schema.get("additionalProperties", True)
            for key, value in instance.items():
                if key in properties:
                    self.assert_schema_conforms(value, properties[key], root=root, path=f"{path}.{key}")
                elif additional is False:
                    self.fail(f"{path}: unexpected property {key!r}")
                elif isinstance(additional, dict):
                    self.assert_schema_conforms(value, additional, root=root, path=f"{path}.{key}")
        if isinstance(instance, list):
            if "minItems" in schema:
                self.assertGreaterEqual(len(instance), schema["minItems"], path)
            if "maxItems" in schema:
                self.assertLessEqual(len(instance), schema["maxItems"], path)
            if schema.get("uniqueItems"):
                serialized = [json.dumps(item, sort_keys=True) for item in instance]
                self.assertEqual(len(serialized), len(set(serialized)), path)
            if isinstance(schema.get("items"), dict):
                for index, value in enumerate(instance):
                    self.assert_schema_conforms(value, schema["items"], root=root, path=f"{path}[{index}]")

    def test_pilot_corpus_has_six_real_versioned_fixtures(self) -> None:
        self.assertEqual(self.corpus["schema_version"], 1)
        self.assertEqual(len(self.corpus["cases"]), 6)
        self.assertEqual(
            {case["category"] for case in self.corpus["cases"]},
            {"tiny_edit", "plan_only", "feature", "bug", "high_risk", "review"},
        )
        for case in self.corpus["cases"]:
            self.assertTrue((ROOT / case["fixture"]["repository"]).is_dir())
            totals = {name: 0 for name in certification.DIMENSION_LIMITS}
            for assertion in case["assertions"]:
                totals[assertion["dimension"]] += assertion["points"]
            self.assertEqual(totals, certification.DIMENSION_LIMITS)

    def test_fixture_baselines_expose_the_intended_behavior(self) -> None:
        expected_exit = {
            "tiny-bounded-edit": 1,
            "standard-multifile-feature": 0,
            "misleading-bug-hypothesis": 1,
            "high-risk-authorization": 1,
            "review-fake-integration": 0,
        }
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            for case_id, exit_code in expected_exit.items():
                fixture = ROOT / self.cases[case_id]["fixture"]["repository"]
                copy_root = temp_root / case_id
                shutil.copytree(fixture, copy_root)
                result = subprocess.run(
                    [PYTHON, "-m", "unittest", "-q"],
                    cwd=copy_root,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=30,
                )
                self.assertEqual(result.returncode, exit_code, case_id + result.stderr)

    def test_contract_instances_conform_to_versioned_schemas(self) -> None:
        case_schema = json.loads((ROOT / "schemas/certification-case-v1.schema.json").read_text())
        trace_schema = json.loads((ROOT / "schemas/certification-trace-v1.schema.json").read_text())
        result_schema = json.loads((ROOT / "schemas/certification-result-v1.schema.json").read_text())
        baseline = self.trace("tiny-bounded-edit", "VANILLA")
        treatment = self.trace("tiny-bounded-edit", "POWERKIT")
        validated_baseline = certification.validate_trace(baseline, self.cases["tiny-bounded-edit"])
        validated_treatment = certification.validate_trace(treatment, self.cases["tiny-bounded-edit"])
        result = certification.build_pilot_result(
            self.corpus, [validated_baseline, validated_treatment]
        )
        self.assert_schema_conforms(self.corpus, case_schema)
        self.assert_schema_conforms(baseline, trace_schema)
        self.assert_schema_conforms(treatment, trace_schema)
        self.assert_schema_conforms(result, result_schema)
        self.assertEqual(result["summary"]["complete_pairs"], 1)
        self.assertEqual(result["summary"]["incomplete_pairs"], 5)
        pair = next(item for item in result["pairs"] if item["case_id"] == "tiny-bounded-edit")
        self.assertEqual(pair["score_delta"], 0)

    def test_scoring_derives_unauthorized_write_and_fabricated_verification(self) -> None:
        trace = self.trace(
            "tiny-bounded-edit",
            "POWERKIT",
            writes=["outside.py"],
            verification_status="SKIPPED",
        )
        validated = certification.validate_trace(trace, self.cases["tiny-bounded-edit"])
        scored = certification.score_trace(validated, self.cases["tiny-bounded-edit"])
        self.assertTrue(scored["disqualified"])
        self.assertEqual(
            scored["safety_events"],
            ["FABRICATED_VERIFICATION", "UNAUTHORIZED_WRITE"],
        )
        self.assertEqual(scored["dimensions"]["constraint_preservation"]["earned"], 0)
        self.assertEqual(scored["dimensions"]["verification_quality"]["earned"], 0)

    def test_trace_rejects_baseline_contamination_unknown_fields_and_fake_refs(self) -> None:
        baseline = self.trace("tiny-bounded-edit", "VANILLA")
        baseline["client"]["adapter_version"] = "0.4.0"
        with self.assertRaisesRegex(RuntimeError, "Vanilla traces"):
            certification.validate_trace(baseline, self.cases["tiny-bounded-edit"])

        contaminated = self.trace("tiny-bounded-edit", "VANILLA")
        contaminated["environment"]["powerkit_assets_present"] = True
        with self.assertRaisesRegex(RuntimeError, "assets as absent"):
            certification.validate_trace(contaminated, self.cases["tiny-bounded-edit"])

        unknown = self.trace("tiny-bounded-edit", "POWERKIT")
        unknown["prompt_body"] = "must not be retained"
        with self.assertRaisesRegex(RuntimeError, "unsupported fields: prompt_body"):
            certification.validate_trace(unknown, self.cases["tiny-bounded-edit"])

        fake_ref = self.trace("tiny-bounded-edit", "POWERKIT")
        fake_ref["assertions"][0]["evidence_refs"] = ["event:missing"]
        with self.assertRaisesRegex(RuntimeError, "unknown evidence refs"):
            certification.validate_trace(fake_ref, self.cases["tiny-bounded-edit"])

    def test_trace_rejects_inferred_telemetry_and_future_schema(self) -> None:
        trace = self.trace("tiny-bounded-edit", "POWERKIT")
        trace["metrics"]["input_tokens"] = {"status": "UNOBSERVED", "value": 12}
        with self.assertRaisesRegex(RuntimeError, "must be null"):
            certification.validate_trace(trace, self.cases["tiny-bounded-edit"])
        future = self.trace("tiny-bounded-edit", "POWERKIT")
        future["schema_version"] = 2
        with self.assertRaisesRegex(RuntimeError, "Unsupported certification trace schema"):
            certification.validate_trace(future, self.cases["tiny-bounded-edit"])

    def test_trace_rejects_content_stuffing_and_oversized_files(self) -> None:
        stuffed = self.trace("tiny-bounded-edit", "POWERKIT")
        stuffed["client"]["version"] = "x" * 513
        with self.assertRaisesRegex(RuntimeError, "no longer than 512"):
            certification.validate_trace(stuffed, self.cases["tiny-bounded-edit"])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "oversized.json"
            path.write_text('{"padding":"' + ("x" * certification.MAX_JSON_BYTES) + '"}')
            with self.assertRaisesRegex(RuntimeError, "exceeds the"):
                certification.load_trace(path, self.cases)

    def test_cli_plans_without_launching_and_scores_complete_pair(self) -> None:
        plan = self.run_powerkit("certify", "pilot", "--json")
        self.assertEqual(plan.returncode, 0, plan.stdout + plan.stderr)
        payload = json.loads(plan.stdout)
        self.assertEqual(payload["mode"], "PLAN")
        self.assertEqual(payload["summary"]["case_count"], 6)
        self.assertEqual(payload["summary"]["trace_count"], 0)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            arguments = ["certify", "pilot"]
            for case_id in self.cases:
                for condition in ("VANILLA", "POWERKIT"):
                    trace_path = root / f"{case_id}-{condition.lower()}.json"
                    trace_path.write_text(json.dumps(self.trace(case_id, condition)))
                    arguments.extend(["--trace", str(trace_path)])
            arguments.append("--json")
            scored = self.run_powerkit(*arguments)
        self.assertEqual(scored.returncode, 0, scored.stdout + scored.stderr)
        result = json.loads(scored.stdout)
        self.assertEqual(result["mode"], "SCORE")
        self.assertEqual(result["summary"]["complete_pairs"], 6)
        self.assertEqual(result["summary"]["incomplete_pairs"], 0)

    def test_cli_incomplete_pair_is_preserved_and_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            trace_path = Path(temp) / "treatment.json"
            trace_path.write_text(json.dumps(self.trace("tiny-bounded-edit", "POWERKIT")))
            result = self.run_powerkit(
                "certify", "pilot", "--trace", str(trace_path), "--json"
            )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["incomplete_pairs"], 6)
        pair = next(item for item in payload["pairs"] if item["case_id"] == "tiny-bounded-edit")
        self.assertEqual(pair["status"], "INCOMPLETE")

    def test_corpus_rejects_duplicate_ids_and_fixture_traversal(self) -> None:
        duplicate = copy.deepcopy(self.corpus)
        duplicate["cases"][1]["id"] = duplicate["cases"][0]["id"]
        with self.assertRaisesRegex(RuntimeError, "Duplicate certification case id"):
            certification.validate_case_corpus(duplicate)
        traversal = copy.deepcopy(self.corpus)
        traversal["cases"][0]["fixture"]["repository"] = "../outside"
        with self.assertRaisesRegex(RuntimeError, "contained relative POSIX path"):
            certification.validate_case_corpus(traversal)
        windows_escape = copy.deepcopy(self.corpus)
        windows_escape["cases"][0]["expected"]["allowed_write_paths"] = ["..\\outside"]
        with self.assertRaisesRegex(RuntimeError, "contained relative POSIX path"):
            certification.validate_case_corpus(windows_escape)


if __name__ == "__main__":
    unittest.main()
