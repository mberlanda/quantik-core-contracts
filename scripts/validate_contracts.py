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
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$")

ARROW_PARQUET_SELFPLAY_COLUMNS = [
    ("logical_schema", "utf8", True),
    ("contract_version", "utf8", True),
    ("game_id", "uint64", True),
    ("ply", "uint16", True),
    ("side_to_move", "uint8", True),
    ("bitboards", "fixed_size_list<uint16,8>", True),
    ("policy_visits", "fixed_size_list<uint32,64>", True),
    ("value", "int8", True),
    ("qfen", "utf8", False),
]

ARROW_PARQUET_SELFPLAY_METADATA = {
    "physical_schema": "arrow-parquet-selfplay.v1",
    "logical_schema": "selfplay.v1",
    "logical_contract": "selfplay.v1",
}

ARROW_PARQUET_SELFPLAY_RELEASE_METADATA_KEYS = [
    "contracts_release",
    "contract_version",
]
ARROW_PARQUET_SELFPLAY_SCHEMA_RELEASE_VALUE = "contracts.json.release_version"

OBSERVATION_PARQUET_COLUMNS = [
    ("schema", "utf8", True),
    ("contract_version", "utf8", True),
    ("run_id", "utf8", True),
    ("row_id", "uint64", True),
    ("position_key", "utf8", True),
    ("ply", "uint16", True),
    ("side_to_move", "uint8", True),
    ("bitboards", "fixed_size_list<uint16,8>", True),
    ("qfen", "utf8", False),
    ("legal_action_mask", "uint64", True),
    ("engine_kind", "utf8", True),
    ("engine_version", "utf8", True),
    ("elapsed_ms", "uint32", True),
    ("policy_visits", "fixed_size_list<uint32,64>", True),
    ("value", "float64", True),
    ("value_source", "utf8", True),
    ("source_confidence", "float64", True),
]

GAME_RESULT_PARQUET_COLUMNS = [
    ("schema", "utf8", True),
    ("contract_version", "utf8", True),
    ("game_id", "utf8", True),
    ("started_at", "utf8", True),
    ("p0_engine_kind", "utf8", True),
    ("p0_engine_version", "utf8", True),
    ("p1_engine_kind", "utf8", True),
    ("p1_engine_version", "utf8", True),
    ("initial_position_key", "utf8", True),
    ("winner", "uint8", True),
    ("plies", "uint16", True),
    ("terminal_reason", "utf8", True),
    ("move_action_indices", "list<uint8>", True),
    ("run_id", "utf8", False),
]

SEARCH_SUMMARY_PARQUET_COLUMNS = [
    ("schema", "utf8", True),
    ("contract_version", "utf8", True),
    ("run_id", "utf8", True),
    ("row_id", "uint64", True),
    ("position_key", "utf8", True),
    ("ply", "uint16", True),
    ("side_to_move", "uint8", True),
    ("bitboards", "fixed_size_list<uint16,8>", True),
    ("qfen", "utf8", False),
    ("legal_action_mask", "uint64", True),
    ("engine_kind", "utf8", True),
    ("engine_version", "utf8", True),
    ("engine_checkpoint", "utf8", False),
    ("config_label", "utf8", True),
    ("search_depth", "uint32", False),
    ("rollouts", "uint32", False),
    ("beam_width", "uint32", False),
    ("node_budget", "uint64", False),
    ("time_budget_ms", "uint32", False),
    ("seed", "uint64", False),
    ("root_value", "float64", True),
    ("policy_mass_kind", "utf8", True),
    ("policy_visits", "fixed_size_list<uint32,64>", True),
    ("root_q_values", "fixed_size_list<float64,64>", True),
    ("principal_variation", "list<uint8>", True),
    ("expanded_nodes", "uint64", True),
    ("generated_nodes", "uint64", True),
    ("transposition_hits", "uint64", True),
    ("canonical_dedup_hits", "uint64", True),
    ("terminal_hits", "uint64", True),
    ("tablebase_hits", "uint64", True),
    ("elapsed_ms", "uint32", False),
    ("depth_reached", "uint32", True),
]

