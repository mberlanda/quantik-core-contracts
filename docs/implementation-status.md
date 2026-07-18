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
| `model-checkpoint.v1` | Manifest loader/parser validates release `1.1.0`, fields, supported inputs, weights format, and fixture; `quantik-models-py` produces checkpoints (`weights.safetensors`, training report, manifest) via `quantik-models-train`, validated through the loader | Manifest parser validates release `1.1.0`, fields, supported inputs, weights format, and fixture | Rust/Python manifest parity is implemented, and the contract now has a produced surface: the model repo's trainer exports safetensors checkpoints whose manifests round-trip through the Python loader. |
| `search-summary.v1` | `search_summary.search_summary_row` produces the 33-field root-search diagnostic row for MCTS/beam/minimax; emits the draft label `search-summary.v1-draft` | Benchmark exporter produces the same 33-field row (`bench::contracts::search_summary_row`); emits the draft label `search-summary.v1-draft` | Registered in `contracts.json` with schema `schemas/search-summary-v1.json`. Both exporters emit field-for-field identical rows with normative event-counter semantics. Remaining: label-flip PRs (`-draft` → `search-summary.v1`) and `SUPPORTED_CONTRACTS` entries in each stack. |

## Cross-Stack Validation Workflows

| Workflow | Python | Rust | Current status |
| --- | --- | --- | --- |
| `api-portability-report.v1` | `quantik-api-portability-report` reads `fixtures/api-portability/game-state-v1.json` and emits normalized QFEN, bitboards, canonical QFEN/key, orbit size, legal actions, terminal/winner, and move projection rows | `quantik-portability-report` emits the same normalized report shape from the same contracts fixture | Implemented in both stacks as a cross-stack validation workflow, not a registered artifact contract. The contracts comparator checks exact release, contract IDs, case IDs, and per-case JSON equality. |
| Training dataset view | `quantik-core-py` exposes artifact readers and tensor helpers consumed by `quantik-models-py` | Rust produces `observation.v1`, `game-result.v1`, and `selfplay.v1` rows consumed by the model repo | Implemented as a `quantik-models-py` workflow over registered artifacts, not a new contract ID. See [Training Dataset View](training-dataset-view.md). |

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
- Searched books built by the Rust IDDFS builder (`bench_bfs`) are now
  readable through the benchmark opening-book API: `OpeningBookDatabase::open`
  upgrades their `positions` table in place by adding the benchmark-book
  columns with default values. Migrated searched rows keep `solved = 0`, so
  they are never served as solved references; position generation with
  `--book` reuses and writes back solved references against the same SQLite
  file. The `quantik-models-py` E2E workflow exercises this read-through path
  with `POSITIONS_USE_BOOK=1`.
- `search-summary.v1` is **registered** (schema `schemas/search-summary-v1.json`).
  Both Rust and Python implement the event-based telemetry surface (shared
  counter semantics across MCTS, beam, and minimax, `[-1, 1]` value scale with
  proven-exclusive `±1`, per-engine policy-mass kind, root-identity flag) and
  emit field-for-field identical 33-field rows under the draft label
  `search-summary.v1-draft`. Remaining gap: the label-flip follow-up PRs that
  switch producers to the stable `search-summary.v1` label and add it to each
  stack's `SUPPORTED_CONTRACTS`. See
  [Search Summary v1](search-summary-v1.md).
- `api-portability-report.v1` is implemented as a cross-stack validation
  workflow, not a registered artifact contract. Keep its fixture, report shape,
  comparator, and implementation CLI docs synchronized after every Python/Rust
  push that changes public API behavior.
- The training dataset view is implemented in `quantik-models-py` as a NumPy
  artifact generator over `observation.v1` and `selfplay.v1`. Cross-stack
  portability still depends on Rust/Python agreement for the underlying
  artifact contracts, plus future checked-in Parquet interchange fixtures.
