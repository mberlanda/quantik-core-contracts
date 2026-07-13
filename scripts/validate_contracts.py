#!/usr/bin/env python3
"""Validate Quantik contract schemas and JSONL fixtures.

This script intentionally uses only the Python standard library so it can run
inside downstream repositories without dependency setup.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path
from typing import Any

QFEN_RE = re.compile(r"^[A-Da-d.]{4}/[A-Da-d.]{4}/[A-Da-d.]{4}/[A-Da-d.]{4}$")


def fail(message: str) -> None:
    raise ValueError(message)


def expect_int(record: dict[str, Any], key: str) -> int:
    value = record.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        fail(f"{key} must be an integer")
    return value


def validate_qfen(qfen: Any) -> None:
    if not isinstance(qfen, str) or not QFEN_RE.match(qfen):
        fail("qfen must match qfen.v1")


def validate_policy(policy: Any) -> None:
    if not isinstance(policy, list) or not policy:
        fail("policy must be a non-empty list")
    seen: set[tuple[int, int]] = set()
    for index, item in enumerate(policy):
        if not isinstance(item, dict):
            fail(f"policy[{index}] must be an object")
        shape = expect_int(item, "shape")
        position = expect_int(item, "position")
        visits = expect_int(item, "visits")
        if shape < 0 or shape > 3:
            fail(f"policy[{index}].shape must be in 0..3")
        if position < 0 or position > 15:
            fail(f"policy[{index}].position must be in 0..15")
        if visits <= 0:
            fail(f"policy[{index}].visits must be positive")
        key = (shape, position)
        if key in seen:
            fail(f"policy[{index}] duplicates shape={shape}, position={position}")
        seen.add(key)


def validate_selfplay_row(record: Any) -> None:
    if not isinstance(record, dict):
        fail("row must be a JSON object")
    if record.get("schema") != "selfplay.v1":
        fail("schema must be selfplay.v1")

    game_id = expect_int(record, "game_id")
    ply = expect_int(record, "ply")
    side_to_move = expect_int(record, "side_to_move")
    if game_id < 0:
        fail("game_id must be non-negative")
    if ply < 0:
        fail("ply must be non-negative")
    if side_to_move not in (0, 1):
        fail("side_to_move must be 0 or 1")
    validate_qfen(record.get("qfen"))
    validate_policy(record.get("policy"))

    value = record.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        fail("value must be numeric")
    if float(value) not in (-1.0, 1.0):
        fail("value must be exactly -1.0 or 1.0")


def validate_json_file(path: Path) -> None:
    with path.open(encoding="utf-8") as handle:
        json.load(handle)


def validate_jsonl_file(path: Path) -> int:
    rows = 0
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
                validate_selfplay_row(record)
            except Exception as exc:
                fail(f"{path}:{line_number}: {exc}")
            rows += 1
    if rows == 0:
        fail(f"{path}: fixture has no rows")
    return rows


def expand_globs(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matches = [Path(match) for match in glob.glob(pattern, recursive=True)]
        if not matches:
            print(f"warning: no matches for {pattern}", file=sys.stderr)
        paths.extend(matches)
    return sorted(set(paths))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--schema-glob",
        action="append",
        default=[],
        help="Glob for JSON schema/metadata files.",
    )
    parser.add_argument(
        "--fixture-glob",
        action="append",
        default=[],
        help="Glob for selfplay.v1 JSONL fixtures.",
    )
    args = parser.parse_args()

    try:
        schema_paths = expand_globs(args.schema_glob)
        fixture_paths = expand_globs(args.fixture_glob)

        for path in schema_paths:
            validate_json_file(path)
            print(f"validated schema json: {path}")

        total_rows = 0
        for path in fixture_paths:
            rows = validate_jsonl_file(path)
            total_rows += rows
            print(f"validated fixture: {path} ({rows} rows)")

        print(
            f"contract validation complete: {len(schema_paths)} json files, {total_rows} fixture rows"
        )
        return 0
    except Exception as exc:
        print(f"contract validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

