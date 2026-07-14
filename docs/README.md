# Quantik Contracts Documentation Index

This index is the hypertext entry point for the contracts repository. Use it to
resume work across sessions and to find the document that owns each decision.

## Current Release

`VERSION` and `contracts.json` currently define release `1.1.0` with status
`draft`.

Registered contracts:

- `qfen.v1`
- `bitboard.v1`
- `action-index.v1`
- `selfplay.v1`
- `tensor-board.v1`
- `arrow-parquet-selfplay.v1`
- `opening-book.v1`
- `opening-book-summary.v1`
- `observation.v1`
- `game-result.v1`
- `model-checkpoint.v1`

Some registered contracts are schema/metadata definitions whose producer or
fixture coverage is still landing in implementation repositories. See the
contract-specific docs and status note before treating a registered ID as fully
implemented end to end.

Known proposed contracts that are not registered yet:

- `search-summary.v1` for root-search diagnostics.
- `opening-annotation.v1` for named theory overlays.
- `opening-probe.v1` for compact runtime book/tablebase probes.

## Core Contracts

- [Versioning](versioning.md): contract IDs, SemVer release rules, and
  compatibility policy.
- [Game State Representation](game-state.md): QFEN, bitboards, move encoding,
  action indices, players, shapes, and side-to-move.
- [Self-Play v1](selfplay-v1.md): JSONL fixture contract and policy/value
  observation rows.
- [Opening Book v1](opening-book-v1.md): canonical opening knowledge graph,
  value/policy aggregates, and human theory overlays.
- [Opening Book Summary v1](opening-book-summary-v1.md): aggregate depth-book
  metrics used for Rust/Python consistency checks.
- [Observation v1](observation-v1.md): Parquet-oriented engine observation rows
  for MCTS, beam, minimax, and training pipelines.
- [Game Result v1](game-result-v1.md): completed H2H games for Elo proxy,
  engine comparison, and opening-line statistics.
- [Model Checkpoint v1](model-checkpoint-v1.md): metadata manifest for
  policy/value model artifacts and runtime compatibility checks.
- [Storage Representations](storage-representations.md): JSONL, CBOR,
  protobuf, Arrow, Parquet, SQLite, and tensor-store guidance.
- [Symmetry And Transposition](symmetry-transposition.md): canonicalization,
  D4 board symmetries, orbit size, and transposition keys.
- [Consistency Checks](consistency-checks.md): validation expectations for
  cross-language implementations.
- [Implementation Status](implementation-status.md): current Python/Rust
  producer and consumer coverage for each registered contract.
- [API Portability Testing](api-portability-testing.md): fixture/report/CI
  design for proving Python, Rust, and future stacks expose the same contracted
  behavior.

## Research Notes

- [Opening Book Scale, Storage, and Proficiency Tradeoffs](research/2026-07-13-opening-book-scale-and-storage.md):
  first scale estimate for opening-book storage, graph shape, and database
  tradeoffs.
- [Doing Better Than A Larger Opening Book](research/2026-07-13-doing-better-than-a-larger-opening-book.md):
  research-grade argument for graph search, compact knowledge, transfer
  learning, and human theory layers.
- [Sub-100MB Policy-Value Model Design](research/2026-07-13-sub-100mb-policy-value-model.md):
  neural network architecture for a small engine evaluator/recommender intended
  to outperform larger static-book-only approaches.
- [Opening Knowledge Data Preparation Next Steps](research/2026-07-13-opening-knowledge-data-preparation-next-steps.md):
  compacted implementation-status note for generated positions, observations,
  root-search summaries, probes, and models.
- [Opening Book Storage Follow-Up From Depth-7 Generation](research/2026-07-14-opening-book-storage-followup.md):
  concrete contract and implementation lessons from the Rust depth-7 SQLite
  book, including compact edges, action-preserving identity, resume semantics,
  and probe artifacts.

## Machine-Readable Contracts

- [`contracts.json`](../contracts.json): released contract manifest.
- [`schemas/qfen-v1.schema.json`](../schemas/qfen-v1.schema.json): QFEN JSON
  schema.
- [`schemas/bitboard-v1.schema.json`](../schemas/bitboard-v1.schema.json):
  bitboard JSON schema.
- [`schemas/selfplay-v1.schema.json`](../schemas/selfplay-v1.schema.json):
  self-play JSONL row schema.
- [`schemas/arrow-parquet-selfplay-v1.json`](../schemas/arrow-parquet-selfplay-v1.json):
  recommended Arrow/Parquet physical schema for self-play data.
- [`schemas/opening-book-v1.json`](../schemas/opening-book-v1.json):
  recommended SQLite source shape for opening-book graph artifacts.
- [`schemas/opening-book-summary-v1.json`](../schemas/opening-book-summary-v1.json):
  aggregate summary shape for cross-stack opening-book consistency checks.
- [`schemas/observation-v1.json`](../schemas/observation-v1.json):
  recommended Parquet physical schema for engine observations.
- [`schemas/game-result-v1.json`](../schemas/game-result-v1.json):
  recommended Parquet physical schema for completed H2H games.
- [`schemas/model-checkpoint-v1.json`](../schemas/model-checkpoint-v1.json):
  metadata manifest shape for model checkpoints.
- [`fixtures/parquet/arrow-parquet-selfplay-v1-metadata.json`](../fixtures/parquet/arrow-parquet-selfplay-v1-metadata.json):
  dependency-free metadata and column-order manifest for
  `arrow-parquet-selfplay.v1` Parquet writers/readers.

## Validators And Workflows

- [`scripts/validate_contracts.py`](../scripts/validate_contracts.py):
  dependency-light manifest, schema JSON, Parquet metadata manifest, and
  `selfplay.v1` fixture validator.
- [`scripts/validate_opening_book_summary.py`](../scripts/validate_opening_book_summary.py):
  `opening-book-summary.v1` artifact validator/comparator.
- [`scripts/validate_opening_book_artifact.py`](../scripts/validate_opening_book_artifact.py):
  SQLite opening-book artifact metrics check against
  `opening-book-summary.v1`.
- [`.github/workflows/validate-contracts.yml`](../.github/workflows/validate-contracts.yml):
  repository-level manifest/schema/fixture validation.
- [`.github/workflows/opening-book-release-consistency.yml`](../.github/workflows/opening-book-release-consistency.yml):
  cross-stack opening-book summary consistency check.
- [`.github/workflows/release-contracts.yml`](../.github/workflows/release-contracts.yml):
  tag-triggered release bundle packaging and GitHub Release asset upload.
