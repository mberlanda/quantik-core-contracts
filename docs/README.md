# Quantik Contracts Documentation Index

This index is the hypertext entry point for the contracts repository. Use it to
resume work across sessions and to find the document that owns each decision.

## Core Contracts

- [Versioning](versioning.md): contract IDs, SemVer release rules, and
  compatibility policy.
- [Game State Representation](game-state.md): QFEN, bitboards, move encoding,
  action indices, players, shapes, and side-to-move.
- [Self-Play v1](selfplay-v1.md): JSONL fixture contract and policy/value
  observation rows.
- [Opening Book v1](opening-book-v1.md): canonical opening knowledge graph,
  value/policy aggregates, and human theory overlays.
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
  implementation sequence for turning generated positions, observations,
  search traces, and models into contracted artifacts.

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
- [`schemas/observation-v1.json`](../schemas/observation-v1.json):
  recommended Parquet physical schema for engine observations.
- [`schemas/game-result-v1.json`](../schemas/game-result-v1.json):
  recommended Parquet physical schema for completed H2H games.
- [`schemas/model-checkpoint-v1.json`](../schemas/model-checkpoint-v1.json):
  metadata manifest shape for model checkpoints.
