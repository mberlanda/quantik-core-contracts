# Implementation Status

This page records the current implementation state of each registered contract.
It is descriptive, not normative. Normative field rules live in the individual
contract documents and schemas.

Repository names and package names may differ. The Rust implementation lives in
the `quantik-core-rust` repository, while the published crate/package reference
is `quantik-core`.

Status terms:

- **Registered**: listed in `contracts.json`.
- **Produced**: at least one implementation emits the contract-shaped artifact.
- **Consumed**: at least one implementation validates and parses the artifact.
- **Parity**: Python and Rust both have the relevant producer or consumer
  surface for the current use case.

## Current Matrix

| Contract | Python | Rust | Current status |
| --- | --- | --- | --- |
| `qfen.v1` | Game-state parser/encoder support | Game-state parser/encoder support | Foundational game-state contract; no standalone artifact fixture validator beyond schema and implementation tests. |
| `bitboard.v1` | Core bitboard representation and validation support | Core bitboard representation and validation support | Foundational in-memory/wire representation; no standalone bulk artifact. |
| `action-index.v1` | Shared `shape * 16 + position` helpers and tests | Shared `shape * 16 + position` helpers and tests | Implemented as a convention used by self-play, observations, and games. |
| `selfplay.v1` | JSONL reader validates schema, optional release, QFEN, side-to-move, legal policy, duplicate actions, value, and the Rust-generated smoke fixture | Contract parser validates release, QFEN, side-to-move, legal policy, duplicate actions, and value; self-play builder emits release metadata and a checked-in JSONL smoke fixture | Logical JSONL fixture/debug parity is implemented across Python and Rust. Bulk training storage should use `arrow-parquet-selfplay.v1` physical columns. |
| `tensor-board.v1` | Tensor materialization from QFEN | Core game state can derive tensors through consumers | Storage guidance / derived representation; no standalone artifact validator. |
| `arrow-parquet-selfplay.v1` | Optional PyArrow reader/writer roundtrips real Parquet bytes, validates metadata, physical schema, bitboards, dense `policy_visits[64]`, integer value, and optional QFEN | Optional Arrow/Parquet feature reader/writer roundtrips real Parquet bytes, validates metadata, physical schema, bitboards, dense `policy_visits[64]`, integer value, and optional QFEN | Real Parquet I/O is implemented in both stacks. Metadata expectations are documented and covered by a dependency-free fixture; cross-stack file interchange fixtures are still pending. |
| `opening-book.v1` | SQLite/opening-book tooling and summary consumption path | SQLite opening-book producer/inspector | Implemented as a graph artifact path, with summary checks covering cross-stack drift and a stricter SQLite artifact validator for graph shape, key/reference integrity, depths, terminal flags, and action identity. |
| `opening-book-summary.v1` | Producer emits summary JSON with release `1.1.0` | Producer emits summary JSON with release `1.1.0` | Cross-stack summary artifact is implemented and validated by contracts scripts. |
| `observation.v1` | JSONL reader plus optional PyArrow Parquet reader/writer validate release `1.1.0`, metadata, physical schema, bitboards, legal mask, policy visits, and scalar fields | Benchmark exporter emits release `1.1.0`; consumer parser plus optional Arrow/Parquet reader/writer validate release, metadata, physical schema, bitboards, legal mask, policy visits, and scalar fields | Rust/Python Parquet parity is implemented for the current required physical column surface. |
| `game-result.v1` | JSONL reader plus optional PyArrow Parquet reader/writer validate release `1.1.0`, metadata, physical schema, winner, plies, move indices, and required engine fields | Benchmark exporter emits release `1.1.0`; consumer parser plus optional Arrow/Parquet reader/writer validate release, metadata, physical schema, winner, plies, move indices, and required engine fields | Rust/Python Parquet parity is implemented for the current required physical column surface. |
| `model-checkpoint.v1` | Manifest loader/parser validates release `1.1.0`, fields, supported inputs, weights format, and fixture | Manifest parser validates release `1.1.0`, fields, supported inputs, weights format, and fixture | Rust/Python manifest parity is implemented. |

## Known Gaps

- `arrow-parquet-selfplay.v1` has real Parquet reader/writer roundtrip tests in
  both stacks, including key/value metadata checks that the physical schema is
  `arrow-parquet-selfplay.v1`, row semantics are `selfplay.v1`, and the stored
  contract release matches `contracts.json.release_version`.
- `arrow-parquet-selfplay.v1` still needs checked-in cross-stack interchange
  evidence: a Rust-produced Parquet fixture loaded by Python and a
  Python-produced Parquet fixture loaded by Rust.
- `observation.v1` and `game-result.v1` still need checked-in cross-stack
  interchange evidence: Rust-produced Parquet fixtures loaded by Python and
  Python-produced Parquet fixtures loaded by Rust.
- `selfplay.v1` has checked-in JSONL fixture/debug evidence, including a
  Rust-builder smoke fixture that Python consumes. Bulk training-data parity
  should use `arrow-parquet-selfplay.v1`.
- `opening-book.v1` now has graph-level SQLite artifact validation beyond
  aggregate summary consistency. It remains structural: it checks keys,
  references, depths, terminal flags, and action identity without
  reimplementing Quantik legal-move generation.
- `search-summary.v1` is proposed but not registered.
