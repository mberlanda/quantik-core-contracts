#!/usr/bin/env python3
"""Validate a generated opening-book SQLite artifact and stack summaries."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any

from validate_opening_book_summary import normalize_summary


REQUIRED_POSITION_COLUMNS = {
    "canonical_key",
    "depth",
    "is_terminal",
}
REQUIRED_EDGE_COLUMNS = {
    "parent_key",
    "child_key",
}


def fail(message: str) -> None:
    raise ValueError(message)


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if not rows:
        fail(f"missing required table: {table}")
    return {str(row[1]) for row in rows}


def query_int(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    if row is None:
        fail(f"query returned no rows: {sql}")
    return int(row[0])


def validate_sqlite_book(db_path: Path, expected_depth: int) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    try:
        position_columns = table_columns(conn, "positions")
        edge_columns = table_columns(conn, "edges")
        missing_positions = sorted(REQUIRED_POSITION_COLUMNS - position_columns)
        missing_edges = sorted(REQUIRED_EDGE_COLUMNS - edge_columns)
        if missing_positions:
            fail(f"positions table missing columns: {', '.join(missing_positions)}")
        if missing_edges:
            fail(f"edges table missing columns: {', '.join(missing_edges)}")

        max_depth = query_int(conn, "SELECT COALESCE(MAX(depth), 0) FROM positions")
        if max_depth != expected_depth:
            fail(f"book max depth {max_depth} does not match {expected_depth}")

        negative_depth = query_int(conn, "SELECT COUNT(*) FROM positions WHERE depth < 0")
        if negative_depth:
            fail("positions contains negative depth rows")

        bad_terminal = query_int(
            conn,
            "SELECT COUNT(*) FROM positions WHERE is_terminal NOT IN (0, 1)",
        )
        if bad_terminal:
            fail("positions contains invalid is_terminal values")

        missing_parent = query_int(
            conn,
            """
            SELECT COUNT(*)
            FROM edges e
            LEFT JOIN positions p ON p.canonical_key = e.parent_key
            WHERE p.canonical_key IS NULL
            """,
        )
        if missing_parent:
            fail(f"edges contains {missing_parent} missing parent references")

        missing_child = query_int(
            conn,
            """
            SELECT COUNT(*)
            FROM edges e
            LEFT JOIN positions p ON p.canonical_key = e.child_key
            WHERE p.canonical_key IS NULL
            """,
        )
        if missing_child:
            fail(f"edges contains {missing_child} missing child references")

        per_depth: list[dict[str, int]] = []
        for depth in range(expected_depth + 1):
            positions = query_int(
                conn,
                "SELECT COUNT(*) FROM positions WHERE depth = ?",
                (depth,),
            )
            terminal = query_int(
                conn,
                "SELECT COUNT(*) FROM positions WHERE depth = ? AND is_terminal = 1",
                (depth,),
            )
            edges = query_int(
                conn,
                """
                SELECT COUNT(*)
                FROM edges e
                JOIN positions p ON p.canonical_key = e.parent_key
                WHERE p.depth = ?
                """,
                (depth,),
            )
            if terminal > positions:
                fail(f"depth {depth}: terminal count exceeds positions")
            per_depth.append(
                {
                    "depth": depth,
                    "positions": positions,
                    "terminal": terminal,
                    "edges": edges,
                }
            )

        return {
            "schema": "opening-book-summary.v1",
            "depth": expected_depth,
            "total_positions": sum(row["positions"] for row in per_depth),
            "terminal_positions": sum(row["terminal"] for row in per_depth),
            "total_edges": sum(row["edges"] for row in per_depth),
            "per_depth": per_depth,
        }
    finally:
        conn.close()


def compare_book_to_summary(book: dict[str, Any], summary: dict[str, Any]) -> None:
    comparable = {
        key: value
        for key, value in summary.items()
        if key != "contract_version"
    }
    if book != comparable:
        fail("SQLite artifact metrics do not match opening-book-summary.v1")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--rust-summary", required=True)
    parser.add_argument("--python-summary", required=True)
    parser.add_argument("--expected-depth", required=True, type=int)
    parser.add_argument("--expected-release", default=None)
    args = parser.parse_args()

    try:
        book_summary = validate_sqlite_book(Path(args.db), args.expected_depth)
        rust_summary = normalize_summary(
            Path(args.rust_summary), args.expected_depth, args.expected_release
        )
        python_summary = normalize_summary(
            Path(args.python_summary), args.expected_depth, args.expected_release
        )
        if rust_summary != python_summary:
            fail("summaries differ between Rust and Python")
        compare_book_to_summary(book_summary, rust_summary)
        print(
            "opening book artifact validation passed: "
            f"depth={book_summary['depth']} "
            f"positions={book_summary['total_positions']} "
            f"edges={book_summary['total_edges']}"
        )
        return 0
    except Exception as exc:
        print(f"opening book artifact validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
