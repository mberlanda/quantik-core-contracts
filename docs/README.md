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

Documentation maintenance rules:

- Keep implemented contract documentation under this `docs/` tree and link it
  from this index. Do not leave implemented contract docs only in research
  notes, PR descriptions, or implementation repositories.
- Update [Implementation Status](implementation-status.md) after every merged
  implementation PR that changes producer/consumer coverage.
- When Rust/Python enforcement changes a contract surface, update the relevant
  contract doc and any local workflow docs before or with the implementation
  push.

## Implementation PR Checklist

Use this flow when a contract or cross-stack validation surface changes:

1. Update the contracts repository first when the shared behavior changes:
   the relevant `docs/*.md` page, `docs/implementation-status.md`, schemas,
   fixtures, validators, and this index if a new page is added.
2. Keep implemented contract docs under `docs/`. Research notes may motivate a
   design, but implemented behavior must be documented in this folder.
3. Implement one contract or validation workflow at a time in Rust and Python,
   keeping report shapes, metadata checks, release handling, terminal/winner
   semantics, and fixture expectations aligned.
4. For each implementation PR, add a PR comment linking the relevant contract
   or workflow doc, then request Copilot review:

   ```bash
   gh pr edit <PR_NUMBER> --add-reviewer @copilot
   ```

5. Wait for Copilot feedback before merging. The operating cadence is roughly
   5 minutes, then 10 minutes, then 20 minutes when needed. Fetch current
   inline comments and address actionable feedback before merging.
6. Require green CI before merge. For API portability changes, regenerate both
   reports and compare them:

   ```bash
   quantik-api-portability-report \
     --contracts-root /path/to/quantik-core-contracts \
     --output build/python-api-portability-report.json

   cargo run -p quantik-core --bin quantik-portability-report -- \
     --contracts-root /path/to/quantik-core-contracts \
     --output build/rust-api-portability-report.json

   python3 /path/to/quantik-core-contracts/scripts/compare_api_portability_reports.py \
     build/python-api-portability-report.json \
     build/rust-api-portability-report.json
   ```

7. Squash merge implementation PRs after Copilot comments are addressed and CI
   is green. After merge, remove only the merged temporary worktrees and prune
   stale worktree metadata.
8. After the merge, update `docs/implementation-status.md` if the PR changed
   producer/consumer coverage or parity state. If the docs update was missed,
   make a follow-up docs PR before starting the next contract slice.

Known proposed contracts that are not registered yet:

- [`search-summary.v1`](search-summary-v1.md) for root-search diagnostics.
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
- [Search Summary v1](search-summary-v1.md): proposed root-search diagnostic
  row and the required Rust/Python telemetry gates before registration.
- [End-to-End Data Pipeline](end-to-end-pipeline.md): reproducible commands
  for generating positions, opening books, observations, H2H reports, contract
  rows, Parquet artifacts, and self-play training data.
- [Training Dataset View](training-dataset-view.md): NumPy-first materialized
  view owned by `quantik-models-py` over registered training artifacts.
- [50-100MB Policy/Value Model Project](policy-value-model-project.md): data,
  artifact, runtime, autoplay, and evaluation plan for the compact portable
  evaluator in `quantik-models-py`.
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
- [`fixtures/parquet/observation-v1-metadata.json`](../fixtures/parquet/observation-v1-metadata.json):
  dependency-free metadata and column-order manifest for `observation.v1`
  Parquet writers/readers.
- [`fixtures/parquet/game-result-v1-metadata.json`](../fixtures/parquet/game-result-v1-metadata.json):
  dependency-free metadata and column-order manifest for `game-result.v1`
  Parquet writers/readers.
- [`fixtures/selfplay/selfplay-v1-rust-smoke.jsonl`](../fixtures/selfplay/selfplay-v1-rust-smoke.jsonl):
  Rust-builder JSONL smoke rows for `selfplay.v1` consumers.
- [`fixtures/api-portability/game-state-v1.json`](../fixtures/api-portability/game-state-v1.json):
  shared game-state cases for local Python/Rust API portability reports.

## Validators And Workflows

- [`scripts/validate_contracts.py`](../scripts/validate_contracts.py):
  dependency-light manifest, schema JSON, Parquet metadata manifest, and
  `selfplay.v1` fixture validator.
- [`scripts/validate_opening_book_summary.py`](../scripts/validate_opening_book_summary.py):
  `opening-book-summary.v1` artifact validator/comparator.
- [`scripts/validate_opening_book_artifact.py`](../scripts/validate_opening_book_artifact.py):
  SQLite opening-book artifact metrics check against
  `opening-book-summary.v1`.
- [`scripts/compare_api_portability_reports.py`](../scripts/compare_api_portability_reports.py):
  dependency-light comparator for normalized local API portability reports.
- [`.github/workflows/validate-contracts.yml`](../.github/workflows/validate-contracts.yml):
  repository-level manifest/schema/fixture validation.
- [`.github/workflows/opening-book-release-consistency.yml`](../.github/workflows/opening-book-release-consistency.yml):
  cross-stack opening-book summary consistency check.
- [`.github/workflows/release-contracts.yml`](../.github/workflows/release-contracts.yml):
  tag-triggered release bundle packaging and GitHub Release asset upload.
