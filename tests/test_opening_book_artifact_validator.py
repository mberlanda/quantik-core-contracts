from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_opening_book_artifact.py"


def create_book(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE positions (
            canonical_key BLOB PRIMARY KEY,
            depth INTEGER NOT NULL,
            is_terminal INTEGER NOT NULL,
            winner INTEGER,
            symmetry_count INTEGER NOT NULL,
            searched_depth INTEGER NOT NULL,
            score INTEGER,
            status TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE edges (
            parent_key BLOB NOT NULL,
            child_key BLOB NOT NULL,
            move TEXT NOT NULL,
            PRIMARY KEY(parent_key, child_key)
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO positions
        (canonical_key, depth, is_terminal, winner, symmetry_count,
         searched_depth, score, status)
        VALUES (?, ?, ?, NULL, 1, 1, NULL, 'ok')
        """,
        [(b"root", 0, 0), (b"a", 1, 0), (b"b", 1, 0), (b"c", 2, 1)],
    )
    conn.executemany(
        "INSERT INTO edges (parent_key, child_key, move) VALUES (?, ?, ?)",
        [(b"root", b"a", "A@0"), (b"root", b"b", "B@1"), (b"a", b"c", "a@2")],
    )
    conn.commit()
    conn.close()


def write_summary(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "opening-book-summary.v1",
                "contract_version": "1.1.0",
                "depth": 2,
                "total_positions": 4,
                "terminal_positions": 1,
                "total_edges": 3,
                "per_depth": [
                    {"depth": 0, "positions": 1, "terminal": 0, "edges": 2},
                    {"depth": 1, "positions": 2, "terminal": 0, "edges": 1},
                    {"depth": 2, "positions": 1, "terminal": 1, "edges": 0},
                ],
            }
        ),
        encoding="utf-8",
    )


class OpeningBookArtifactValidatorTests(unittest.TestCase):
    def test_valid_book_and_matching_summaries_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            db_path = tmp_path / "book.sqlite"
            rust_summary = tmp_path / "rust-summary.json"
            python_summary = tmp_path / "python-summary.json"
            create_book(db_path)
            write_summary(rust_summary)
            write_summary(python_summary)

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--db",
                    str(db_path),
                    "--rust-summary",
                    str(rust_summary),
                    "--python-summary",
                    str(python_summary),
                    "--expected-depth",
                    "2",
                    "--expected-release",
                    "1.1.0",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_edges_pointing_to_missing_child(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            db_path = tmp_path / "book.sqlite"
            rust_summary = tmp_path / "rust-summary.json"
            python_summary = tmp_path / "python-summary.json"
            create_book(db_path)
            write_summary(rust_summary)
            write_summary(python_summary)

            conn = sqlite3.connect(db_path)
            conn.execute(
                "INSERT INTO edges (parent_key, child_key, move) VALUES (?, ?, ?)",
                (b"root", b"missing", "C@2"),
            )
            conn.commit()
            conn.close()

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--db",
                    str(db_path),
                    "--rust-summary",
                    str(rust_summary),
                    "--python-summary",
                    str(python_summary),
                    "--expected-depth",
                    "2",
                    "--expected-release",
                    "1.1.0",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("missing child", result.stderr)


if __name__ == "__main__":
    unittest.main()
