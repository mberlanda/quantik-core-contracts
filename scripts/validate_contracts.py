#!/usr/bin/env python3
"""Validate Quantik contract schemas and JSONL fixtures.

This script intentionally uses only the Python standard library so it can run
inside downstream repositories without dependency setup.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import itertools
import json
import re
import sys
from pathlib import Path
from typing import Any

QFEN_RE = re.compile(r"^[A-Da-d.]{4}/[A-Da-d.]{4}/[A-Da-d.]{4}/[A-Da-d.]{4}$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$")

# The symmetry-fixtures.v1 transform_index space is d4_index * 24 + shape_perm_index,
# where shape_perm_index enumerates the 24 permutations of (0, 1, 2, 3) in the same
# lexicographic order Python's itertools.permutations and both engine implementations'
# generators produce (see docs/symmetry-transposition.md). Reimplemented here, rather
# than imported, to keep this validator dependency-free and language-neutral.
SHAPE_PERM_ORDER: list[tuple[int, ...]] = list(itertools.permutations(range(4)))


def _build_d4_position_maps() -> list[list[int]]:
    maps: list[list[int]] = [[0] * 16 for _ in range(8)]
    for i in range(16):
        r, c = divmod(i, 4)
        maps[0][i] = r * 4 + c  # id
        maps[1][i] = c * 4 + (3 - r)  # rot90
        maps[2][i] = (3 - r) * 4 + (3 - c)  # rot180
        maps[3][i] = (3 - c) * 4 + r  # rot270
        maps[4][i] = r * 4 + (3 - c)  # reflV
        maps[5][i] = (3 - r) * 4 + c  # reflH
        maps[6][i] = c * 4 + r  # reflD
        maps[7][i] = (3 - c) * 4 + (3 - r)  # reflAD
    return maps


D4_POSITION_MAPS = _build_d4_position_maps()

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
SYMMETRY_FIXTURE_SCHEMA = "symmetry-fixtures.v1"
INVALID_STATE_FIXTURE_SCHEMA = "invalid-state-fixtures.v1"

INVALID_STATE_BOUNDARIES = ("parser", "constructor")
INVALID_STATE_REJECTIONS = (
    "MALFORMED_QFEN",
    "TURN_BALANCE_INVALID",
    "SHAPE_COUNT_EXCEEDED",
    "ILLEGAL_PLACEMENT",
    "PIECE_OVERLAP",
)

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


ENGINE_REQUEST_SCHEMA = "engine-request.v1"
ENGINE_RESPONSE_SCHEMA = "engine-response.v1"
ENGINE_REQUEST_FIELDS = {"schema", "qfen", "side_to_move", "legal_action_indices", "config"}
ENGINE_REQUEST_REQUIRED = ENGINE_REQUEST_FIELDS - {"config"}
ENGINE_CONFIG_FIELDS = {
    "max_depth", "time_limit_ms", "iterations", "beam_width", "rollouts", "seed",
}
ENGINE_RESPONSE_REQUIRED = {"schema", "action_index", "engine_kind", "engine_version", "elapsed_ms"}
ENGINE_RESPONSE_FIELDS = ENGINE_RESPONSE_REQUIRED | {"value", "policy"}
ENGINE_RESPONSE_V2_SCHEMA = "engine-response.v2"
ENGINE_RESPONSE_V2_REQUIRED = ENGINE_RESPONSE_REQUIRED | {"certainty"}
ENGINE_RESPONSE_V2_FIELDS = ENGINE_RESPONSE_V2_REQUIRED | {
    "value", "policy", "candidates", "pv", "engine_config",
}
ENGINE_CERTAINTY_VALUES = ("estimate", "proof")
ENGINE_CANDIDATE_UNITS = ("visits", "logit", "prior", "value")


def _expect_exact_keys(record: dict[str, Any], required: set[str], allowed: set[str]) -> None:
    missing = sorted(required - record.keys())
    if missing:
        fail(f"missing required fields: {missing}")
    unknown = sorted(record.keys() - allowed)
    if unknown:
        fail(f"unknown fields: {unknown}")


def _expect_action_index(value: Any, label: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 63:
        fail(f"{label} must be an integer in 0..=63")


def validate_engine_request_row(record: dict[str, Any]) -> None:
    """Mirror of schemas/engine-request-v1.json (stdlib only, no jsonschema)."""
    _expect_exact_keys(record, ENGINE_REQUEST_REQUIRED, ENGINE_REQUEST_FIELDS)
    if record["schema"] != ENGINE_REQUEST_SCHEMA:
        fail(f"schema must be {ENGINE_REQUEST_SCHEMA}")
    validate_qfen(record["qfen"])
    if record["side_to_move"] not in (0, 1) or isinstance(record["side_to_move"], bool):
        fail("side_to_move must be 0 or 1")
    indices = record["legal_action_indices"]
    if not isinstance(indices, list):
        fail("legal_action_indices must be a list")
    for index in indices:
        _expect_action_index(index, "legal_action_indices entry")
    config = record.get("config")
    if config is not None:
        if not isinstance(config, dict):
            fail("config must be an object")
        unknown = sorted(config.keys() - ENGINE_CONFIG_FIELDS)
        if unknown:
            fail(f"unknown config fields: {unknown}")
        for key, value in config.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                fail(f"config.{key} must be a non-negative integer")


def validate_engine_response_row(record: dict[str, Any]) -> None:
    """Mirror of schemas/engine-response-v1.json (stdlib only, no jsonschema)."""
    _expect_exact_keys(record, ENGINE_RESPONSE_REQUIRED, ENGINE_RESPONSE_FIELDS)
    if record["schema"] != ENGINE_RESPONSE_SCHEMA:
        fail(f"schema must be {ENGINE_RESPONSE_SCHEMA}")
    _expect_action_index(record["action_index"], "action_index")
    for key in ("engine_kind", "engine_version"):
        if not isinstance(record[key], str) or not record[key]:
            fail(f"{key} must be a non-empty string")
    elapsed = record["elapsed_ms"]
    if not isinstance(elapsed, int) or isinstance(elapsed, bool) or elapsed < 0:
        fail("elapsed_ms must be a non-negative integer")
    if "value" in record:
        value = record["value"]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            fail("value must be a number")
    if "policy" in record:
        policy = record["policy"]
        if (
            not isinstance(policy, list)
            or len(policy) != 64
            or any(not isinstance(p, (int, float)) or isinstance(p, bool) for p in policy)
        ):
            fail("policy must be a list of 64 numbers")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_engine_candidate(candidate: Any) -> int:
    if not isinstance(candidate, dict):
        fail("candidates entry must be an object")
    _expect_exact_keys(candidate, {"action_index", "score", "unit"}, {"action_index", "score", "unit"})
    _expect_action_index(candidate["action_index"], "candidates action_index")
    unit = candidate["unit"]
    if unit not in ENGINE_CANDIDATE_UNITS:
        fail(f"candidates unit must be one of {list(ENGINE_CANDIDATE_UNITS)}")
    score = candidate["score"]
    if not _is_number(score):
        fail("candidates score must be a number")
    if unit == "visits" and (not isinstance(score, int) or score < 0):
        fail("visits score must be a non-negative integer")
    if unit == "prior" and not 0 <= score <= 1:
        fail("prior score must be in [0, 1]")
    if unit == "value" and not -1 <= score <= 1:
        fail("value score must be in [-1, 1]")
    return candidate["action_index"]


def validate_engine_response_v2_row(record: dict[str, Any]) -> None:
    """Mirror of schemas/engine-response-v2.json (stdlib only, no jsonschema).

    Also checks two things JSON Schema cannot express: pv[0] equals
    action_index, and candidate action indices are unique.
    """
    _expect_exact_keys(record, ENGINE_RESPONSE_V2_REQUIRED, ENGINE_RESPONSE_V2_FIELDS)
    if record["schema"] != ENGINE_RESPONSE_V2_SCHEMA:
        fail(f"schema must be {ENGINE_RESPONSE_V2_SCHEMA}")
    _expect_action_index(record["action_index"], "action_index")
    for key in ("engine_kind", "engine_version"):
        if not isinstance(record[key], str) or not record[key]:
            fail(f"{key} must be a non-empty string")
    elapsed = record["elapsed_ms"]
    if not isinstance(elapsed, int) or isinstance(elapsed, bool) or elapsed < 0:
        fail("elapsed_ms must be a non-negative integer")
    certainty = record["certainty"]
    if not isinstance(certainty, str) or certainty not in ENGINE_CERTAINTY_VALUES:
        fail(f"certainty must be one of {list(ENGINE_CERTAINTY_VALUES)}")
    if "value" in record:
        value = record["value"]
        if not _is_number(value) or not -1 <= value <= 1:
            fail("value must be a number in [-1, 1]")
    if "policy" in record:
        policy = record["policy"]
        if not isinstance(policy, list) or len(policy) != 64 or not all(map(_is_number, policy)):
            fail("policy must be a list of 64 numbers")
    if "engine_config" in record:
        config = record["engine_config"]
        if not isinstance(config, str) or not config:
            fail("engine_config must be a non-empty string")
    if "candidates" in record:
        candidates = record["candidates"]
        if not isinstance(candidates, list) or not 1 <= len(candidates) <= 64:
            fail("candidates must be a list of 1 to 64 entries")
        actions = [_validate_engine_candidate(candidate) for candidate in candidates]
        if len(set(actions)) != len(actions):
            fail("candidates has duplicate action_index values")
    if "pv" in record:
        pv = record["pv"]
        if not isinstance(pv, list) or not 1 <= len(pv) <= 64:
            fail("pv must be a list of 1 to 64 action indices")
        for index in pv:
            _expect_action_index(index, "pv entry")
        if pv[0] != record["action_index"]:
            fail("pv[0] must equal action_index")


OPENING_PROBE_SCHEMA = "opening-probe.v1"
OPENING_PROBE_ROW_REQUIRED = {"schema", "contract_version", "case_id", "header", "records"}
OPENING_PROBE_ROW_FIELDS = OPENING_PROBE_ROW_REQUIRED | {"description", "file_length", "probe_cases"}
OPENING_PROBE_HEADER_REQUIRED = {
    "schema", "format_major", "key_format", "record_size", "entry_count", "ply_min",
    "ply_max", "per_ply", "source_book", "generator", "generator_version",
    "contract_version", "body_sha256",
}
OPENING_PROBE_HEADER_FIELDS = OPENING_PROBE_HEADER_REQUIRED | {"created_at", "coverage_complete"}
OPENING_PROBE_SOURCE_BOOK_FIELDS = {
    "book_id", "schema", "contract_version", "generator", "generator_version",
}
OPENING_PROBE_RECORD_FIELDS = {"key", "game_value", "status", "optimal_actions"}
OPENING_PROBE_STATUS_CODE = {"exact": 1, "bounded": 2}
OPENING_PROBE_RECORD_SIZE = 28
SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


class ProbeError(ValueError):
    """A probe failure named by the docs/opening-probe-v1.md section 5 taxonomy."""

    def __init__(self, kind: str, detail: str = "") -> None:
        super().__init__(f"{kind}{': ' + detail if detail else ''}")
        self.kind = kind


def _bitboard_from_qfen(qfen: str) -> list[int]:
    validate_qfen(qfen)
    board = [0] * 8
    for row, line in enumerate(qfen.split("/")):
        for col, ch in enumerate(line):
            if ch != ".":
                board[(0 if ch.isupper() else 4) + "abcd".index(ch.lower())] |= 1 << (row * 4 + col)
    return board


def _apply_transform(board: list[int], transform_index: int) -> list[int]:
    """Output slot k receives the D4-mapped plane that was shape perm[k] (symmetry doc)."""
    d4, perm_index = divmod(transform_index, 24)
    perm = SHAPE_PERM_ORDER[perm_index]
    out = [0] * 8
    for player in (0, 4):
        for slot in range(4):
            plane = board[player + perm[slot]]
            out[player + slot] = sum(
                1 << D4_POSITION_MAPS[d4][p] for p in range(16) if plane >> p & 1
            )
    return out


def _payload(board: list[int]) -> bytes:
    return b"".join(plane.to_bytes(2, "little") for plane in board)


def _canonical_transforms(board: list[int]) -> tuple[bytes, list[int]]:
    """Byte-wise least payload over the 192 transforms, and every minimiser (ascending)."""
    images = [_payload(_apply_transform(board, t)) for t in range(192)]
    least = min(images)
    return least, [t for t, image in enumerate(images) if image == least]


def _inverse_transform_index(transform_index: int) -> int:
    d4, perm_index = divmod(transform_index, 24)
    perm = SHAPE_PERM_ORDER[perm_index]
    d4_inv = next(
        e for e in range(8)
        if all(D4_POSITION_MAPS[e][D4_POSITION_MAPS[d4][p]] == p for p in range(16))
    )
    return d4_inv * 24 + SHAPE_PERM_ORDER.index(tuple(perm.index(i) for i in range(4)))


def _remap_action(action: int, transform_index: int) -> int:
    d4, perm_index = divmod(transform_index, 24)
    shape, position = divmod(action, 16)
    return SHAPE_PERM_ORDER[perm_index].index(shape) * 16 + D4_POSITION_MAPS[d4][position]


def _side_to_move(board: list[int]) -> int:
    return sum(bin(plane).count("1") for plane in board) % 2


def _has_completed_line(board: list[int]) -> bool:
    lines = [[r * 4 + c for c in range(4)] for r in range(4)]
    lines += [[r * 4 + c for r in range(4)] for c in range(4)]
    lines += [[(r0 + r) * 4 + c0 + c for r in range(2) for c in range(2)]
              for r0 in (0, 2) for c0 in (0, 2)]
    for line in lines:
        shapes = set()
        for p in line:
            for plane, bits in enumerate(board):
                if bits >> p & 1:
                    shapes.add(plane % 4)
        if len(shapes) == 4 and all(any(bits >> p & 1 for bits in board) for p in line):
            return True
    return False


def _legal_actions(board: list[int], player: int) -> set[int]:
    occupied = 0
    for plane in board:
        occupied |= plane
    actions = set()
    for shape in range(4):
        if bin(board[player * 4 + shape]).count("1") >= 2:
            continue
        opponent = board[(1 - player) * 4 + shape]
        for p in range(16):
            if occupied >> p & 1:
                continue
            row, col = divmod(p, 4)
            zone_row, zone_col = row // 2, col // 2  # the four 2x2 zones
            if any(
                opponent >> q & 1
                and (
                    row == q // 4
                    or col == q % 4
                    or (zone_row == q // 8 and zone_col == (q % 4) // 2)
                )
                for q in range(16)
            ):
                continue
            actions.add(shape * 16 + p)
    return actions


def _bitboard_from_key(key: bytes) -> list[int]:
    return [int.from_bytes(key[2 + 2 * i:4 + 2 * i], "little") for i in range(8)]


def _parse_probe_records(records: Any) -> list[tuple[bytes, int, str, int]]:
    """Corrupt-record checks; returns (key, game_value, status, action_mask) tuples."""
    if not isinstance(records, list):
        raise ProbeError("corrupt", "records must be a list")
    parsed = []
    for index, record in enumerate(records):
        where = f"record {index}"
        if not isinstance(record, dict) or set(record) != OPENING_PROBE_RECORD_FIELDS:
            raise ProbeError("corrupt", f"{where} must have exactly {sorted(OPENING_PROBE_RECORD_FIELDS)}")
        key_hex = record["key"]
        if not isinstance(key_hex, str) or not re.fullmatch(r"[0-9a-f]{36}", key_hex):
            raise ProbeError("corrupt", f"{where} key must be 36 lowercase hex characters")
        key = bytes.fromhex(key_hex)
        if key[0] != 1 or key[1] != 2:
            raise ProbeError("corrupt", f"{where} key must start with 0x01 0x02 (canonical_key.v1)")
        value, status, actions = record["game_value"], record["status"], record["optimal_actions"]
        if value not in (-1, 0, 1) or isinstance(value, bool) or not isinstance(value, int):
            raise ProbeError("corrupt", f"{where} game_value must be -1, 0 or 1")
        if status not in OPENING_PROBE_STATUS_CODE:
            raise ProbeError("corrupt", f"{where} status must be exact or bounded")
        if status == "exact" and value == 0:
            raise ProbeError("corrupt", f"{where} exact requires game_value -1 or 1")
        if (
            not isinstance(actions, list)
            or any(not isinstance(a, int) or isinstance(a, bool) or not 0 <= a <= 63 for a in actions)
            or actions != sorted(set(actions))
        ):
            raise ProbeError("corrupt", f"{where} optimal_actions must be sorted unique indices 0..63")
        board = _bitboard_from_key(key)
        if not actions and not (
            _has_completed_line(board) or not _legal_actions(board, _side_to_move(board))
        ):
            raise ProbeError("corrupt", f"{where} empty optimal_actions on a non-terminal position")
        parsed.append((key, value, status, sum(1 << a for a in actions)))
    return parsed


def _probe_record_bytes(parsed: list[tuple[bytes, int, str, int]]) -> bytes:
    return b"".join(
        key + value.to_bytes(1, "little", signed=True)
        + bytes([OPENING_PROBE_STATUS_CODE[status]]) + mask.to_bytes(8, "little")
        for key, value, status, mask in parsed
    )


def _open_probe(record: dict[str, Any]) -> tuple[dict[str, Any], list[tuple[bytes, int, str, int]]]:
    """Open-time checks in docs/opening-probe-v1.md section 5 (never partially read)."""
    header = record["header"]
    if not isinstance(header, dict):
        raise ProbeError("corrupt", "header must be an object")
    if (
        header.get("schema") != OPENING_PROBE_SCHEMA
        or header.get("format_major") != 1
        or header.get("key_format") != "canonical_key.v1"
    ):
        raise ProbeError("incompatible version", "schema, format_major and key_format must be opening-probe.v1, 1, canonical_key.v1")
    missing = OPENING_PROBE_HEADER_REQUIRED - set(header)
    if missing:
        raise ProbeError("corrupt", f"header missing mandatory keys {sorted(missing)}")
    unknown = set(header) - OPENING_PROBE_HEADER_FIELDS
    if unknown:
        raise ProbeError("corrupt", f"header has unknown keys {sorted(unknown)} (fixture headers are closed)")
    if header["record_size"] != OPENING_PROBE_RECORD_SIZE:
        raise ProbeError("corrupt", "record_size must be 28")
    source_book = header["source_book"]
    if (
        not isinstance(source_book, dict)
        or not isinstance(source_book.get("book_id"), str)
        or not source_book["book_id"]
        or set(source_book) - OPENING_PROBE_SOURCE_BOOK_FIELDS
    ):
        raise ProbeError("corrupt", "source_book must be an object with a non-empty book_id")
    for key in ("generator", "generator_version", "contract_version"):
        if not isinstance(header[key], str) or not header[key]:
            raise ProbeError("corrupt", f"header {key} must be a non-empty string")
    for key in ("entry_count", "ply_min", "ply_max"):
        if not isinstance(header[key], int) or isinstance(header[key], bool) or header[key] < 0:
            raise ProbeError("corrupt", f"header {key} must be a non-negative integer")
    if header["ply_min"] > header["ply_max"] or header["ply_max"] > 16:
        raise ProbeError("corrupt", "ply_min must be <= ply_max <= 16")
    per_ply = header["per_ply"]
    if not isinstance(per_ply, list) or any(
        not isinstance(row, dict) or set(row) != {"ply", "entries"}
        or any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in row.values())
        for row in per_ply
    ):
        raise ProbeError("corrupt", "per_ply must be a list of {ply, entries} non-negative integers")
    if sum(row["entries"] for row in per_ply) != header["entry_count"]:
        raise ProbeError("corrupt", "per_ply does not sum to entry_count")
    if not isinstance(header["body_sha256"], str) or not SHA256_HEX_RE.match(header["body_sha256"]):
        raise ProbeError("corrupt", "body_sha256 must be 64 lowercase hex characters")
    if "coverage_complete" in header and not isinstance(header["coverage_complete"], bool):
        raise ProbeError("corrupt", "coverage_complete must be a boolean")
    if "created_at" in header and not isinstance(header["created_at"], str):
        raise ProbeError("corrupt", "created_at must be a string")

    parsed = _parse_probe_records(record["records"])
    metadata_len = len(json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    body_start = -(-(12 + metadata_len) // 8) * 8
    expected_length = body_start + header["entry_count"] * OPENING_PROBE_RECORD_SIZE
    declared_length = record.get("file_length", expected_length)
    if len(parsed) != header["entry_count"] or declared_length != expected_length:
        raise ProbeError(
            "truncated",
            f"entry_count {header['entry_count']}, {len(parsed)} records, "
            f"file_length {declared_length}, layout needs {expected_length}",
        )
    if hashlib.sha256(_probe_record_bytes(parsed)).hexdigest() != header["body_sha256"]:
        raise ProbeError("checksum mismatch", "body_sha256 differs from the record region")
    keys = [entry[0] for entry in parsed]
    if any(a >= b for a, b in zip(keys, keys[1:])):
        raise ProbeError("unsorted or duplicate keys", "keys must be strictly ascending bytewise")
    counts: dict[int, int] = {}
    for key in keys:
        ply = sum(bin(plane).count("1") for plane in _bitboard_from_key(key))
        counts[ply] = counts.get(ply, 0) + 1
    if {row["ply"]: row["entries"] for row in per_ply} != counts or len(per_ply) != len(counts):
        raise ProbeError("corrupt", f"per_ply {per_ply} does not match the records' plies {counts}")
    if any(not header["ply_min"] <= ply <= header["ply_max"] for ply in counts):
        raise ProbeError("corrupt", "a record lies outside ply_min..ply_max")
    return header, parsed


def _probe_lookup(
    header: dict[str, Any],
    parsed: list[tuple[bytes, int, str, int]],
    case: dict[str, Any],
) -> dict[str, Any]:
    """Reference probe (docs/opening-probe-v1.md section 3.2)."""
    if "expected_book_id" in case and case["expected_book_id"] != header["source_book"]["book_id"]:
        raise ProbeError("stale", f"expected_book_id {case['expected_book_id']!r} != source_book.book_id")
    board = _bitboard_from_qfen(case["caller_qfen"])
    ply = sum(bin(plane).count("1") for plane in board)
    counts = [sum(bin(board[p * 4 + s]).count("1") for s in range(4)) for p in (0, 1)]
    if counts[0] - counts[1] not in (0, 1) or any(
        bin(board[p * 4 + s]).count("1") > 2 for p in (0, 1) for s in range(4)
    ):
        raise ProbeError("invalid caller position", case["caller_qfen"])
    if not header["ply_min"] <= ply <= header["ply_max"]:
        return {"outcome": "miss", "reason": "ply_outside_coverage"}
    least, minimisers = _canonical_transforms(board)
    key = bytes([1, 2]) + least
    found = next((entry for entry in parsed if entry[0] == key), None)
    if found is None:
        return {"outcome": "miss", "reason": "key_absent"}
    t_star = minimisers[0]
    _, value, status, mask = found
    back = _inverse_transform_index(t_star)
    actions = sorted(_remap_action(a, back) for a in range(64) if mask >> a & 1)
    legal = _legal_actions(board, _side_to_move(board))
    illegal = [a for a in actions if a not in legal]
    if illegal:
        raise ProbeError("illegal mapped-back action", f"{illegal} not legal in {case['caller_qfen']}")
    return {
        "outcome": "hit", "transform_index": t_star, "game_value": value,
        "status": status, "actions": actions,
        "_wrong_direction": sorted(_remap_action(a, t_star) for a in range(64) if mask >> a & 1),
        "_legal": legal, "_minimisers": minimisers,
    }


def _check_probe_case(header: dict[str, Any], parsed: list[Any], case: Any) -> None:
    if not isinstance(case, dict):
        fail("probe_cases entry must be an object")
    _expect_exact_keys(
        case, {"case_id", "caller_qfen", "expected"},
        {"case_id", "caller_qfen", "expected", "expected_book_id"},
    )
    expected = case["expected"]
    if not isinstance(expected, dict) or "outcome" not in expected:
        fail(f"probe case {case['case_id']}: expected must be an object with outcome")
    try:
        result = _probe_lookup(header, parsed, case)
    except ProbeError as exc:
        if expected["outcome"] == "error" and expected.get("error") == exc.kind:
            return
        raise
    extras = {}
    if result["outcome"] == "hit":
        extras = {
            "wrong_direction_actions": result["_wrong_direction"],
            "wrong_direction_legal": all(a in result["_legal"] for a in result["_wrong_direction"]),
            "minimiser_transform_indices": result["_minimisers"],
        }
    public = {k: v for k, v in result.items() if not k.startswith("_")}
    core = {k: v for k, v in expected.items() if k not in extras}
    if core != public:
        fail(f"probe case {case['case_id']}: expected {core}, reference probe returned {public}")
    for name in set(expected) & set(extras):
        if expected[name] != extras[name]:
            fail(f"probe case {case['case_id']}: {name} is {extras[name]}, fixture says {expected[name]}")


def validate_opening_probe_row(
    record: dict[str, Any], expected_contract_version: str | None
) -> None:
    """One opening-probe.v1 fixture row: a decoded probe file plus lookups against it.

    The header is checked against schemas/opening-probe-v1.json (stdlib mirror). The
    remaining checks are the fail-fast taxonomy of docs/opening-probe-v1.md section 5
    and a reference probe that maps every hit back with the inverse transform.
    """
    _expect_exact_keys(record, OPENING_PROBE_ROW_REQUIRED, OPENING_PROBE_ROW_FIELDS)
    if record["schema"] != OPENING_PROBE_SCHEMA:
        fail(f"schema must be {OPENING_PROBE_SCHEMA}")
    if expected_contract_version is not None and record["contract_version"] != expected_contract_version:
        fail(f"contract_version must be {expected_contract_version}")
    if not isinstance(record["case_id"], str) or not record["case_id"]:
        fail("case_id must be a non-empty string")
    header, parsed = _open_probe(record)
    for case in record.get("probe_cases", []):
        _check_probe_case(header, parsed, case)


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


def _validate_transform_index(value: Any, label: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 191:
        fail(f"{label} must be an integer in 0..191")


def _validate_shape_perm(value: Any, label: str) -> None:
    if not isinstance(value, list) or len(value) != 4:
        fail(f"{label} must be a 4-element list")
    if sorted(value) != [0, 1, 2, 3]:
        fail(f"{label} must be a permutation of [0, 1, 2, 3]")


def validate_symmetry_fixture(document: dict[str, Any], path: Path) -> None:
    board_cases = document.get("board_cases")
    if not isinstance(board_cases, list) or not board_cases:
        fail(f"{path}: board_cases must be a non-empty list")
    seen_board_ids: set[str] = set()
    for case in board_cases:
        if not isinstance(case, dict):
            fail(f"{path}: board_cases entries must be objects")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            fail(f"{path}: board_cases case_id must be a non-empty string")
        if case_id in seen_board_ids:
            fail(f"{path}: duplicate symmetry board case_id {case_id}")
        seen_board_ids.add(case_id)
        validate_qfen(case.get("qfen"))
        validate_qfen(case.get("canonical_qfen"))
        canonical_key = case.get("canonical_key")
        if not isinstance(canonical_key, str) or not re.match(r"^[0-9a-f]{36}$", canonical_key):
            fail(f"{path}: {case_id}.canonical_key must be 36 lowercase hex chars")
        orbit_size = case.get("orbit_size")
        if not isinstance(orbit_size, int) or isinstance(orbit_size, bool) or not 1 <= orbit_size <= 192:
            fail(f"{path}: {case_id}.orbit_size must be an integer in 1..192")
        transforms = case.get("transforms")
        if not isinstance(transforms, list) or not transforms:
            fail(f"{path}: {case_id}.transforms must be a non-empty list")
        seen_transform_indices: set[int] = set()
        for transform in transforms:
            if not isinstance(transform, dict):
                fail(f"{path}: {case_id} transform entries must be objects")
            t_index = transform.get("transform_index")
            _validate_transform_index(t_index, f"{case_id}.transforms[].transform_index")
            if t_index in seen_transform_indices:
                fail(f"{path}: {case_id} duplicate transform_index {t_index}")
            seen_transform_indices.add(t_index)
            d4_index = transform.get("d4_index")
            if not isinstance(d4_index, int) or isinstance(d4_index, bool) or not 0 <= d4_index <= 7:
                fail(f"{path}: {case_id}.transforms[].d4_index must be in 0..7")
            shape_perm = transform.get("shape_perm")
            _validate_shape_perm(shape_perm, f"{case_id}.transforms[].shape_perm")
            if t_index != d4_index * 24 + SHAPE_PERM_ORDER.index(tuple(shape_perm)):
                fail(
                    f"{path}: {case_id} transform_index {t_index} does not match "
                    f"d4_index {d4_index} and shape_perm {shape_perm}"
                )
            validate_qfen(transform.get("qfen"))

    action_cases = document.get("action_remap_cases")
    if not isinstance(action_cases, list) or not action_cases:
        fail(f"{path}: action_remap_cases must be a non-empty list")
    seen_action_ids: set[str] = set()
    for case in action_cases:
        if not isinstance(case, dict):
            fail(f"{path}: action_remap_cases entries must be objects")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            fail(f"{path}: action_remap_cases case_id must be a non-empty string")
        if case_id in seen_action_ids:
            fail(f"{path}: duplicate action_remap case_id {case_id}")
        seen_action_ids.add(case_id)
        action_index = case.get("action_index")
        if not isinstance(action_index, int) or isinstance(action_index, bool) or not 0 <= action_index <= 63:
            fail(f"{path}: {case_id}.action_index must be in 0..63")
        t_index = case.get("transform_index")
        _validate_transform_index(t_index, f"{case_id}.transform_index")
        expected = case.get("expected_action_index")
        if not isinstance(expected, int) or isinstance(expected, bool) or not 0 <= expected <= 63:
            fail(f"{path}: {case_id}.expected_action_index must be in 0..63")
        t_inv = case.get("inverse_transform_index")
        _validate_transform_index(t_inv, f"{case_id}.inverse_transform_index")

        # Reference re-derivation: recompute the remap independently from the
        # transform's own (d4_index, shape_perm) pair and require it to match
        # expected_action_index, so a hand-edited fixture can't silently drift.
        shape, position = divmod(action_index, 16)
        d4_index = case.get("d4_index")
        shape_perm = case.get("shape_perm")
        _validate_shape_perm(shape_perm, f"{case_id}.shape_perm")
        new_position = D4_POSITION_MAPS[d4_index][position]
        new_shape = shape_perm.index(shape)
        recomputed = new_shape * 16 + new_position
        if recomputed != expected:
            fail(
                f"{path}: {case_id} expected_action_index {expected} does not match "
                f"recomputed {recomputed} from d4_index/shape_perm"
            )


def validate_invalid_state_fixture(document: dict[str, Any], path: Path) -> None:
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        fail(f"{path}: cases must be a non-empty list")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            fail(f"{path}: invalid-state cases must be objects")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            fail(f"{path}: invalid-state case_id must be a non-empty string")
        if case_id in seen:
            fail(f"{path}: duplicate invalid-state case_id {case_id}")
        seen.add(case_id)
        if case.get("boundary") not in INVALID_STATE_BOUNDARIES:
            fail(f"{path}: {case_id}.boundary must be one of {INVALID_STATE_BOUNDARIES}")
        if case.get("expected_rejection") not in INVALID_STATE_REJECTIONS:
            fail(
                f"{path}: {case_id}.expected_rejection must be one of "
                f"{INVALID_STATE_REJECTIONS}"
            )
        has_qfen = "qfen" in case
        has_bitboards = "bitboards" in case
        if has_qfen == has_bitboards:
            fail(f"{path}: {case_id} must set exactly one of qfen or bitboards")
        if has_bitboards:
            bitboards = case["bitboards"]
            if not isinstance(bitboards, list) or len(bitboards) != 8:
                fail(f"{path}: {case_id}.bitboards must be a list of 8 integers")
            for plane in bitboards:
                if not isinstance(plane, int) or isinstance(plane, bool) or not 0 <= plane <= 0xFFFF:
                    fail(f"{path}: {case_id}.bitboards entries must be uint16")
        if not isinstance(case.get("note"), str) or not case.get("note"):
            fail(f"{path}: {case_id}.note must be a non-empty string")


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
    if isinstance(document, dict) and document.get("schema") == SYMMETRY_FIXTURE_SCHEMA:
        validate_symmetry_fixture(document, path)
    if isinstance(document, dict) and document.get("schema") == INVALID_STATE_FIXTURE_SCHEMA:
        validate_invalid_state_fixture(document, path)
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
                if row_schema in (ENGINE_REQUEST_SCHEMA, "quantik." + ENGINE_REQUEST_SCHEMA):
                    validate_engine_request_row(record)
                elif row_schema in (ENGINE_RESPONSE_SCHEMA, "quantik." + ENGINE_RESPONSE_SCHEMA):
                    validate_engine_response_row(record)
                elif row_schema in (
                    ENGINE_RESPONSE_V2_SCHEMA,
                    "quantik." + ENGINE_RESPONSE_V2_SCHEMA,
                ):
                    validate_engine_response_v2_row(record)
                elif row_schema == OPENING_PROBE_SCHEMA:
                    validate_opening_probe_row(record, expected_contract_version)
                elif row_schema == "search-summary.v1":
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
