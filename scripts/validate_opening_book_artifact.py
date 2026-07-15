#!/usr/bin/env python3
"""Validate a generated opening-book SQLite artifact and stack summaries."""

from __future__ import annotations

import argparse
import re
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
CANONICAL_KEY_BYTES = 18
MOVE_RE = re.compile(r"^P[01]S([0-3])P([0-9]|1[0-5])$")


def fail(message: str) -> None:
    raise ValueError(message)


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if not rows:
        fail(f"missing required table: {table}")
    return {str(row[1]) for row in rows}


def optional_table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


def query_int(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    if row is None:
        fail(f"query returned no rows: {sql}")
    return int(row[0])


def validate_metadata_if_present(
    conn: sqlite3.Connection, expected_release: str | None
) -> None:
    columns = optional_table_columns(conn, "book_metadata")
    if not columns:
        return
    missing = {"key", "value"} - columns
    if missing:
        fail(f"book_metadata table missing columns: {', '.join(sorted(missing))}")
    metadata = {
        str(key): str(value)
        for key, value in conn.execute("SELECT key, value FROM book_metadata")
    }
    schema = metadata.get("schema")
    if schema is not None and schema != "opening-book.v1":
        fail(f"book_metadata.schema must be opening-book.v1, got {schema}")
    contract_version = metadata.get("contract_version")
    if (
        contract_version is not None
        and expected_release is not None
        and contract_version != expected_release
    ):
        fail(
            f"book_metadata.contract_version must be {expected_release}, "
            f"got {contract_version}"
        )


def edge_table_and_columns(conn: sqlite3.Connection) -> tuple[str, set[str]]:
    for table in ("edges", "position_edges"):
        columns = optional_table_columns(conn, table)
        if columns:
            return table, columns
    fail("missing required table: edges")


def edge_reference_mode(edge_columns: set[str], position_columns: set[str]) -> str:
    if {"parent_key", "child_key"} <= edge_columns:
        return "canonical_key"
    if {"parent_node_id", "child_node_id"} <= edge_columns:
        if "node_id" not in position_columns:
            fail("positions table missing node_id for node_id edge references")
        return "node_id"
    fail(
        "edges table missing reference columns: expected parent_key/child_key "
        "or parent_node_id/child_node_id"
    )


def edge_ref_sql(mode: str) -> tuple[str, str, str, str]:
    if mode == "canonical_key":
        return (
            "e.parent_key",
            "e.child_key",
            "p.canonical_key = e.parent_key",
            "p.canonical_key = e.child_key",
        )
    return (
        "e.parent_node_id",
        "e.child_node_id",
        "p.node_id = e.parent_node_id",
        "p.node_id = e.child_node_id",
    )


def validate_positions(
    conn: sqlite3.Connection, position_columns: set[str], expected_depth: int
) -> None:
    position_count = query_int(conn, "SELECT COUNT(*) FROM positions")
    if position_count == 0:
        fail("positions table is empty")

    bad_key = query_int(
        conn,
        """
        SELECT COUNT(*)
        FROM positions
        WHERE typeof(canonical_key) != 'blob' OR length(canonical_key) != ?
        """,
        (CANONICAL_KEY_BYTES,),
    )
    if bad_key:
        fail(
            "positions contains canonical_key values that are not "
            f"{CANONICAL_KEY_BYTES}-byte blobs"
        )

    root_count = query_int(conn, "SELECT COUNT(*) FROM positions WHERE depth = 0")
    if root_count != 1:
        fail(f"positions must contain exactly one depth-0 root, found {root_count}")

    missing_depths = [
        depth
        for depth in range(expected_depth + 1)
        if query_int(conn, "SELECT COUNT(*) FROM positions WHERE depth = ?", (depth,))
        == 0
    ]
    if missing_depths:
        fail(f"positions missing depth rows: {', '.join(map(str, missing_depths))}")

    if "node_id" in position_columns:
        bad_node_id = query_int(
            conn,
            """
            SELECT COUNT(*)
            FROM positions
            WHERE node_id IS NULL OR typeof(node_id) != 'integer' OR node_id < 0
            """,
        )
        if bad_node_id:
            fail("positions contains invalid node_id values")
        duplicate_node_id = query_int(
            conn,
            """
            SELECT COUNT(*)
            FROM (
                SELECT node_id, COUNT(*) AS n
                FROM positions
                GROUP BY node_id
                HAVING n > 1
            )
            """,
        )
        if duplicate_node_id:
            fail("positions contains duplicate node_id values")

    if "winner" in position_columns:
        bad_winner = query_int(
            conn,
            "SELECT COUNT(*) FROM positions WHERE winner IS NOT NULL AND winner NOT IN (0, 1)",
        )
        if bad_winner:
            fail("positions contains invalid winner values")

    if "searched_depth" in position_columns:
        bad_searched_depth = query_int(
            conn,
            "SELECT COUNT(*) FROM positions WHERE searched_depth < 0",
        )
        if bad_searched_depth:
            fail("positions contains negative searched_depth values")

    if "status" in position_columns:
        bad_status = query_int(
            conn,
            """
            SELECT COUNT(*)
            FROM positions
            WHERE typeof(status) = 'integer' AND status NOT IN (0, 1, 2)
            """,
        )
        if bad_status:
            fail("positions contains invalid integer status values")

    if "symmetry_count" in position_columns:
        bad_symmetry_count = query_int(
            conn,
            """
            SELECT COUNT(*)
            FROM positions
            WHERE symmetry_count < 0 OR symmetry_count > 192
            """,
        )
        if bad_symmetry_count:
            fail("positions contains invalid symmetry_count values")


def validate_edge_identity(
    conn: sqlite3.Connection, edge_table: str, edge_columns: set[str], mode: str
) -> None:
    parent_expr, child_expr, _, _ = edge_ref_sql(mode)
    if "action_index" in edge_columns:
        bad_action = query_int(
            conn,
            f"""
            SELECT COUNT(*)
            FROM {edge_table} e
            WHERE typeof(e.action_index) != 'integer'
               OR e.action_index < 0
               OR e.action_index > 63
            """,
        )
        if bad_action:
            fail("edges contains invalid action_index values")
        duplicate_action = query_int(
            conn,
            f"""
            SELECT COUNT(*)
            FROM (
                SELECT {parent_expr}, e.action_index, COUNT(*) AS n
                FROM {edge_table} e
                GROUP BY {parent_expr}, e.action_index
                HAVING n > 1
            )
            """,
        )
        if duplicate_action:
            fail("edges contains duplicate action_index identities per parent")
        duplicate_identity = query_int(
            conn,
            f"""
            SELECT COUNT(*)
            FROM (
                SELECT {parent_expr}, e.action_index, {child_expr}, COUNT(*) AS n
                FROM {edge_table} e
                GROUP BY {parent_expr}, e.action_index, {child_expr}
                HAVING n > 1
            )
            """,
        )
        if duplicate_identity:
            fail("edges contains duplicate parent/action/child identities")
        return

    if "move" not in edge_columns:
        fail("edges table missing action identity column: action_index or move")
    bad_move = query_int(
        conn,
        f"""
        SELECT COUNT(*)
        FROM {edge_table} e
        WHERE e.move IS NULL OR trim(e.move) = ''
        """,
    )
    if bad_move:
        fail("edges contains empty move action identities")
    invalid_moves = [
        str(row[0])
        for row in conn.execute(f"SELECT DISTINCT move FROM {edge_table}")
        if not MOVE_RE.match(str(row[0]))
    ]
    if invalid_moves:
        fail(f"edges contains invalid move action identities: {invalid_moves[0]}")
    duplicate_move = query_int(
        conn,
        f"""
        SELECT COUNT(*)
        FROM (
            SELECT {parent_expr}, e.move, COUNT(*) AS n
            FROM {edge_table} e
            GROUP BY {parent_expr}, e.move
            HAVING n > 1
        )
        """,
    )
    if duplicate_move:
        fail("edges contains duplicate move identities per parent")


def validate_edges(
    conn: sqlite3.Connection,
    edge_table: str,
    edge_columns: set[str],
    mode: str,
    expected_depth: int,
) -> None:
    parent_join = edge_ref_sql(mode)[2]
    child_join = edge_ref_sql(mode)[3]
    missing_parent = query_int(
        conn,
        f"""
        SELECT COUNT(*)
        FROM {edge_table} e
        LEFT JOIN positions p ON {parent_join}
        WHERE p.canonical_key IS NULL
        """,
    )
    if missing_parent:
        fail(f"edges contains {missing_parent} missing parent references")

    missing_child = query_int(
        conn,
        f"""
        SELECT COUNT(*)
        FROM {edge_table} e
        LEFT JOIN positions p ON {child_join}
        WHERE p.canonical_key IS NULL
        """,
    )
    if missing_child:
        fail(f"edges contains {missing_child} missing child references")

    depth_mismatch = query_int(
        conn,
        f"""
        SELECT COUNT(*)
        FROM {edge_table} e
        JOIN positions parent ON {parent_join.replace('p.', 'parent.')}
        JOIN positions child ON {child_join.replace('p.', 'child.')}
        WHERE child.depth != parent.depth + 1
        """,
    )
    if depth_mismatch:
        fail("edges contains parent/child depth mismatches")

    outgoing_terminal = query_int(
        conn,
        f"""
        SELECT COUNT(*)
        FROM {edge_table} e
        JOIN positions parent ON {parent_join.replace('p.', 'parent.')}
        WHERE parent.is_terminal != 0
        """,
    )
    if outgoing_terminal:
        fail("terminal positions must not have outgoing edges")

    outgoing_horizon = query_int(
        conn,
        f"""
        SELECT COUNT(*)
        FROM {edge_table} e
        JOIN positions parent ON {parent_join.replace('p.', 'parent.')}
        WHERE parent.depth >= ?
        """,
        (expected_depth,),
    )
    if outgoing_horizon:
        fail("expected-depth horizon positions must not have outgoing edges")

    validate_edge_identity(conn, edge_table, edge_columns, mode)


def validate_sqlite_book(
    db_path: Path, expected_depth: int, expected_release: str | None = None
) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    try:
        validate_metadata_if_present(conn, expected_release)
        position_columns = table_columns(conn, "positions")
        edge_table, edge_columns = edge_table_and_columns(conn)
        missing_positions = sorted(REQUIRED_POSITION_COLUMNS - position_columns)
        if missing_positions:
            fail(f"positions table missing columns: {', '.join(missing_positions)}")
        edge_mode = edge_reference_mode(edge_columns, position_columns)

        validate_positions(conn, position_columns, expected_depth)

        max_depth = query_int(conn, "SELECT COALESCE(MAX(depth), -1) FROM positions")
        if max_depth != expected_depth:
            fail(f"book max depth {max_depth} does not match {expected_depth}")

        negative_depth = query_int(conn, "SELECT COUNT(*) FROM positions WHERE depth < 0")
        if negative_depth:
            fail("positions contains negative depth rows")

        bad_terminal = query_int(
            conn,
            "SELECT COUNT(*) FROM positions WHERE is_terminal NOT IN (0, 1, 2, 3)",
        )
        if bad_terminal:
            fail("positions contains invalid is_terminal values")

        validate_edges(conn, edge_table, edge_columns, edge_mode, expected_depth)

        per_depth: list[dict[str, int]] = []
        for depth in range(expected_depth + 1):
            positions = query_int(
                conn,
                "SELECT COUNT(*) FROM positions WHERE depth = ?",
                (depth,),
            )
            terminal = query_int(
                conn,
                "SELECT COUNT(*) FROM positions WHERE depth = ? AND is_terminal != 0",
                (depth,),
            )
            edges = query_int(
                conn,
                f"""
                SELECT COUNT(*)
                FROM {edge_table} e
                JOIN positions p ON {edge_ref_sql(edge_mode)[2]}
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
        book_summary = validate_sqlite_book(
            Path(args.db), args.expected_depth, args.expected_release
        )
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
