# Opening Knowledge Data Preparation Status

Date: 2026-07-13

Last refreshed: 2026-07-14

Status: compacted implementation-status note

## Purpose

This note records the artifact boundaries for opening knowledge and tracks what
has moved from plan into registered contracts. Older step-by-step planning has
been compacted so this file reflects the repository as implemented.

The durable decision remains:

```text
SQLite stores graph truth.
Parquet stores observations and games.
Compact probe artifacts serve engines.
Model checkpoints compress expertise.
```

JSONL remains fixture/debug oriented. Large generated observation and game data
belongs in Parquet. SQLite should not become a dumping ground for every search
visit.

## Artifact Status

| Artifact | Contract | Storage | Status | Owner |
| --- | --- | --- | --- | --- |
| Golden self-play fixture | `selfplay.v1` | JSONL | registered | contracts |
| Bulk self-play rows | `arrow-parquet-selfplay.v1` | Parquet | registered metadata | generators/training |
| Opening graph | `opening-book.v1` | SQLite | registered | Rust generator |
| Opening graph summary | `opening-book-summary.v1` | JSON | registered | Rust/Python consistency checks |
| Engine observations | `observation.v1` | Parquet | registered | Rust generator |
| H2H games | `game-result.v1` | Parquet | registered | Rust generator |
| Model checkpoint manifest | `model-checkpoint.v1` | JSON manifest plus weights artifact | registered metadata | training/runtime |
| Root search summary | `search-summary.v1` | Parquet or JSONL fixture | proposed | Rust generator |
| Named theory | `opening-annotation.v1` | SQLite or JSON | proposed | contracts/frontend |
| Engine probe | `opening-probe.v1` | compact binary or KV | proposed | Rust engine |

## Implemented Contract Docs

The following docs and schema metadata are now the source of truth:

- `docs/opening-book-v1.md`
- `schemas/opening-book-v1.json`
- `docs/opening-book-summary-v1.md`
- `schemas/opening-book-summary-v1.json`
- `docs/observation-v1.md`
- `schemas/observation-v1.json`
- `docs/game-result-v1.md`
- `schemas/game-result-v1.json`
- `docs/model-checkpoint-v1.md`
- `schemas/model-checkpoint-v1.json`

`contracts.json` registers these contracts in release `1.1.0`.

## Storage Boundaries

### Opening Graph

`opening-book.v1` owns stable, resumable graph truth:

- canonical positions,
- legal action-preserving edges,
- aggregated value/policy knowledge,
- solved or bounded status,
- generation provenance,
- optional annotation hooks.

The SQLite source shape is defined in `docs/opening-book-v1.md` and
`schemas/opening-book-v1.json`.

### Opening Summary

`opening-book-summary.v1` is a small consistency artifact for CI and release
checks. It is not the graph and does not replace the SQLite book. It records
depth, total positions, terminals, total edges, and per-depth aggregates.

### Observations

`observation.v1` owns per-root training and analytics rows:

- bitboards,
- side to move,
- legal action mask,
- engine identity and budget,
- elapsed time,
- dense `policy_visits[64]`,
- optional `root_q_values[64]`,
- optional `principal_variation`,
- value and source confidence.

This is the right contract for model training rows and engine disagreement
mining. It is not opening-book graph truth.

### H2H Games

`game-result.v1` owns completed head-to-head games and tournament evidence:

- engine identities,
- initial position,
- winner,
- terminal reason,
- action-index move list,
- optional position trace and budget metadata.

This feeds Elo proxy estimation, opening-line outcome statistics, and engine
regression checks.

### Model Checkpoints

`model-checkpoint.v1` owns small manifests for neural or statistical model
artifacts. Weights remain outside the contracts repository. The manifest records
input/output contracts, format, hashes, size, training-data provenance, and
calibration references.

## Proposed Remaining Contract: `search-summary.v1`

Current status: still proposed and not registered. The living readiness note is
[Search Summary v1](../search-summary-v1.md). Rust/Python audits confirmed that
root values, PVs, and some engine-specific counts exist, but portable
`expanded_nodes`, `transposition_hits`, `terminal_hits`, `tablebase_hits`,
`policy_visits[64]`, and `root_q_values[64]` semantics are not yet implemented
across MCTS, beam, and minimax.

Full search traces can become enormous, so do not standardize full per-edge or
per-simulation traces in v1. The proposed first artifact should be one
root-search diagnostic row per completed search.

Recommended row shape:

```text
schema
contract_version
run_id
row_id
position_key
ply
side_to_move
bitboards
qfen
legal_action_mask
engine_kind
engine_version
engine_checkpoint
config_label
search_depth
rollouts
beam_width
node_budget
time_budget_ms
seed
root_value
policy_visits[64]
root_q_values[64]
principal_variation
expanded_nodes
transposition_hits
terminal_hits
tablebase_hits
elapsed_ms
```

Boundary with `observation.v1`:

- Keep `observation.v1` as the training/analytics corpus contract.
- Use `search-summary.v1` only for reproducibility and diagnostic counters.
- Duplicating `policy_visits`, `root_q_values`, and principal variation is
  acceptable only so a diagnostic row can stand alone.
- Counter semantics must be defined before registration. If an engine has no
  tablebase or compact probe shortcut, `tablebase_hits` must be `0`.

## Validators

Implemented validators currently cover:

- manifest references and release consistency,
- JSON schema/metadata parseability,
- `selfplay.v1` JSONL fixtures,
- `opening-book-summary.v1` artifacts,
- SQLite opening-book metrics compared with an opening summary.

Remaining validator work:

- `observation.v1` fixture validation,
- `game-result.v1` fixture validation,
- `model-checkpoint.v1` fixture validation,
- future `search-summary.v1` fixture validation after the contract is
  registered.

## Remaining Milestones

1. Generate and retain real Rust smoke artifacts for `observation.v1`,
   `game-result.v1`, and `opening-book-summary.v1`.
2. Add small checked-in fixtures for registered analytical contracts when the
   generated shape is stable enough.
3. Define and register `search-summary.v1` only after Rust exposes consistent
   `expanded_nodes`, `transposition_hits`, `terminal_hits`, and
   `tablebase_hits` semantics.
4. Define compact runtime probe artifacts separately from the SQLite source of
   truth.
5. Add named opening/theory annotations after the graph identity and evidence
   model stabilize.

## Review Checklist

- Observations and games are Parquet-oriented analytical data, not SQLite graph
  tables.
- SQLite stores graph truth and aggregates, not every search row.
- JSONL remains the small fixture/debug format.
- QFEN is optional in bulk data unless a specific contract requires it.
- Legal masks are present for training-oriented rows.
- Engine kind, checkpoint, budget, and seed are recorded where reproducibility
  depends on them.
- Model manifests include input/output contracts and hashes.
- Large generated artifacts stay out of the contracts repository.
