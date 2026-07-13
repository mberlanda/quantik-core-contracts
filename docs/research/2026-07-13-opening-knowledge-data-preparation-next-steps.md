# Opening Knowledge Data Preparation Next Steps

Date: 2026-07-13

Status: implementation preparation note

## Purpose

This note translates the research direction into concrete next steps for the
contracts repository and the Quantik generators. It focuses on artifact
boundaries: what should be SQLite, what should be Parquet, what should remain
JSONL, and what should later become a compact engine probe or model checkpoint.

The key decision is:

```text
SQLite stores graph truth.
Parquet stores observations and games.
Compact probe artifacts serve engines.
Model checkpoints compress expertise.
```

## Artifact Map

| Artifact | Contract candidate | Storage | Owner |
| --- | --- | --- | --- |
| Golden self-play fixture | `selfplay.v1` | JSONL | contracts |
| Bulk self-play rows | `arrow-parquet-selfplay.v1` | Parquet | generators/training |
| Opening graph | `opening-book.v1` | SQLite | Rust generator |
| Engine observations | `observation.v1` | Parquet | Rust generator |
| H2H games | `game-result.v1` | Parquet | Rust generator |
| Search trace summaries | `search-summary.v1` | Parquet | Rust generator |
| Named theory | `opening-annotation.v1` | SQLite or JSON | contracts/frontend |
| Engine probe | `opening-probe.v1` | compact binary or KV | Rust engine |
| Model checkpoint | `model-checkpoint.v1` | safetensors/ONNX plus manifest | training |

JSONL should stay small and fixture-oriented. It is not the right format for
millions of observations. SQLite should not become a dumping ground for every
search visit. Parquet should own the analytical record.

## Step 1: Add Contract Vocabulary

Add human-readable contract docs before schemas:

- `docs/opening-book-v1.md`
- `docs/observation-v1.md`
- `docs/model-checkpoint-v1.md`

The first pass can be normative prose plus examples. Machine-readable schemas
can follow once the Rust exporter has produced fixtures.

Required terms:

- `canonical_key`
- `node_id`
- `edge_id`
- `action_index`
- `legal_action_mask`
- `engine_id`
- `engine_checkpoint`
- `generation_budget`
- `search_budget`
- `source_confidence`
- `solved_status`
- `line_id`

## Step 2: Keep SQLite Focused On Opening Graph Truth

SQLite should contain stable, resumable graph state:

```text
positions(
  canonical_key,
  node_id,
  qfen_debug,
  bitboards,
  side_to_move,
  depth_ply,
  terminal_status,
  solved_status,
  game_value,
  value_confidence,
  symmetry_orbit_size,
  source
)

edges(
  parent_node_id,
  action_index,
  child_node_id,
  transform_id,
  edge_flags
)

book_policy(
  node_id,
  action_index,
  rank,
  prior,
  visits,
  q_value,
  source,
  source_confidence
)
```

The opening graph can aggregate observations, but it should not store every raw
observation event. This keeps the graph inspectable and avoids turning SQLite
into a training lake.

## Step 3: Store Observations As Parquet

Observation rows should be columnar because the common operations are scans,
filters, aggregations, and ML batch reads.

Recommended `observation.v1` columns:

```text
run_id: utf8
row_id: uint64
schema: utf8
contract_version: utf8
position_key: fixed_size_binary[16] or utf8
ply: uint16
side_to_move: uint8
bitboards: fixed_size_list<uint16, 8>
qfen: optional utf8
legal_action_mask: uint64
engine_kind: dictionary utf8  # mcts, beam, minimax, hybrid
engine_checkpoint: optional utf8
engine_version: utf8
search_depth: optional uint16
rollouts: optional uint32
beam_width: optional uint16
node_budget: optional uint64
time_budget_ms: optional uint32
elapsed_ms: uint32
seed: optional uint64
policy_visits: fixed_size_list<uint32, 64>
policy_priors: optional fixed_size_list<float32, 64>
root_q_values: optional fixed_size_list<float32, 64>
value: float32
value_source: dictionary utf8  # exact, rollout, minimax, backup, game
source_confidence: float32
principal_variation: optional list<uint8>
```

Partition layout:

```text
data/observations/
  contract_version=1.0.0/
  engine_kind=mcts/
  engine_checkpoint=<checkpoint>/
  date=YYYY-MM-DD/
  part-00000.parquet
```

The contracts repo should define the columns and invariants. The Rust repo
should own generation.

## Step 4: Store H2H Games As Parquet

Head-to-head games are not the same as search observations. They should be
separate rows:

