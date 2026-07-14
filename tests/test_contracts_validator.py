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

    def test_arrow_parquet_selfplay_requires_logical_contract(self) -> None:
        schema_path = ROOT / "schemas" / "arrow-parquet-selfplay-v1.json"
        document = json.loads(schema_path.read_text(encoding="utf-8"))
        document.pop("logical_contract")

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
            self.assertIn("logical_contract must be selfplay.v1", result.stderr)


if __name__ == "__main__":
    unittest.main()
