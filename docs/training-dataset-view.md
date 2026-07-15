# Training Dataset View

The training dataset view is a derived workflow over registered Quantik
artifacts. It is not a new wire contract. Durable inputs remain
`observation.v1`, `selfplay.v1`, `arrow-parquet-selfplay.v1`,
`game-result.v1`, and `model-checkpoint.v1`.

The materializer lives in `quantik-models-py`, not in the core libraries. Core
libraries expose stable artifact and tensor APIs; the model repository owns
training views, model architecture, autoplay experiments, and checkpoint export.

## Repository Boundary

```text
quantik-core-contracts  -> contract IDs, schemas, docs, validators
quantik-core-rust       -> search/book/self-play/H2H data producers
quantik-core-py         -> artifact readers, tensor helpers, manifest validation
quantik-models-py       -> dataset materialization, training, evaluation, export
```

## Materialization Commands

Setup:

```bash
export CORE_PY=/Users/mauroberlanda/Code/quantik-ns/quantik/quantik-core-py
export MODELS=/Users/mauroberlanda/Code/quantik-ns/quantik-models-py
cd "$MODELS"
test -d .venv || python -m venv .venv
.venv/bin/python -m pip install -e "${CORE_PY}[arrow]"
.venv/bin/python -m pip install -e ".[dev,arrow]"
```

From observations:

```bash
quantik-models-materialize \
  --observations-jsonl /path/to/observations-v1.jsonl \
  --output-npz /path/to/training-view-observations.npz
```

From self-play:

```bash
quantik-models-materialize \
  --selfplay-jsonl /path/to/selfplay-v1.jsonl \
  --output-npz /path/to/training-view-selfplay.npz
```

Parquet inputs are supported when `quantik-core-py[arrow]` and
`quantik-models-py[arrow]` are installed:

```bash
quantik-models-materialize \
  --observations-parquet /path/to/observations-v1.parquet \
  --output-npz /path/to/training-view-observations.npz
```

## Arrays

The materialized `.npz` artifact contains:

| Field | Dtype | Shape | Meaning |
| --- | --- | --- | --- |
| `tensors` | `float32` | `(n, 9, 4, 4)` | 8 player-shape planes plus side-to-move plane. |
| `policy_target` | `float32` | `(n, 64)` | Normalized visit distribution over `action-index.v1`. |
| `value_target` | `float32` | `(n,)` | Value target in `[-1.0, 1.0]`, from side-to-move perspective. |
| `sample_weight` | `float32` | `(n,)` | Confidence-weighted source priority. |
| `legal_action_mask` | `uint64` | `(n,)` | Shared legal move mask. |
| `side_to_move` | `uint8` | `(n,)` | `0` or `1`. |
| `source_tags` | string | `(n,)` | Encoded provenance tags. |

## Tensor Structure

`tensor-board.v1` is represented as `(9, 4, 4)`:

- channels `0..7`: the 8 `bitboard.v1` player/shape occupancy planes,
- channel `8`: full-board side-to-move plane, `0.0` for player 0 and `1.0`
  for player 1.

Policy targets use `action-index.v1`:

```text
action_index = shape * 16 + position
```

Legal masking is always a runtime rule. The model may learn legality, but
engines must apply `legal_action_mask` outside the network.

## Label Strategy

Policy labels:

- `selfplay.v1`: normalize root MCTS visits.
- `observation.v1`: normalize dense `policy_visits[64]`.
- future `search-summary.v1`: only after the contract has real root visits and
  Q-values.

Value labels should be prioritized as:

1. exact/tablebase/opening-book,
2. bounded solver,
3. strong search,
4. generic MCTS/minimax/beam search,
5. self-play outcomes,
6. H2H calibration evidence,
7. heuristic/synthetic.

`game-result.v1` alone is not a supervised sample because it does not contain
per-ply board tensors. It is evaluation/calibration evidence unless joined with
position traces.

## Partitioning

Large training corpora should be partitioned before materialization:

```text
dataset_root/
  observations/engine_kind=mcts/run_id=.../*.parquet
  observations/engine_kind=minimax/run_id=.../*.parquet
  selfplay/generator=mcts-vs-mcts/run_id=.../*.parquet
  views/split=train/shard-0000.npz
  views/split=validation/shard-0000.npz
  views/split=test/shard-0000.npz
```

Keep Parquet shards large enough to avoid tiny-file churn. A practical target is
64-512 MB per Parquet shard before deriving `.npz` shards for training.