```text
game_id: utf8
schema: utf8
contract_version: utf8
started_at: timestamp
p0_engine_kind: utf8
p0_engine_checkpoint: optional utf8
p1_engine_kind: utf8
p1_engine_checkpoint: optional utf8
opening_book_id: optional utf8
initial_position_key: fixed_size_binary[16] or utf8
winner: int8  # 0 or 1
plies: uint16
terminal_reason: utf8
seed: optional uint64
time_budget_ms_per_move: optional uint32
node_budget_per_move: optional uint64
move_action_indices: list<uint8>
position_keys: optional list<fixed_size_binary[16]>
```

This table feeds Elo estimation, opening-line win rates, and engine regression
tests. It should be queryable with DuckDB without loading the opening-book
SQLite file.

## Step 5: Store Search Trace Summaries Separately

Full traces can become enormous. The first contract should store root summaries
and optional principal variations, not every simulation edge.

Recommended `search-summary.v1` row:

```text
run_id
position_key
engine_kind
engine_checkpoint
budget
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

If later debugging needs full traces, put them under a separate experimental
contract and sample them aggressively.

## Step 6: Define The Training Dataset View

Training should read Parquet and produce model-ready batches:

```text
training_row = {
  bitboards,
  side_to_move,
  legal_action_mask,
  policy_target[64],
  value_target,
  sample_weight,
  source_tags
}
```

Policy target:

```text
policy_target[a] = visits[a] / sum_b visits[b]
```

Value target priority:

1. exact solved value,
2. bounded retrograde value,
3. strong search root value,
4. H2H game outcome.

The training view can be materialized as Parquet shards. It should not be a new
SQLite table.

## Step 7: Add Minimal Fixtures

For each new contract, add tiny fixtures:

- one valid opening-book SQLite or SQL fixture if binary SQLite is avoided in
  the contracts repo,
- one `observation.v1` JSONL equivalent fixture for validator smoke tests,
- one tiny Parquet schema metadata file,
- one H2H game fixture,
- one model manifest fixture without weights.

The actual large artifacts should stay out of git.

## Step 8: Validation Rules

Validators should reject:

- invalid QFEN when QFEN is present,
- bitboards with overlapping pieces,
- illegal `side_to_move`,
- policy visits on illegal actions,
- empty policy targets,
- terminal positions in initial-position datasets,
- missing engine kind or budget metadata for observations,
- contract-version mismatch,
- unknown required schema ids.

Validators should warn, not reject, when:

- optional QFEN is omitted from Parquet,
- policy priors are absent but visits are present,
- principal variation is absent,
- source confidence is low.

## Step 9: Generation Milestones

### Milestone A: Contract Shape

- Add prose docs for `opening-book.v1`, `observation.v1`, and
  `model-checkpoint.v1`.
- Add one tiny fixture per contract.
- Extend `contracts.json` only after validators exist.

### Milestone B: Rust Export Smoke

- Export 100 nonterminal valid initial positions.
- Export one MCTS observation shard to Parquet.
- Export one minimax observation shard to Parquet.
- Export one beam observation shard to Parquet.
- Export one H2H shard.

### Milestone C: Depth-6 Knowledge Baseline

- Generate complete canonical depth-6 graph.
- Aggregate observations into book-policy rows.
- Export Parquet training rows.
- Train `qnue-small`.

### Milestone D: Engine Integration

- Add book probe before search.
- Add model policy/value inference at leaves and roots.
- Run H2H tournaments against current engines.
- Record Elo proxy with reproducible configs.

### Milestone E: Naming And Puzzles

- Identify stable opening families.
- Create named line annotations.
- Generate forced-line puzzle candidates.
- Attach evidence to each name and puzzle.

## Review Checklist Before Implementation

- Observations are Parquet, not SQLite.
- SQLite stores graph truth and aggregates, not every search row.
- JSONL remains the small fixture format.
- QFEN is optional in bulk data and required only where the contract says so.
- Legal masks are present for training rows.
- Engine kind, checkpoint, budget, and seed are recorded for reproducibility.
- Model manifests include input/output contracts and hashes.
- Large generated artifacts stay out of the contracts repository.

## Immediate Next Commit After This Note

The next code-bearing contracts commit should add:

1. `docs/opening-book-v1.md`
2. `docs/observation-v1.md`
3. `docs/model-checkpoint-v1.md`
4. minimal JSON examples for each,
5. validator scaffolding for the examples,
6. a decision note that Parquet is the normative bulk observation format.

That sequence prepares the Rust generator work without prematurely freezing a
binary probe format or neural-network checkpoint format.