IMPLEMENTED_PARQUET_CONTRACTS = {
    "observation.v1": OBSERVATION_PARQUET_COLUMNS,
    "game-result.v1": GAME_RESULT_PARQUET_COLUMNS,
    "search-summary.v1": SEARCH_SUMMARY_PARQUET_COLUMNS,
}

API_PORTABILITY_FIXTURE_SCHEMA = "api-portability-fixtures.v1"

PARQUET_RELEASE_METADATA_KEYS = ["contracts_release", "contract_version"]
PARQUET_SCHEMA_RELEASE_VALUE = "contracts.json.release_version"


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


def validate_selfplay_row(
    record: Any, expected_schema: str, expected_contract_version: str | None
) -> None:
    if not isinstance(record, dict):
        fail("row must be a JSON object")
    if record.get("schema") != expected_schema:
        fail(f"schema must be {expected_schema}")
    contract_version = record.get("contract_version")
    if contract_version is not None:
        if not isinstance(contract_version, str):
            fail("contract_version must be a string")
        if expected_contract_version is not None and contract_version != expected_contract_version:
            fail(
                "contract_version must match contracts release "
                f"{expected_contract_version}"
            )

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


SEARCH_SUMMARY_ENGINE_KINDS = ("mcts", "beam", "minimax")
SEARCH_SUMMARY_POLICY_MASS_KINDS = ("visits", "multiplicity", "none")


def _expect_uint(record: dict[str, Any], key: str) -> int:
    value = expect_int(record, key)
    if value < 0:
        fail(f"{key} must be non-negative")
    return value


def _expect_optional_uint(record: dict[str, Any], key: str) -> None:
    value = record.get(key)
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        fail(f"{key} must be a non-negative integer or null")


