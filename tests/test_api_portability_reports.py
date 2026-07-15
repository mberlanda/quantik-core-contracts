import json
import tempfile
import unittest
from pathlib import Path

from scripts.compare_api_portability_reports import compare_reports
from scripts.validate_contracts import validate_json_file


def report(language: str, cases: list[dict] | None = None) -> dict:
    return {
        "schema": "api-portability-report.v1",
        "contracts_release": "1.1.0",
        "implementation": {
            "language": language,
            "package": f"quantik-core-{language}",
            "version": "1.1.0",
        },
        "contract_ids": {
            "qfen": "qfen.v1",
            "bitboard": "bitboard.v1",
            "action_index": "action-index.v1",
        },
        "cases": cases
        or [
            {
                "case_id": "empty-board",
                "qfen": "..../..../..../....",
                "bitboards": [0, 0, 0, 0, 0, 0, 0, 0],
                "canonical_qfen": "..../..../..../....",
                "legal_action_mask": "0xffffffffffffffff",
                "legal_action_indices": list(range(64)),
            }
        ],
    }


class ApiPortabilityReportTests(unittest.TestCase):
    def test_api_portability_fixture_validates(self) -> None:
        validate_json_file(
            Path("fixtures/api-portability/game-state-v1.json"),
            expected_contract_version="1.1.0",
        )

    def test_api_portability_fixture_rejects_missing_cases(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "bad-fixture.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "api-portability-fixtures.v1",
                        "contract_version": "1.1.0",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "game_state_cases"):
                validate_json_file(path, expected_contract_version="1.1.0")

    def test_identical_reports_ignore_implementation_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            py = Path(root) / "python.json"
            rust = Path(root) / "rust.json"
            py.write_text(json.dumps(report("python")), encoding="utf-8")
            rust.write_text(json.dumps(report("rust")), encoding="utf-8")

            compare_reports([py, rust])

    def test_case_drift_fails_with_case_id(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            py = Path(root) / "python.json"
            rust = Path(root) / "rust.json"
            py.write_text(json.dumps(report("python")), encoding="utf-8")
            drifted = report("rust")
            drifted["cases"][0]["canonical_qfen"] = "A.../..../..../...."
            rust.write_text(json.dumps(drifted), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "empty-board"):
                compare_reports([py, rust])

    def test_release_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            py = Path(root) / "python.json"
            rust = Path(root) / "rust.json"
            py.write_text(json.dumps(report("python")), encoding="utf-8")
            drifted = report("rust")
            drifted["contracts_release"] = "1.0.0"
            rust.write_text(json.dumps(drifted), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "contracts_release"):
                compare_reports([py, rust])


if __name__ == "__main__":
    unittest.main()
