# quantik-core-contracts

Shared contracts for Quantik implementations across Python, Rust, and future
language bindings.

This repository is the compatibility boundary. Implementations can optimize
their internals, but persisted data, interchange formats, and ML training rows
must conform to the contracts documented here.

## Scope

- Game-state representation: board coordinates, QFEN, bitboards, players,
  shapes, moves, and action indices.
- Canonicalization: D4 symmetries, canonical representatives, orbits, and
  transposition keys.
- Storage decisions: JSONL, CBOR, protobuf, Arrow, Parquet, SQLite, and tensor
  materializations.
- Machine-readable schemas for externally exchanged data.
- GitHub Actions for local validation, release smoke checks, and
  cross-language producer/consumer checks.

## Contract Stability

This repository has one SemVer release in `VERSION` and
`contracts.json.release_version`. Individual wire formats use stable contract
IDs such as `selfplay.v1`. Additive fields are allowed only when existing
readers can ignore them safely. Breaking changes must introduce a new contract
ID such as `selfplay.v2`.

The current baseline is:

- contracts release `1.0.0`
- `qfen.v1`
- `bitboard.v1`
- `action-index.v1`
- `selfplay.v1`
- `tensor-board.v1`
- `opening-book.v1`
- `observation.v1`
- `game-result.v1`
- `model-checkpoint.v1`

See [docs/versioning.md](docs/versioning.md) for the full versioning model.

## Repository Layout

```text
docs/                    Human-readable decisions and compatibility rules
schemas/                 JSON Schemas and format metadata
fixtures/                Golden fixtures used by implementations and CI
scripts/                 Validation helpers with no third-party dependency
actions/                 Reusable composite GitHub Actions
.github/workflows/       CI and reusable workflows
contracts.json           Machine-readable contract/version manifest
VERSION                  SemVer release of this contract set
```

Start from [docs/README.md](docs/README.md) for a hypertext index of the
contracts, research notes, and machine-readable schemas.

## Using The Contracts From Another Repository

Validate committed fixtures:

```yaml
jobs:
  contracts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: mberlanda/quantik-core-contracts/actions/validate-contracts@v1.0.0
        with:
          fixture-glob: "tests/fixtures/**/*.jsonl"
          expected-release: "1.0.0"
```

Run an export/import smoke where one implementation produces a `selfplay.v1`
JSONL file and another consumes it:

```yaml
jobs:
  cross-language-smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: mberlanda/quantik-core-contracts/actions/cross-language-smoke@v1.0.0
        with:
          artifact-path: "build/selfplay-smoke.jsonl"
          producer-command: "cargo run --bin quantik-selfplay -- --rows 8 --output build/selfplay-smoke.jsonl"
          consumer-command: "python -m quantik_core.ml_data build/selfplay-smoke.jsonl"
          expected-release: "1.0.0"
```

The exact producer/consumer commands are intentionally supplied by the caller
repository. This contracts repo validates the artifact in the middle.

## Decision Summary

- JSONL remains the golden fixture format because it is readable, diffable, and
  easy to validate in CI.
- Parquet/Arrow are preferred for large analytical and ML pipelines.
- SQLite remains useful for graph-like opening books, indexes, and resumable
  local exploration, not for high-throughput tensor training.
- Protobuf and CBOR are acceptable for API or compact message exchange, but are
  not the primary bulk ML storage format.
- Dense tensor stores may be derived from Parquet/Arrow for training hot paths.

## Library Version Alignment

Python and Rust packages should expose both their own package/crate version and
the contracts release they support. The recommended exported contract release is
currently:

```text
1.0.0
```

The recommended supported contract IDs are listed in `contracts.json`.
