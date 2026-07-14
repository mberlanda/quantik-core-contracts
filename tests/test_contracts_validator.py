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


if __name__ == "__main__":
    unittest.main()
