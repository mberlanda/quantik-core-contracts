from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_opening_book_summary.py"


def write_summary(path: Path, *, depth_four_edges: int = 317682) -> None:
    total_edges = 3 + 51 + 1422 + 21522 + depth_four_edges
    path.write_text(
        json.dumps(
            {
                "schema": "opening-book-summary.v1",
                "contract_version": "1.1.0",
                "depth": 4,
                "total_positions": 11739,
                "terminal_positions": 12,
                "total_edges": total_edges,
                "per_depth": [
                    {
                        "depth": 0,
                        "positions": 1,
                        "terminal": 0,
                        "edges": 3,
                    },
                    {
                        "depth": 1,
                        "positions": 3,
                        "terminal": 0,
                        "edges": 51,
                    },
                    {
                        "depth": 2,
                        "positions": 51,
                        "terminal": 0,
                        "edges": 1422,
                    },
                    {
                        "depth": 3,
                        "positions": 726,
                        "terminal": 0,
                        "edges": 21522,
                    },
                    {
                        "depth": 4,
                        "positions": 10958,
                        "terminal": 12,
                        "edges": depth_four_edges,
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


class OpeningBookSummaryValidatorTests(unittest.TestCase):
    def test_matching_rust_and_python_opening_book_summaries_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            rust_summary = tmp_path / "rust.json"
            python_summary = tmp_path / "python.json"
            write_summary(rust_summary)
            write_summary(python_summary)

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--rust-summary",
                    str(rust_summary),
                    "--python-summary",
                    str(python_summary),
                    "--expected-depth",
                    "4",
                    "--expected-release",
                    "1.1.0",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_mismatched_rust_and_python_opening_book_summaries_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            rust_summary = tmp_path / "rust.json"
            python_summary = tmp_path / "python.json"
            write_summary(rust_summary)
            write_summary(python_summary, depth_four_edges=317683)

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--rust-summary",
                    str(rust_summary),
                    "--python-summary",
                    str(python_summary),
                    "--expected-depth",
                    "4",
                    "--expected-release",
                    "1.1.0",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("summaries differ", result.stderr)


if __name__ == "__main__":
    unittest.main()
