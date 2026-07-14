#!/usr/bin/env python3
"""Validate and compare opening-book-summary.v1 artifacts.

The summary is intentionally small: it is a contract smoke artifact that lets
Rust and Python agree on graph shape without sharing implementation details.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = {
    "schema",
    "contract_version",
    "depth",
    "total_positions",
    "terminal_positions",
    "total_edges",
    "per_depth",
}


def fail(message: str) -> None:
    raise ValueError(message)


def load_summary(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        fail(f"{path}: summary must be a JSON object")
    missing = sorted(REQUIRED_TOP_LEVEL - set(value))
    if missing:
        fail(f"{path}: missing required fields: {', '.join(missing)}")
    return value


def expect_int(summary: dict[str, Any], key: str, path: Path) -> int:
    value = summary.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        fail(f"{path}: {key} must be an integer")
    if value < 0:
        fail(f"{path}: {key} must be non-negative")
    return value


def normalize_summary(
    path: Path, expected_depth: int, expected_release: str | None
) -> dict[str, Any]:
    summary = load_summary(path)
    if summary.get("schema") != "opening-book-summary.v1":
        fail(f"{path}: schema must be opening-book-summary.v1")
    contract_version = summary.get("contract_version")
    if not isinstance(contract_version, str):
        fail(f"{path}: contract_version must be a string")
    if expected_release is not None and contract_version != expected_release:
        fail(
            f"{path}: contract_version {contract_version} does not match "
            f"{expected_release}"
        )

    depth = expect_int(summary, "depth", path)
    if depth != expected_depth:
        fail(f"{path}: depth {depth} does not match {expected_depth}")
    total_positions = expect_int(summary, "total_positions", path)
    terminal_positions = expect_int(summary, "terminal_positions", path)
    total_edges = expect_int(summary, "total_edges", path)

    per_depth = summary.get("per_depth")
    if not isinstance(per_depth, list) or len(per_depth) != depth + 1:
        fail(f"{path}: per_depth must contain one row for every depth 0..{depth}")

    normalized_rows: list[dict[str, int]] = []
    position_sum = 0
    terminal_sum = 0
    edge_sum = 0
    for expected_row_depth, row in enumerate(per_depth):
        if not isinstance(row, dict):
            fail(f"{path}: per_depth[{expected_row_depth}] must be an object")
        row_path = Path(f"{path}:per_depth[{expected_row_depth}]")
        row_depth = expect_int(row, "depth", row_path)
        positions = expect_int(row, "positions", row_path)
        terminal = expect_int(row, "terminal", row_path)
        edges = expect_int(row, "edges", row_path)
        if row_depth != expected_row_depth:
            fail(
                f"{path}: per_depth[{expected_row_depth}].depth must be "
                f"{expected_row_depth}"
            )
        if terminal > positions:
            fail(f"{path}: per_depth[{expected_row_depth}].terminal exceeds positions")
        normalized_rows.append(
            {
                "depth": row_depth,
                "positions": positions,
                "terminal": terminal,
                "edges": edges,
            }
        )
        position_sum += positions
        terminal_sum += terminal
        edge_sum += edges

    if total_positions != position_sum:
        fail(f"{path}: total_positions does not match per_depth positions")
    if terminal_positions != terminal_sum:
        fail(f"{path}: terminal_positions does not match per_depth terminal")
    if total_edges != edge_sum:
        fail(f"{path}: total_edges does not match per_depth edges")

    return {
        "schema": "opening-book-summary.v1",
        "contract_version": contract_version,
        "depth": depth,
        "total_positions": total_positions,
        "terminal_positions": terminal_positions,
        "total_edges": total_edges,
        "per_depth": normalized_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rust-summary", required=True)
    parser.add_argument("--python-summary", required=True)
    parser.add_argument("--expected-depth", type=int, required=True)
    parser.add_argument("--expected-release", default=None)
    args = parser.parse_args()

    try:
        rust_summary = normalize_summary(
            Path(args.rust_summary), args.expected_depth, args.expected_release
        )
        python_summary = normalize_summary(
            Path(args.python_summary), args.expected_depth, args.expected_release
        )
        if rust_summary != python_summary:
            fail("summaries differ between Rust and Python")
        print(
            "opening-book-summary.v1 consistency passed: "
            f"depth={rust_summary['depth']} "
            f"positions={rust_summary['total_positions']} "
            f"edges={rust_summary['total_edges']}"
        )
        return 0
    except Exception as exc:
        print(f"opening book summary validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
