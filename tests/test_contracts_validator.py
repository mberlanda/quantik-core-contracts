from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_contracts.py"


class ContractsValidatorTests(unittest.TestCase):
    def test_repository_contracts_validate(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                "--manifest",
                "contracts.json",
                "--schema-glob",
                "schemas/**/*.json",
                "--schema-glob",
                "fixtures/parquet/*.json",
                "--fixture-glob",
                "fixtures/**/*.jsonl",
                "--expected-release",
                "1.3.0",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def _run_validator_with_schema(
        self, document: dict, expected_error: str
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bad_schema = Path(temp_dir) / "arrow-parquet-selfplay-v1.json"
            bad_schema.write_text(json.dumps(document), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--manifest",
                    "contracts.json",
                    "--schema-glob",
                    str(bad_schema),
                    "--expected-release",
                    "1.3.0",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn(expected_error, result.stderr)

    def _load_arrow_parquet_schema(self) -> dict:
        schema_path = ROOT / "schemas" / "arrow-parquet-selfplay-v1.json"
        return json.loads(schema_path.read_text(encoding="utf-8"))

    def test_arrow_parquet_selfplay_requires_logical_contract(self) -> None:
        document = self._load_arrow_parquet_schema()
        document.pop("logical_contract")
        self._run_validator_with_schema(document, "logical_contract must be selfplay.v1")

    def test_arrow_parquet_selfplay_requires_storage_parquet(self) -> None:
        document = self._load_arrow_parquet_schema()
        document.pop("storage")
        self._run_validator_with_schema(document, "storage must be parquet")

    def test_arrow_parquet_selfplay_requires_parquet_metadata_physical_schema(self) -> None:
        document = self._load_arrow_parquet_schema()
        document["parquet_metadata"]["physical_schema"] = "selfplay.v1"
        self._run_validator_with_schema(
            document,
            "parquet_metadata.physical_schema must be arrow-parquet-selfplay.v1",
        )

    def test_arrow_parquet_selfplay_requires_parquet_metadata_release_placeholder(self) -> None:
        document = self._load_arrow_parquet_schema()
        document["parquet_metadata"]["contracts_release"] = "1.2.0"
        self._run_validator_with_schema(
            document,
            "parquet_metadata.contracts_release must be contracts.json.release_version",
        )

    def test_arrow_parquet_selfplay_rejects_extra_column(self) -> None:
        document = self._load_arrow_parquet_schema()
        document["columns"].append({"name": "extra", "type": "utf8", "required": False})
        self._run_validator_with_schema(document, "must define 9 columns")

    def test_arrow_parquet_selfplay_rejects_missing_required_column(self) -> None:
        document = self._load_arrow_parquet_schema()
        document["columns"] = [
            column for column in document["columns"] if column["name"] != "policy_visits"
        ]
        self._run_validator_with_schema(document, "must define 9 columns")

    def test_arrow_parquet_selfplay_requires_policy_visits_column(self) -> None:
        document = self._load_arrow_parquet_schema()
        document["columns"][6]["name"] = "policy"
        self._run_validator_with_schema(document, "column 6 name must be policy_visits")

    def _load_search_summary_schema(self) -> dict:
        schema_path = ROOT / "schemas" / "search-summary-v1.json"
        return json.loads(schema_path.read_text(encoding="utf-8"))

    def test_search_summary_rejects_extra_column(self) -> None:
        document = self._load_search_summary_schema()
        document["columns"].append({"name": "extra", "type": "utf8", "required": False})
        self._run_validator_with_schema(document, "must define 33 columns")

    def test_search_summary_requires_generated_nodes_column(self) -> None:
        # generated_nodes and canonical_dedup_hits are part of the normative
        # counter set and must be present (the earlier design doc omitted them).
        document = self._load_search_summary_schema()
        document["columns"][26]["name"] = "gen_nodes"
        self._run_validator_with_schema(
            document, "column 26 name must be generated_nodes"
        )

    def test_search_summary_requires_engine_kind_allowed(self) -> None:
        document = self._load_search_summary_schema()
        document["columns"][10]["allowed"] = ["mcts"]
        self._run_validator_with_schema(
            document, "engine_kind allowed values must be"
        )

    def test_search_summary_requires_policy_mass_kind_allowed(self) -> None:
        document = self._load_search_summary_schema()
        document["columns"][21]["allowed"] = ["visits"]
        self._run_validator_with_schema(
            document, "policy_mass_kind allowed values must be"
        )

    def _load_search_summary_row(self) -> dict:
        fixture = ROOT / "fixtures" / "search-summary" / "search-summary-v1-smoke.jsonl"
        with fixture.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    # Return a row that carries qfen (skip the optional-qfen row).
                    row = json.loads(line)
                    if "qfen" in row:
                        return row
        raise AssertionError("no search-summary fixture row with qfen")

    def _run_validator_with_row(self, row: dict, expected_error: str) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bad = Path(temp_dir) / "search-summary-bad.jsonl"
            bad.write_text(json.dumps(row) + "\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--manifest",
                    "contracts.json",
                    "--fixture-glob",
                    str(bad),
                    "--expected-release",
                    "1.3.0",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(expected_error, result.stderr)

    def test_search_summary_row_rejects_bad_side_to_move(self) -> None:
        row = self._load_search_summary_row()
        row["side_to_move"] = 2
        self._run_validator_with_row(row, "side_to_move must be 0 or 1")

    def test_search_summary_row_rejects_bad_engine_kind(self) -> None:
        row = self._load_search_summary_row()
        row["engine_kind"] = "astar"
        self._run_validator_with_row(row, "engine_kind must be one of")

    def test_search_summary_row_rejects_short_policy_visits(self) -> None:
        row = self._load_search_summary_row()
        row["policy_visits"] = row["policy_visits"][:63]
        self._run_validator_with_row(
            row, "policy_visits must be a list of 64 integers"
        )

    def test_search_summary_row_rejects_out_of_range_q_value(self) -> None:
        row = self._load_search_summary_row()
        row["root_q_values"][0] = 1.5
        self._run_validator_with_row(row, "root_q_values entry must be in [-1, 1]")

    def test_search_summary_row_rejects_nonzero_tablebase_hits(self) -> None:
        row = self._load_search_summary_row()
        row["tablebase_hits"] = 1
        self._run_validator_with_row(row, "tablebase_hits must be 0")

    def test_search_summary_row_allows_missing_qfen(self) -> None:
        # qfen is optional: a row without it must validate cleanly.
        row = self._load_search_summary_row()
        row.pop("qfen", None)
        with tempfile.TemporaryDirectory() as temp_dir:
            ok = Path(temp_dir) / "search-summary-ok.jsonl"
            ok.write_text(json.dumps(row) + "\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--manifest",
                    "contracts.json",
                    "--fixture-glob",
                    str(ok),
                    "--expected-release",
                    "1.3.0",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_repository_contracts_validate_parquet_metadata_manifest(self) -> None:
        manifest_path = (
            ROOT
            / "fixtures"
            / "parquet"
            / "arrow-parquet-selfplay-v1-metadata.json"
        )
        self.assertTrue(
            manifest_path.exists(),
            "expected dependency-free Parquet metadata manifest fixture",
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["physical_schema"], "arrow-parquet-selfplay.v1")
        self.assertEqual(manifest["logical_schema"], "selfplay.v1")
        self.assertEqual(manifest["logical_contract"], "selfplay.v1")
        self.assertEqual(manifest["contracts_release"], "1.3.0")
        self.assertEqual(manifest["contract_version"], "1.3.0")

        result = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                "--manifest",
                "contracts.json",
                "--schema-glob",
                str(manifest_path),
                "--expected-release",
                "1.3.0",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_parquet_metadata_manifest_requires_physical_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata_path = Path(temp_dir) / "metadata.json"
            metadata_path.write_text(
                json.dumps(
                    {
                        "schema": "arrow-parquet-selfplay.v1.metadata",
                        "physical_schema": "selfplay.v1",
                        "logical_schema": "selfplay.v1",
                        "logical_contract": "selfplay.v1",
                        "contracts_release": "1.2.0",
                        "contract_version": "1.2.0",
                        "parquet_key_value_metadata": {
                            "physical_schema": "selfplay.v1",
                            "logical_schema": "selfplay.v1",
                            "logical_contract": "selfplay.v1",
                            "contracts_release": "1.2.0",
                            "contract_version": "1.2.0",
                        },
                        "columns": [
                            column["name"]
                            for column in self._load_arrow_parquet_schema()["columns"]
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--manifest",
                    "contracts.json",
                    "--schema-glob",
                    str(metadata_path),
                    "--expected-release",
                    "1.3.0",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("physical_schema must be arrow-parquet-selfplay.v1", result.stderr)

    def _load_symmetry_fixture(self) -> dict:
        fixture_path = ROOT / "fixtures" / "symmetry" / "symmetry-v1.json"
        return json.loads(fixture_path.read_text(encoding="utf-8"))

    def _load_invalid_state_fixture(self) -> dict:
        fixture_path = ROOT / "fixtures" / "invalid-states" / "invalid-state-v1.json"
        return json.loads(fixture_path.read_text(encoding="utf-8"))

    def test_symmetry_fixture_validates(self) -> None:
        document = self._load_symmetry_fixture()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "symmetry-v1.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--manifest",
                    "contracts.json",
                    "--schema-glob",
                    str(path),
                    "--expected-release",
                    "1.3.0",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_symmetry_fixture_rejects_transform_index_mismatch(self) -> None:
        document = self._load_symmetry_fixture()
        document["board_cases"][0]["transforms"][1]["transform_index"] = 999 % 24
        self._run_validator_with_schema(
            document, "does not match d4_index"
        )

    def test_symmetry_fixture_rejects_wrong_expected_action_index(self) -> None:
        document = self._load_symmetry_fixture()
        document["action_remap_cases"][0]["expected_action_index"] = (
            document["action_remap_cases"][0]["expected_action_index"] + 1
        ) % 64
        self._run_validator_with_schema(
            document, "does not match recomputed"
        )

    def test_symmetry_fixture_rejects_bad_canonical_key(self) -> None:
        document = self._load_symmetry_fixture()
        document["board_cases"][0]["canonical_key"] = "not-hex"
        self._run_validator_with_schema(
            document, "canonical_key must be 36 lowercase hex chars"
        )

    def test_invalid_state_fixture_validates(self) -> None:
        document = self._load_invalid_state_fixture()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "invalid-state-v1.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--manifest",
                    "contracts.json",
                    "--schema-glob",
                    str(path),
                    "--expected-release",
                    "1.3.0",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_state_fixture_rejects_unknown_rejection_reason(self) -> None:
        document = self._load_invalid_state_fixture()
        document["cases"][0]["expected_rejection"] = "SOMETHING_ELSE"
        self._run_validator_with_schema(
            document, "expected_rejection must be one of"
        )

    def test_invalid_state_fixture_rejects_both_qfen_and_bitboards(self) -> None:
        document = self._load_invalid_state_fixture()
        document["cases"][0]["bitboards"] = [0] * 8
        self._run_validator_with_schema(
            document, "must set exactly one of qfen or bitboards"
        )


class EngineContractRowTests(unittest.TestCase):
    """engine-request.v1 / engine-response.v1 rows are checked, not just read."""

    def _first_row(self, directory: str) -> dict:
        path = next((ROOT / "fixtures" / directory).glob("*.jsonl"))
        return json.loads(path.read_text(encoding="utf-8").splitlines()[0])

    def _run(self, row: dict) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "engine-row.jsonl"
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            return subprocess.run(
                [
                    sys.executable, str(VALIDATOR), "--manifest", "contracts.json",
                    "--fixture-glob", str(path), "--expected-release", "1.3.0",
                ],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )

    def _assert_rejected(self, row: dict, message: str) -> None:
        result = self._run(row)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(message, result.stderr)

    def test_request_fixture_row_is_accepted(self) -> None:
        self.assertEqual(self._run(self._first_row("engine-request")).returncode, 0)

    def test_response_fixture_row_is_accepted(self) -> None:
        self.assertEqual(self._run(self._first_row("engine-response")).returncode, 0)

    def test_request_rejects_unknown_field(self) -> None:
        row = self._first_row("engine-request")
        row["surprise"] = 1
        self._assert_rejected(row, "unknown fields")

    def test_request_rejects_prefixed_schema_value(self) -> None:
        row = self._first_row("engine-request")
        row["schema"] = "quantik.engine-request.v1"
        self._assert_rejected(row, "schema must be engine-request.v1")

    def test_request_rejects_out_of_range_action(self) -> None:
        row = self._first_row("engine-request")
        row["legal_action_indices"] = [64]
        self._assert_rejected(row, "0..=63")

    def test_request_rejects_unknown_config_field(self) -> None:
        row = self._first_row("engine-request")
        row["config"] = {"depth": 3}
        self._assert_rejected(row, "unknown config fields")

    def test_response_rejects_unknown_field(self) -> None:
        row = self._first_row("engine-response")
        row["win_probability"] = 0.5
        self._assert_rejected(row, "unknown fields")

    def test_response_rejects_wrong_schema_value(self) -> None:
        row = self._first_row("engine-response")
        row["schema"] = "quantik.engine-response.v1"
        self._assert_rejected(row, "schema must be engine-response.v1")

    def test_response_rejects_short_policy(self) -> None:
        row = self._first_row("engine-response")
        row["policy"] = [0.0] * 63
        self._assert_rejected(row, "policy must be a list of 64 numbers")

    def test_response_rejects_missing_required_field(self) -> None:
        row = self._first_row("engine-response")
        del row["elapsed_ms"]
        self._assert_rejected(row, "missing required fields")


class EngineResponseV2Tests(unittest.TestCase):
    """engine-response.v2: valid fixtures accepted, invalid cases rejected, v1 frozen."""

    FIXTURE_DIR = ROOT / "fixtures" / "engine-response"

    def _run(self, path: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable, str(VALIDATOR), "--manifest", "contracts.json",
                "--fixture-glob", str(path), "--expected-release", "1.3.0",
            ],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )

    def _run_row(self, row: dict) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "row.jsonl"
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            return self._run(path)

    def _valid_rows(self) -> list[dict]:
        path = self.FIXTURE_DIR / "engine-response-v2-synthetic.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_valid_fixture_file_is_accepted(self) -> None:
        result = self._run(self.FIXTURE_DIR / "engine-response-v2-synthetic.jsonl")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_valid_fixtures_cover_units_certainties_and_pv(self) -> None:
        rows = self._valid_rows()
        units = {c["unit"] for r in rows for c in r.get("candidates", [])}
        self.assertEqual(units, {"visits", "logit", "prior", "value"})
        self.assertEqual({r["certainty"] for r in rows}, {"estimate", "proof"})
        self.assertTrue(any("pv" in r for r in rows))
        self.assertTrue(all(r["schema"] == "engine-response.v2" for r in rows))

    def test_every_invalid_case_is_rejected_with_its_message(self) -> None:
        path = self.FIXTURE_DIR / "engine-response-v2-invalid.json"
        cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
        self.assertGreaterEqual(len(cases), 20)
        for case in cases:
            with self.subTest(case=case["case_id"]):
                result = self._run_row(case["row"])
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(case["expected_error"], result.stderr)

    def test_invalid_cases_include_the_three_required_defects(self) -> None:
        path = self.FIXTURE_DIR / "engine-response-v2-invalid.json"
        ids = {c["case_id"] for c in json.loads(path.read_text(encoding="utf-8"))["cases"]}
        self.assertTrue(
            {"missing-certainty", "certainty-third-value", "candidate-bad-unit"} <= ids
        )

    def test_v1_schema_rejects_certainty(self) -> None:
        path = self.FIXTURE_DIR / "engine-response-v1-captured.jsonl"
        row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        row["certainty"] = "estimate"
        result = self._run_row(row)
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown fields", result.stderr)

    def test_v2_schema_file_requires_certainty(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "engine-response-v2.json").read_text(encoding="utf-8")
        )
        self.assertIn("certainty", schema["required"])
        self.assertEqual(schema["properties"]["certainty"]["enum"], ["estimate", "proof"])
        self.assertEqual(
            schema["properties"]["candidates"]["items"]["properties"]["unit"]["enum"],
            ["visits", "logit", "prior", "value"],
        )


class OpeningProbeTests(unittest.TestCase):
    """opening-probe.v1: registered, valid fixtures accepted, invalid cases rejected."""

    FIXTURE_DIR = ROOT / "fixtures" / "opening-probe"

    def _run(self, path: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable, str(VALIDATOR), "--manifest", "contracts.json",
                "--fixture-glob", str(path), "--expected-release", "1.3.0",
            ],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )

    def _run_row(self, row: dict) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "row.jsonl"
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            return self._run(path)

    def _valid_rows(self) -> list[dict]:
        path = self.FIXTURE_DIR / "opening-probe-v1-synthetic.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def _invalid_cases(self) -> list[dict]:
        path = self.FIXTURE_DIR / "opening-probe-v1-invalid.json"
        return json.loads(path.read_text(encoding="utf-8"))["cases"]

    def test_registered_with_schema_docs_and_narrow_fixture_glob(self) -> None:
        manifest = json.loads((ROOT / "contracts.json").read_text(encoding="utf-8"))
        entry = manifest["contracts"]["opening_probe"]
        self.assertEqual(entry["id"], "opening-probe.v1")
        self.assertEqual(entry["schema"], "schemas/opening-probe-v1.json")
        self.assertEqual(entry["docs"], "docs/opening-probe-v1.md")
        self.assertEqual(entry["fixture_glob"], "fixtures/opening-probe/opening-probe-v1-*.jsonl")
        self.assertTrue((ROOT / entry["schema"]).exists())

    def test_schema_is_closed_and_requires_the_mandatory_header_keys(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "opening-probe-v1.json").read_text(encoding="utf-8")
        )
        self.assertIs(schema["additionalProperties"], False)
        self.assertEqual(
            set(schema["required"]),
            {
                "schema", "format_major", "key_format", "record_size", "entry_count",
                "ply_min", "ply_max", "per_ply", "source_book", "generator",
                "generator_version", "contract_version", "body_sha256",
            },
        )
        self.assertEqual(schema["properties"]["record_size"], {"const": 28})
        self.assertEqual(schema["properties"]["format_major"], {"const": 1})

    def test_valid_fixture_file_is_accepted(self) -> None:
        result = self._run(self.FIXTURE_DIR / "opening-probe-v1-synthetic.jsonl")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("(5 rows)", result.stdout)

    def test_valid_fixtures_cover_the_required_cases(self) -> None:
        cases = {c["case_id"]: c["expected"] for r in self._valid_rows() for c in r["probe_cases"]}
        self.assertEqual(cases["identity"]["transform_index"], 0)
        self.assertEqual(cases["transformed-95"]["actions"], [42])
        self.assertEqual(cases["tie-77"]["minimiser_transform_indices"], [77, 91, 125, 139])
        self.assertEqual(cases["tie-77"]["actions"], [9])
        self.assertEqual(cases["bounded-unknown"]["game_value"], 0)
        self.assertEqual(cases["miss-key-absent"]["reason"], "key_absent")
        self.assertEqual(cases["miss-ply-outside-coverage"]["reason"], "ply_outside_coverage")
        self.assertEqual(cases["stale-book-id"]["error"], "stale")
        # the case the legality tripwire cannot catch: t* instead of its inverse is legal
        legal_wrong = cases["wrong-direction-52-is-legal"]
        self.assertTrue(legal_wrong["wrong_direction_legal"])
        self.assertEqual(legal_wrong["wrong_direction_actions"], [52])
        self.assertNotEqual(legal_wrong["wrong_direction_actions"], legal_wrong["actions"])
        # section 3.5: the wrong direction lands on an occupied square there
        self.assertFalse(cases["transformed-95"]["wrong_direction_legal"])

    def test_every_invalid_case_is_rejected_with_its_message(self) -> None:
        cases = self._invalid_cases()
        self.assertGreaterEqual(len(cases), 20)
        for case in cases:
            with self.subTest(case=case["case_id"]):
                result = self._run_row(case["row"])
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(case["expected_error"], result.stderr)

    def test_invalid_cases_include_the_section_5_taxonomy(self) -> None:
        errors = {c["expected_error"] for c in self._invalid_cases()}
        self.assertEqual(
            errors,
            {
                "corrupt", "truncated", "incompatible version", "checksum mismatch",
                "unsorted or duplicate keys", "illegal mapped-back action",
            },
        )

    def test_headers_match_the_schema_when_jsonschema_is_available(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed; the stdlib validator mirrors the schema")
        schema = json.loads(
            (ROOT / "schemas" / "opening-probe-v1.json").read_text(encoding="utf-8")
        )
        validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
        for row in self._valid_rows():
            with self.subTest(row=row["case_id"]):
                validator.validate(row["header"])
        for case in self._invalid_cases():
            with self.subTest(case=case["case_id"]):
                rejected = bool(list(validator.iter_errors(case["row"]["header"])))
                self.assertEqual(rejected, case["header_schema_rejects"])

    def test_reference_legality_matches_known_legal_sets(self) -> None:
        # Every "illegal mapped-back action" verdict rests on _legal_actions, so pin it to
        # legal sets produced by engines (engine-request fixtures, search-summary masks).
        sys.path.insert(0, str(ROOT / "scripts"))
        import validate_contracts as vc

        checked = 0
        request_path = ROOT / "fixtures" / "engine-request" / "engine-request-v1-captured.jsonl"
        for line in request_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            board = vc._bitboard_from_qfen(row["qfen"])
            self.assertEqual(vc._side_to_move(board), row["side_to_move"], row["qfen"])
            self.assertEqual(
                sorted(vc._legal_actions(board, row["side_to_move"])),
                row["legal_action_indices"], row["qfen"],
            )
            checked += 1
        summary_path = ROOT / "fixtures" / "search-summary" / "search-summary-v1-smoke.jsonl"
        for line in summary_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            board = row["bitboards"]
            mask = sum(1 << a for a in vc._legal_actions(board, vc._side_to_move(board)))
            self.assertEqual(mask, row["legal_action_mask"], row["position_key"])
            checked += 1
        self.assertGreaterEqual(checked, 8)

    def test_reference_legality_matches_quantik_core_when_installed(self) -> None:
        try:
            from quantik_core import State, generate_legal_moves_list
        except ImportError:
            self.skipTest("quantik_core not installed")
        sys.path.insert(0, str(ROOT / "scripts"))
        import validate_contracts as vc

        qfens = ["AbC./..../..../....", "A.../..../B.../...a", "..../.B../c.../A...",
                 "B.../..../..c./....", "AB../c.../..../..d.", "..../..../..../D..."]
        symmetry = json.loads(
            (ROOT / "fixtures" / "symmetry" / "symmetry-v1.json").read_text(encoding="utf-8")
        )
        qfens += [case["qfen"] for case in symmetry["board_cases"]]
        for qfen in qfens:
            board = vc._bitboard_from_qfen(qfen)
            player = vc._side_to_move(board)
            with self.subTest(qfen=qfen):
                engine = {m.shape * 16 + m.position
                          for m in generate_legal_moves_list(State.from_qfen(qfen).bb, player)}
                self.assertEqual(vc._legal_actions(board, player), engine)

    def test_wrong_direction_answer_is_rejected(self) -> None:
        # An implementation that applies t* instead of its inverse returns 52 (still a
        # legal move) for the wrong-direction fixture; the fixture must fail it.
        row = next(r for r in self._valid_rows() if r["case_id"] == "hit-wrong-direction-still-legal")
        row["probe_cases"][0]["expected"]["actions"] = [52]
        result = self._run_row(row)
        self.assertEqual(result.returncode, 1)
        self.assertIn("reference probe returned", result.stderr)

    def test_engine_and_other_fixture_globs_do_not_pick_up_probe_files(self) -> None:
        manifest = json.loads((ROOT / "contracts.json").read_text(encoding="utf-8"))
        self.assertNotIn(
            "fixtures/opening-probe", manifest["contracts"]["engine_response_v2"]["fixture_glob"]
        )
        self.assertEqual(list(self.FIXTURE_DIR.glob("*.jsonl")), [
            self.FIXTURE_DIR / "opening-probe-v1-synthetic.jsonl"
        ])


if __name__ == "__main__":
    unittest.main()