def _expect_unit_value(value: Any, label: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        fail(f"{label} must be numeric")
    if not -1.0 <= float(value) <= 1.0:
        fail(f"{label} must be in [-1, 1]")


def validate_search_summary_row(
    record: Any, expected_contract_version: str | None
) -> None:
    if not isinstance(record, dict):
        fail("row must be a JSON object")
    if record.get("schema") != "search-summary.v1":
        fail("schema must be search-summary.v1")

    contract_version = record.get("contract_version")
    if not isinstance(contract_version, str):
        fail("contract_version must be a string")
    if (
        expected_contract_version is not None
        and contract_version != expected_contract_version
    ):
        fail(f"contract_version must be {expected_contract_version}")

    for key in ("run_id", "position_key", "engine_version", "config_label"):
        if not isinstance(record.get(key), str) or not record.get(key):
            fail(f"{key} must be a non-empty string")

    _expect_uint(record, "row_id")
    _expect_uint(record, "ply")
    if _expect_uint(record, "side_to_move") not in (0, 1):
        fail("side_to_move must be 0 or 1")
    _expect_uint(record, "legal_action_mask")
    _expect_uint(record, "depth_reached")

    bitboards = record.get("bitboards")
    if not isinstance(bitboards, list) or len(bitboards) != 8:
        fail("bitboards must be a list of 8 integers")
    for plane in bitboards:
        if not isinstance(plane, int) or isinstance(plane, bool) or not 0 <= plane <= 0xFFFF:
            fail("bitboards entries must be uint16")

    # qfen is optional; validate only when present.
    if "qfen" in record and record.get("qfen") is not None:
        validate_qfen(record.get("qfen"))

    if record.get("engine_kind") not in SEARCH_SUMMARY_ENGINE_KINDS:
        fail(f"engine_kind must be one of {list(SEARCH_SUMMARY_ENGINE_KINDS)}")
    if record.get("policy_mass_kind") not in SEARCH_SUMMARY_POLICY_MASS_KINDS:
        fail(
            "policy_mass_kind must be one of "
            f"{list(SEARCH_SUMMARY_POLICY_MASS_KINDS)}"
        )

    engine_checkpoint = record.get("engine_checkpoint")
    if engine_checkpoint is not None and not isinstance(engine_checkpoint, str):
        fail("engine_checkpoint must be a string or null")

    for key in (
        "search_depth",
        "rollouts",
        "beam_width",
        "node_budget",
        "time_budget_ms",
        "seed",
        "elapsed_ms",
    ):
        _expect_optional_uint(record, key)

    _expect_unit_value(record.get("root_value"), "root_value")

    policy_visits = record.get("policy_visits")
    if not isinstance(policy_visits, list) or len(policy_visits) != 64:
        fail("policy_visits must be a list of 64 integers")
    for visit in policy_visits:
        if not isinstance(visit, int) or isinstance(visit, bool) or visit < 0:
            fail("policy_visits entries must be non-negative integers")

    root_q_values = record.get("root_q_values")
    if not isinstance(root_q_values, list) or len(root_q_values) != 64:
        fail("root_q_values must be a list of 64 nullable floats")
    for q in root_q_values:
        if q is not None:
            _expect_unit_value(q, "root_q_values entry")

    pv = record.get("principal_variation")
    if not isinstance(pv, list):
        fail("principal_variation must be a list of action indices")
    for action in pv:
        if not isinstance(action, int) or isinstance(action, bool) or not 0 <= action < 64:
            fail("principal_variation entries must be action indices in [0, 64)")

    for key in (
        "expanded_nodes",
        "generated_nodes",
        "transposition_hits",
        "canonical_dedup_hits",
        "terminal_hits",
    ):
        _expect_uint(record, key)
    if _expect_uint(record, "tablebase_hits") != 0:
        fail("tablebase_hits must be 0")


def validate_arrow_parquet_selfplay_metadata(
    document: dict[str, Any], path: Path
) -> None:
    if document.get("storage") != "parquet":
        fail(f"{path}: arrow-parquet-selfplay.v1 storage must be parquet")
    if document.get("logical_contract") != "selfplay.v1":
        fail(
            f"{path}: arrow-parquet-selfplay.v1 logical_contract must be "
            "selfplay.v1"
        )
    parquet_metadata = document.get("parquet_metadata")
    if not isinstance(parquet_metadata, dict):
        fail(f"{path}: arrow-parquet-selfplay.v1 parquet_metadata must be an object")
    for key, expected_value in ARROW_PARQUET_SELFPLAY_METADATA.items():
        if parquet_metadata.get(key) != expected_value:
            fail(f"{path}: parquet_metadata.{key} must be {expected_value}")
    for key in ARROW_PARQUET_SELFPLAY_RELEASE_METADATA_KEYS:
        if parquet_metadata.get(key) != ARROW_PARQUET_SELFPLAY_SCHEMA_RELEASE_VALUE:
            fail(
                f"{path}: parquet_metadata.{key} must be "
                f"{ARROW_PARQUET_SELFPLAY_SCHEMA_RELEASE_VALUE}"
            )

    columns = document.get("columns")
    if not isinstance(columns, list):
        fail(f"{path}: arrow-parquet-selfplay.v1 columns must be a list")
    if len(columns) != len(ARROW_PARQUET_SELFPLAY_COLUMNS):
        fail(
            f"{path}: arrow-parquet-selfplay.v1 must define "
            f"{len(ARROW_PARQUET_SELFPLAY_COLUMNS)} columns"
        )

    for index, (column, expected) in enumerate(
        zip(columns, ARROW_PARQUET_SELFPLAY_COLUMNS, strict=True)
    ):
        expected_name, expected_type, expected_required = expected
        if not isinstance(column, dict):
            fail(f"{path}: column {index} must be an object")
        if column.get("name") != expected_name:
            fail(f"{path}: column {index} name must be {expected_name}")
        if column.get("type") != expected_type:
            fail(f"{path}: column {expected_name} type must be {expected_type}")
        if column.get("required") is not expected_required:
            fail(
                f"{path}: column {expected_name} required must be "
                f"{expected_required}"
            )

    logical_schema = columns[0]
    if logical_schema.get("allowed") != ["selfplay.v1"]:
        fail(f"{path}: logical_schema allowed values must be ['selfplay.v1']")
    side_to_move = columns[4]
    if side_to_move.get("allowed") != [0, 1]:
        fail(f"{path}: side_to_move allowed values must be [0, 1]")
    value = columns[7]
    if value.get("allowed") != [-1, 1]:
        fail(f"{path}: value allowed values must be [-1, 1]")


def validate_arrow_parquet_selfplay_metadata_manifest(
    document: dict[str, Any], path: Path, expected_contract_version: str | None
) -> None:
    for key, expected_value in ARROW_PARQUET_SELFPLAY_METADATA.items():
        if document.get(key) != expected_value:
            fail(f"{path}: {key} must be {expected_value}")

    if expected_contract_version is not None:
        for key in ARROW_PARQUET_SELFPLAY_RELEASE_METADATA_KEYS:
            if document.get(key) != expected_contract_version:
                fail(f"{path}: {key} must be {expected_contract_version}")

    parquet_metadata = document.get("parquet_key_value_metadata")
    if not isinstance(parquet_metadata, dict):
        fail(f"{path}: parquet_key_value_metadata must be an object")
    for key, expected_value in ARROW_PARQUET_SELFPLAY_METADATA.items():
        if parquet_metadata.get(key) != expected_value:
            fail(f"{path}: parquet_key_value_metadata.{key} must be {expected_value}")
    if expected_contract_version is not None:
        for key in ARROW_PARQUET_SELFPLAY_RELEASE_METADATA_KEYS:
            if parquet_metadata.get(key) != expected_contract_version:
                fail(
                    f"{path}: parquet_key_value_metadata.{key} must be "
                    f"{expected_contract_version}"
                )

    columns = document.get("columns")
    expected_columns = [name for name, _type, _required in ARROW_PARQUET_SELFPLAY_COLUMNS]
    if columns != expected_columns:
        fail(f"{path}: columns must be {expected_columns}")


def validate_implemented_parquet_schema(
    document: dict[str, Any], path: Path, contract_id: str
) -> None:
    if document.get("storage") != "parquet":
        fail(f"{path}: {contract_id} storage must be parquet")

    parquet_metadata = document.get("parquet_metadata")
    if not isinstance(parquet_metadata, dict):
        fail(f"{path}: {contract_id} parquet_metadata must be an object")
    for key in ("physical_schema", "logical_schema", "logical_contract"):
        if parquet_metadata.get(key) != contract_id:
            fail(f"{path}: parquet_metadata.{key} must be {contract_id}")
    for key in PARQUET_RELEASE_METADATA_KEYS:
        if parquet_metadata.get(key) != PARQUET_SCHEMA_RELEASE_VALUE:
            fail(
                f"{path}: parquet_metadata.{key} must be "
                f"{PARQUET_SCHEMA_RELEASE_VALUE}"
            )

    expected_columns = IMPLEMENTED_PARQUET_CONTRACTS[contract_id]
    columns = document.get("columns")
    if not isinstance(columns, list):
        fail(f"{path}: {contract_id} columns must be a list")
    if len(columns) != len(expected_columns):
        fail(
            f"{path}: {contract_id} must define {len(expected_columns)} columns"
        )

    for index, (column, expected) in enumerate(
        zip(columns, expected_columns, strict=True)
    ):
        expected_name, expected_type, expected_required = expected
        if not isinstance(column, dict):
            fail(f"{path}: column {index} must be an object")
        if column.get("name") != expected_name:
            fail(f"{path}: column {index} name must be {expected_name}")
        if column.get("type") != expected_type:
            fail(f"{path}: column {expected_name} type must be {expected_type}")
        if column.get("required") is not expected_required:
            fail(
                f"{path}: column {expected_name} required must be "
                f"{expected_required}"
            )

    if contract_id == "observation.v1":
        side_to_move = columns[6]
        if side_to_move.get("allowed") not in (None, [0, 1]):
            fail(f"{path}: side_to_move allowed values must be [0, 1] when present")
    if contract_id == "game-result.v1":
        winner = columns[9]
        if winner.get("allowed") != [0, 1]:
            fail(f"{path}: winner allowed values must be [0, 1]")
    if contract_id == "search-summary.v1":
        if columns[0].get("allowed") != ["search-summary.v1"]:
            fail(f"{path}: schema allowed values must be ['search-summary.v1']")
        if columns[6].get("allowed") != [0, 1]:
            fail(f"{path}: side_to_move allowed values must be [0, 1]")
        if columns[10].get("allowed") != ["mcts", "beam", "minimax"]:
            fail(
                f"{path}: engine_kind allowed values must be "
                "['mcts', 'beam', 'minimax']"
            )
        if columns[21].get("allowed") != ["visits", "multiplicity", "none"]:
            fail(
                f"{path}: policy_mass_kind allowed values must be "
                "['visits', 'multiplicity', 'none']"
            )


def validate_implemented_parquet_metadata_manifest(
    document: dict[str, Any],
    path: Path,
    contract_id: str,
    expected_contract_version: str | None,
) -> None:
    for key in ("physical_schema", "logical_schema", "logical_contract"):
        if document.get(key) != contract_id:
            fail(f"{path}: {key} must be {contract_id}")

    if expected_contract_version is not None:
        for key in PARQUET_RELEASE_METADATA_KEYS:
            if document.get(key) != expected_contract_version:
                fail(f"{path}: {key} must be {expected_contract_version}")

    parquet_metadata = document.get("parquet_key_value_metadata")
    if not isinstance(parquet_metadata, dict):
        fail(f"{path}: parquet_key_value_metadata must be an object")
    for key in ("physical_schema", "logical_schema", "logical_contract"):
        if parquet_metadata.get(key) != contract_id:
            fail(f"{path}: parquet_key_value_metadata.{key} must be {contract_id}")
    if expected_contract_version is not None:
        for key in PARQUET_RELEASE_METADATA_KEYS:
            if parquet_metadata.get(key) != expected_contract_version:
                fail(
                    f"{path}: parquet_key_value_metadata.{key} must be "
                    f"{expected_contract_version}"
                )

    columns = document.get("columns")
    expected_columns = [
        name for name, _type, _required in IMPLEMENTED_PARQUET_CONTRACTS[contract_id]
    ]
    if columns != expected_columns:
        fail(f"{path}: columns must be {expected_columns}")


def validate_api_portability_fixture(
    document: dict[str, Any], path: Path, expected_contract_version: str | None
) -> None:
    contract_version = document.get("contract_version")
    if not isinstance(contract_version, str):
        fail(f"{path}: contract_version must be a string")
    if expected_contract_version is not None and contract_version != expected_contract_version:
        fail(f"{path}: contract_version must be {expected_contract_version}")

    cases = document.get("game_state_cases")
    if not isinstance(cases, list) or not cases:
        fail(f"{path}: game_state_cases must be a non-empty list")
    seen: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            fail(f"{path}: game_state_cases[{index}] must be an object")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            fail(f"{path}: game_state_cases[{index}].case_id must be a non-empty string")
        if case_id in seen:
            fail(f"{path}: duplicate api portability case_id {case_id}")
        seen.add(case_id)
        validate_qfen(case.get("qfen"))
        move = case.get("move")
        if move is None:
            continue
        if not isinstance(move, dict):
            fail(f"{path}: game_state_cases[{case_id}].move must be an object")
        shape = expect_int(move, "shape")
        position = expect_int(move, "position")
        if shape < 0 or shape > 3:
            fail(f"{path}: game_state_cases[{case_id}].move.shape must be in 0..3")
        if position < 0 or position > 15:
            fail(f"{path}: game_state_cases[{case_id}].move.position must be in 0..15")


def validate_json_file(path: Path, expected_contract_version: str | None) -> None:
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    if (
        isinstance(document, dict)
        and document.get("schema") == "arrow-parquet-selfplay.v1"
    ):
        validate_arrow_parquet_selfplay_metadata(document, path)
    if (
        isinstance(document, dict)
        and document.get("schema") == "arrow-parquet-selfplay.v1.metadata"
    ):
        validate_arrow_parquet_selfplay_metadata_manifest(
            document, path, expected_contract_version
        )
    if isinstance(document, dict) and document.get("schema") in IMPLEMENTED_PARQUET_CONTRACTS:
        validate_implemented_parquet_schema(document, path, document["schema"])
    if isinstance(document, dict) and document.get("schema") == API_PORTABILITY_FIXTURE_SCHEMA:
        validate_api_portability_fixture(document, path, expected_contract_version)
    if isinstance(document, dict):
        schema = document.get("schema")
        if isinstance(schema, str) and schema.endswith(".metadata"):
            contract_id = schema.removesuffix(".metadata")
            if contract_id in IMPLEMENTED_PARQUET_CONTRACTS:
                validate_implemented_parquet_metadata_manifest(
                    document, path, contract_id, expected_contract_version
                )


def validate_jsonl_file(
    path: Path, expected_schema: str, expected_contract_version: str | None
) -> int:
    rows = 0
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
                row_schema = record.get("schema") if isinstance(record, dict) else None
                if row_schema == "search-summary.v1":
                    validate_search_summary_row(record, expected_contract_version)
                else:
                    validate_selfplay_row(
                        record,
                        expected_schema=expected_schema,
                        expected_contract_version=expected_contract_version,
                    )
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


def validate_manifest(
    manifest_path: Path, version_path: Path, expected_release: str | None
) -> tuple[str, str | None]:
    if not manifest_path.exists():
        return "selfplay.v1", expected_release

    with manifest_path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        fail(f"{manifest_path}: manifest must be a JSON object")

    release_version = manifest.get("release_version")
    if not isinstance(release_version, str) or not SEMVER_RE.match(release_version):
        fail(f"{manifest_path}: release_version must be SemVer")
    if expected_release is not None and release_version != expected_release:
        fail(
            f"{manifest_path}: release_version {release_version} does not match "
            f"expected release {expected_release}"
        )

    if version_path.exists():
        version = version_path.read_text(encoding="utf-8").strip()
        if version != release_version:
            fail(
                f"{version_path}: version {version} does not match "
                f"{manifest_path} release_version {release_version}"
            )

    contracts = manifest.get("contracts")
    if not isinstance(contracts, dict) or not contracts:
        fail(f"{manifest_path}: contracts must be a non-empty object")

    base_dir = manifest_path.parent
    selfplay_schema = "selfplay.v1"
    for name, contract in contracts.items():
        if not isinstance(contract, dict):
            fail(f"{manifest_path}: contract {name} must be an object")
        contract_id = contract.get("id")
        major = contract.get("major")
        docs = contract.get("docs")
        schema = contract.get("schema")
        if not isinstance(contract_id, str):
            fail(f"{manifest_path}: contract {name}.id must be a string")
        if not isinstance(major, int) or major < 1:
            fail(f"{manifest_path}: contract {name}.major must be positive")
        if not contract_id.endswith(f".v{major}"):
            fail(
                f"{manifest_path}: contract {name}.id must end with .v{major}"
            )
        if not isinstance(docs, str) or not (base_dir / docs).exists():
            fail(f"{manifest_path}: contract {name}.docs must reference a file")
        if schema is not None:
            if not isinstance(schema, str):
                fail(f"{manifest_path}: contract {name}.schema must be string or null")
            schema_path = base_dir / schema
            if not schema_path.exists():
                fail(f"{manifest_path}: contract {name}.schema file is missing")
            schema_text = schema_path.read_text(encoding="utf-8")
            if contract_id not in schema_text:
                fail(
                    f"{manifest_path}: contract {name}.schema does not mention "
                    f"{contract_id}"
                )
        if name == "selfplay":
            selfplay_schema = contract_id

    print(f"validated manifest: {manifest_path} ({release_version})")
    return selfplay_schema, release_version


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
    parser.add_argument(
        "--manifest",
        default="contracts.json",
        help="Contracts manifest path. Skipped when the file is absent.",
    )
    parser.add_argument(
        "--version-file",
        default="VERSION",
        help="Version file compared to the manifest when present.",
    )
    parser.add_argument(
        "--expected-release",
        default=None,
        help="Expected contracts SemVer release.",
    )
    args = parser.parse_args()

    try:
        expected_schema, expected_contract_version = validate_manifest(
            Path(args.manifest), Path(args.version_file), args.expected_release
        )
        schema_paths = expand_globs(args.schema_glob)
        fixture_paths = expand_globs(args.fixture_glob)

        for path in schema_paths:
            validate_json_file(path, expected_contract_version)
            print(f"validated schema json: {path}")

        total_rows = 0
        for path in fixture_paths:
            rows = validate_jsonl_file(
                path,
                expected_schema=expected_schema,
                expected_contract_version=expected_contract_version,
            )
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
