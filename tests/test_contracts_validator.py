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
                "1.1.0",
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
                    "1.1.0",
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
        self.assertEqual(manifest["contracts_release"], "1.1.0")
        self.assertEqual(manifest["contract_version"], "1.1.0")

        result = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                "--manifest",
                "contracts.json",
                "--schema-glob",
                str(manifest_path),
                "--expected-release",
                "1.1.0",
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
                        "contracts_release": "1.1.0",
                        "contract_version": "1.1.0",
                        "parquet_key_value_metadata": {
                            "physical_schema": "selfplay.v1",
                            "logical_schema": "selfplay.v1",
                            "logical_contract": "selfplay.v1",
                            "contracts_release": "1.1.0",
                            "contract_version": "1.1.0",
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
                    "1.1.0",
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
