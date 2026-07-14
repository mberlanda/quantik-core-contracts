# API Portability Testing

This document defines how Quantik implementations prove that their public APIs
honor the shared contracts across Python, Rust, and future language stacks.

The goal is not to force identical internal implementations. The goal is to
prove that externally visible behavior is identical for contracted state,
action, artifact, and release semantics.

## Scope

Portability tests should cover:

- supported contract release and wire contract IDs,
- QFEN parsing and emission,
- bitboard encoding and decoding,
- action-index encoding,
- side-to-move handling,
- legal move generation,
- move application,
- terminal-state detection,
- D4 symmetry transforms and canonical QFEN,
- self-play fixture parsing,
- opening-book summary generation,
- registered artifact readers and writers as they become implemented.

Out of scope:

- engine strength comparisons,
- exact search-node ordering,
- internal transposition-table layout,
- performance benchmarks except for basic smoke timeouts.

## Test Layers

### 1. Contract Repository Validation

The contracts repository validates its own manifest, schemas, and golden
fixtures. This proves that the shared inputs are internally coherent, not that
any implementation supports them.

Required gate:

```bash
python3 scripts/validate_contracts.py \
  --manifest contracts.json \
  --schema-glob 'schemas/**/*.json' \
  --fixture-glob 'fixtures/**/*.jsonl' \
  --expected-release "$(cat VERSION)"
```

### 2. Implementation Self-Test

Each implementation must run a local test suite against the same fixtures and
expected values. These tests live in the implementation repository because they
exercise implementation APIs.

Minimum expected assertions:

- exported contract release equals `contracts.json.release_version`,
- exported contract IDs match the manifest for the supported release,
- every QFEN fixture roundtrips through bitboards,
- every action fixture roundtrips through `(shape, position)`,
- legal action masks match generated legal moves,
- applying a fixture move produces the expected next state,
- canonical QFEN is stable across every D4 transform,
- `selfplay.v1` fixtures parse into implementation-native rows.

### 3. Cross-Stack Report Comparison

Each implementation should expose a small command that reads the same contract
fixtures and emits a normalized JSON report. The contracts repository can then
compare reports byte-for-byte or field-by-field.

Recommended command shape:

```bash
quantik-portability-report \
  --contracts-root /path/to/quantik-core-contracts \
  --output build/portability-report.json
```

Recommended report shape:

```json
{
  "schema": "api-portability-report.v1",
  "contracts_release": "1.1.0",
  "implementation": {
    "language": "python",
    "package": "quantik-core",
    "version": "1.1.0"
  },
  "contract_ids": {
    "qfen": "qfen.v1",
    "bitboard": "bitboard.v1",
    "action_index": "action-index.v1"
  },
  "cases": [
    {
      "case_id": "empty-board",
      "qfen": "..../..../..../....",
      "bitboards": [0, 0, 0, 0, 0, 0, 0, 0],
      "canonical_qfen": "..../..../..../....",
      "legal_action_mask": "0xffffffffffffffff",
      "legal_action_indices": [
        0, 1, 2, 3, 4, 5, 6, 7,
        8, 9, 10, 11, 12, 13, 14, 15,
        16, 17, 18, 19, 20, 21, 22, 23,
        24, 25, 26, 27, 28, 29, 30, 31,
        32, 33, 34, 35, 36, 37, 38, 39,
        40, 41, 42, 43, 44, 45, 46, 47,
        48, 49, 50, 51, 52, 53, 54, 55,
        56, 57, 58, 59, 60, 61, 62, 63
      ]
    }
  ]
}
```

The report schema is intentionally proposed here, not yet registered in
`contracts.json`.

### 4. Cross-Language Smoke

The first cross-language smoke should compare Python and Rust reports:

```text
Python report -> contracts comparator
Rust report   -> contracts comparator
```

The comparator should reject:

- mismatched contract release,
- missing contract IDs,
- different QFEN or bitboard outputs for the same case,
- different canonical QFEN for any D4 orbit fixture,
- different legal action masks or legal action index sets,
- different next-state QFEN after applying the same move,
- mismatched parser acceptance/rejection for invalid fixtures.

## Fixture Plan

Add fixtures in small, reviewable groups.

### Game-State Fixtures

Each case should include:

```text
case_id
qfen
side_to_move
bitboards[8]
occupied_mask
expected_legal_action_indices
expected_legal_action_mask
canonical_qfen
orbit_size
```

Recommended cases:

- empty board,
- single player-0 piece,
- single player-1 piece,
- asymmetric mixed position,
- horizontally symmetric position,
- diagonally symmetric position,
- near-terminal legal position,
- invalid overlapping bitboards,
- invalid QFEN width,
- invalid side-to-move parity.

### Move Fixtures

Each case should include:

```text
case_id
before_qfen
side_to_move
shape
position
action_index
after_qfen
is_legal
```

Recommended cases:

- one legal move per shape,
- occupied-square rejection,
- row/column/region shape-conflict rejection,
- inventory exhaustion rejection,
- terminal/no-legal-move case.

### Symmetry Fixtures

Each case should include the eight transformed QFEN strings and the expected
canonical QFEN. This removes ambiguity about transform order and lexicographic
comparison.

### Artifact Fixtures

Registered artifact contracts should gain tiny fixtures as implementations
stabilize:

- `observation.v1`,
- `game-result.v1`,
- `model-checkpoint.v1`,
- `opening-book-summary.v1`.

`search-summary.v1` fixtures should wait until that contract is registered.

## CI Design

Recommended gates:

1. Contracts repo validates fixtures and schemas on every PR.
2. Python repo validates contracts fixtures and emits a portability report.
3. Rust repo validates contracts fixtures and emits a portability report.
4. A scheduled or manual cross-stack workflow compares Python and Rust reports
   from the same contracts tag.
5. Release smoke checks install published Python/Rust packages and run the same
   report comparison against the latest contracts release.

## Ownership

- Contracts repo owns fixture content, report comparison rules, and release
  packaging.
- Python and Rust repos own implementation-specific test runners and report
  producers.
- Generated large artifacts stay outside the contracts repo. Only minimal
  golden fixtures and normalized reports should be committed or uploaded.

## Readiness Checklist

- The fixture names and expected values are stable.
- Python and Rust expose equivalent report commands.
- Reports include implementation versions and contract release.
- Invalid fixtures assert rejection behavior, not just successful paths.
- CI compares normalized reports from the same contracts tag.
- Release workflows archive the fixtures and comparator with the contracts
  release artifact.
