# Observation v1

`observation.v1` defines engine observation rows emitted while exploring
Quantik positions. The normative bulk storage format is Parquet using the
physical schema described in `schemas/observation-v1.json`.

JSONL may be used for tiny fixtures and debug samples. SQLite is not the
normative storage for observations.

## Scope

Observation rows capture what one engine saw at one root position under one
budget. They are training and analytics data, not opening-book graph truth.

Use observations for:

- MCTS root visit distributions,
- beam-search candidate summaries,
- minimax root scores,
- policy/value training rows,
- disagreement mining,
- active-learning queues.

Use `opening-book.v1` for aggregated graph knowledge.

## Required Fields

```text
schema: observation.v1
contract_version: 1.0.0
run_id: string
row_id: uint64
position_key: bytes or lowercase hex string
ply: uint16
side_to_move: uint8
bitboards: fixed_size_list<uint16, 8>
legal_action_mask: uint64
engine_kind: string
engine_version: string
elapsed_ms: uint32
policy_visits: fixed_size_list<uint32, 64>
value: float32
value_source: string
source_confidence: float32
```

Optional fields:

```text
qfen
engine_checkpoint
search_depth
rollouts
beam_width
node_budget
time_budget_ms
seed
policy_priors: fixed_size_list<float32, 64>
root_q_values: fixed_size_list<float32, 64>
principal_variation: list<uint8>
```

## Engine Kinds

Recommended values:

```text
mcts
beam
minimax
hybrid
random
human
```

Implementations may add engine kinds, but they must record `engine_version` and
the budget fields needed to reproduce the observation.

## Legal Action Mask

`legal_action_mask` is a 64-bit integer where bit `action_index` is set when
the action is legal.

```text
action_index = shape * 16 + position
```

Rows must not assign visits, priors, or q-values to illegal actions unless the
row is explicitly marked invalid by a debug-only extension.

## Policy Visits

`policy_visits` is dense and has exactly 64 slots. MCTS should store root visit
counts. Beam and minimax exporters may store synthetic counts where higher
counts correspond to stronger ranked candidates.

When creating a policy target:

```text
policy_target[a] = policy_visits[a] / sum(policy_visits)
```

At least one legal action must have a positive visit count for nonterminal
positions.

## Value

`value` is from the perspective of `side_to_move`.

Recommended `value_source` values:

```text
exact
bounded
minimax
rollout
backup
game
neural
heuristic
```

`source_confidence` must be in `0.0..1.0`.

## Parquet Partitioning

Recommended layout:

```text
data/observations/
  contract_version=1.0.0/
  engine_kind=mcts/
  engine_checkpoint=<checkpoint-or-none>/
  date=YYYY-MM-DD/
  part-00000.parquet
```

Partitioning by engine kind and checkpoint keeps model-training and comparison
queries simple.

## Compatibility Rules

Readers must reject:

- unknown required schema versions,
- invalid bitboard length,
- invalid `side_to_move`,
- invalid `legal_action_mask`,
- non-64-slot policy arrays,
- nonzero visits on illegal actions,
- missing engine kind or version,
- missing budget metadata for engines that require it,
- `source_confidence` outside `0.0..1.0`.

Readers may ignore:

- optional QFEN,
- optional priors,
- optional root q-values,
- optional principal variations.

