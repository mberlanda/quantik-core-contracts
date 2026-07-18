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
                "1.2.0",
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
                    "1.2.0",
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
                    "1.2.0",
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
                    "1.2.0",
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
        self.assertEqual(manifest["contracts_release"], "1.2.0")
        self.assertEqual(manifest["contract_version"], "1.2.0")

        result = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                "--manifest",
                "contracts.json",
                "--schema-glob",
                str(manifest_path),
                "--expected-release",
                "1.2.0",
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
                    "1.2.0",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("physical_schema must be arrow-parquet-selfplay.v1", result.stderr)


if __name__ == "__main__":
    unittest.main()
