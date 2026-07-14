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
| `selfplay.v1` | JSONL reader validates schema, optional release, QFEN, side-to-move, legal policy, and value | Registered in supported input lists | Schema and Python consumer are implemented; Rust producer parity is not currently the active benchmark path. |
| `tensor-board.v1` | Tensor materialization from QFEN | Core game state can derive tensors through consumers | Storage guidance / derived representation; no standalone artifact validator. |
| `arrow-parquet-selfplay.v1` | Registered constant | Registered as supported model input | Physical schema guidance only; Parquet reader/writer parity is still missing. |
| `opening-book.v1` | SQLite/opening-book tooling and summary consumption path | SQLite opening-book producer/inspector | Implemented as a graph artifact path, with summary checks covering cross-stack drift; general graph validators are still lightweight. |
| `opening-book-summary.v1` | Producer emits summary JSON with release `1.1.0` | Producer emits summary JSON with release `1.1.0` | Cross-stack summary artifact is implemented and validated by contracts scripts. |
| `observation.v1` | JSONL reader validates release `1.1.0`, bitboards, legal mask, policy visits, and scalar fields | Benchmark exporter emits release `1.1.0`; consumer parser validates release, bitboards, legal mask, policy visits, and scalar fields | Rust/Python JSON consumer parity is implemented for debug/fixture rows; Parquet remains the normative large-storage target. |
| `game-result.v1` | JSONL reader validates release `1.1.0`, winner, plies, move indices, and required engine fields | Benchmark exporter emits release `1.1.0`; consumer parser validates release, winner, plies, move indices, and required engine fields | Rust/Python JSON consumer parity is implemented for debug/fixture rows; Parquet remains the normative large-storage target. |
| `model-checkpoint.v1` | Manifest loader/parser validates release `1.1.0`, fields, supported inputs, weights format, and fixture | Manifest parser validates release `1.1.0`, fields, supported inputs, weights format, and fixture | Rust/Python manifest parity is implemented. |

## Known Gaps

- `arrow-parquet-selfplay.v1` needs real Parquet roundtrip tests.
- `observation.v1` and `game-result.v1` need Parquet readers/writers once the
  large artifact path is active; current parity is JSON/JSONL parser coverage.
- `selfplay.v1` needs a current Rust producer smoke if it remains part of the
  active training-data path.
- `opening-book.v1` should eventually have stricter graph-level validators for
  full SQLite artifacts, beyond aggregate summary consistency.
- `search-summary.v1` is proposed but not registered.
