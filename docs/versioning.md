# Versioning Model

Quantik contracts use two related version systems.

## Repository Release Version

`VERSION` and `contracts.json.release_version` define the SemVer release of this
contracts repository.

Examples:

```text
0.1.0
1.0.0
1.1.0
2.0.0
```

This version changes when the contract set, schemas, fixtures, or reusable
actions change.

Rules:

- Patch: editorial fixes, validator bug fixes, non-semantic CI fixes.
- Minor: additive optional fields, new fixtures, new non-breaking checks, new
  storage guidance.
- Major: breaking wire-format changes, renamed required fields, changed action
  indexing, changed QFEN semantics, or incompatible tensor layout.

## Wire Contract IDs

Each externally exchanged format has a stable ID:

```text
qfen.v1
bitboard.v1
action-index.v1
selfplay.v1
tensor-board.v1
arrow-parquet-selfplay.v1
```

The suffix `v1` is the wire-format major version. It changes only when readers
must implement a different model.

The repository can move from `0.1.0` to `0.2.0` while still supporting
`selfplay.v1`. A future incompatible self-play row would become `selfplay.v2`
and require a major repository release.

## Machine-Readable Manifest

`contracts.json` is the source of truth for supported contract IDs, schemas,
docs, and implementation expectations.

Validators must check:

- `VERSION` equals `contracts.json.release_version`.
- Referenced schema and documentation files exist.
- Schema titles/metadata mention the corresponding contract ID.
- Fixtures use a supported row schema.
- Optional `contract_version` fields equal the repository release version.

## Library Alignment

Each implementation should expose both its own package/crate version and the
contract release it supports.

Recommended Python shape:

```python
SUPPORTED_CONTRACTS = {
    "contracts_release": "0.1.0",
    "qfen": "qfen.v1",
    "bitboard": "bitboard.v1",
    "action_index": "action-index.v1",
    "selfplay": "selfplay.v1",
    "tensor_board": "tensor-board.v1",
}
```

Recommended Rust shape:

```rust
pub const SUPPORTED_CONTRACTS_RELEASE: &str = "0.1.0";
pub const SUPPORTED_CONTRACTS: &[(&str, &str)] = &[
    ("qfen", "qfen.v1"),
    ("bitboard", "bitboard.v1"),
    ("action_index", "action-index.v1"),
    ("selfplay", "selfplay.v1"),
    ("tensor_board", "tensor-board.v1"),
];
```

The libraries do not need to share package SemVer. They do need to declare which
contracts release and wire contract IDs they support.

## Actions And Tests

Reusable Actions should pin a contracts repo ref:

```yaml
- uses: mberlanda/quantik-core-contracts/actions/validate-contracts@v0.1.0
```

During early development `@main` is acceptable, but release branches should pin
tags.

Test fixtures should include `schema`. They may include `contract_version` when
the fixture is intended to pin an exact repository release:

```json
{
  "schema": "selfplay.v1",
  "contract_version": "0.1.0"
}
```

When `contract_version` is present, validators must require it to match the
manifest release.

