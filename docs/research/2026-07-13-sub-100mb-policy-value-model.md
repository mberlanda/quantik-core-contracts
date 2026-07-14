# Sub-100MB Policy-Value Model Design

Date: 2026-07-13

Status: research design for a future Quantik model contract

## Goal

Design a neural evaluator/recommender that stays below 100 MB on disk and is
expected to outperform static-book-only approaches of similar or larger size
when paired with Quantik search. The model should be useful for:

- Move recommendation.
- MCTS and beam-search priors.
- Minimax leaf evaluation.
- Puzzle candidate scoring.
- Opening and defense discovery.

The model is not intended to replace exact solved data. It compresses exact
data and search observations into a fast general evaluator.

## Design Thesis

Quantik is small enough for exact and near-exact data to be generated, but large
enough that explicit storage becomes wasteful beyond the early graph. A compact
policy/value model can generalize across unseen canonical states and improve
search everywhere. The recommended design is a sparse, NNUE-inspired evaluator
with policy and value heads:

```text
f_theta(s) -> (p_theta(a | s), v_theta(s), u_theta(s))
```

where:

- $p_\theta(a | s)$ is a 64-action policy distribution.
- $v_\theta(s) \in [-1, 1]$ is the value from the side-to-move perspective.
- $u_\theta(s) \in [0, 1]$ is an optional confidence/proof-likeness estimate.

This design is called `quantik-qnue.v0` in this note: Quantik Efficiently
Updatable Evaluator. The name is descriptive, not yet a contract ID.

## Inputs

The model input should be derivable from existing contracts:

- `bitboard.v1`: eight `uint16` bitboards, one per player/shape.
- `side_to_move`: `0|1`.
- `action-index.v1`: 64 shape-major action slots.
- Legal action mask from the rules engine.
- Optional derived features: ply, remaining inventory, terminal flag, and
  symmetry transform metadata.

The model should not require QFEN at runtime. QFEN is useful in fixtures and
debug data, but bitboards and side-to-move are the stable machine input.

## Sparse Feature Set

The feature transformer consumes active integer feature ids:

```text
A(s) = {i_1, i_2, ..., i_k}
```

Suggested feature families:

| Family | Purpose | Cardinality strategy |
| --- | --- | --- |
| Piece-square | Which owner/shape occupies which square. | Exact small table. |
| Side-relative piece-square | Same board from side-to-move perspective. | Exact small table. |
| Shape pressure | Shape conflicts by row, column, and 2x2 region. | Exact derived table. |
| Legal actions | Current legal shape/position placements. | Exact 64-bit mask features. |
| Piece-pair relations | Relative shape/square pairs that encode tactics. | Feature hashing. |
| Forcedness motifs | Only move, threat, refutation, terminal-near patterns. | Derived sparse features. |

Feature hashing keeps the model bounded. For example:

```text
feature_id = hash(feature_family, payload) mod F
```

Hash collisions are acceptable during training if $F$ is large enough and
feature families include a family id in the hash payload.

## Architecture

### Feature Transformer

The first layer is a sparse accumulator:

```text
h_0(s) = clip(b + \sum_{i in A(s)} E_i, 0, q)
```

where:

- $E \in Z^{F \times H}$ is the quantized feature embedding table.
- $F$ is the feature table size.
- $H$ is the accumulator width.
- $q$ is the clipped activation maximum.

This follows NNUE principles: sparse inputs, small board deltas between moves,
shallow integer-friendly inference, and accumulator reuse on the search stack.

### Dense Tower

Use a small dense tower after the accumulator:

```text
h_1 = crelu(W_1 h_0 + b_1)
h_2 = crelu(W_2 h_1 + b_2)
```

Recommended initial widths:

```text
H -> 256 -> 128
```

The dense tower should be quantization-aware from the start.

### Heads

The model has three heads:

```text
policy_logits = W_p h_2 + b_p        # 64 actions
value         = tanh(W_v h_2 + b_v)  # scalar in [-1, 1]
confidence    = sigmoid(W_u h_2 + b_u)
```

Illegal actions are masked before softmax:

```text
p(a | s) = softmax(logits_a + mask_a)
mask_a = 0 if legal else -infinity
```

## Size Budgets

The first layer dominates size. Dense heads are tiny by comparison.

| Variant | Feature table | Accumulator | First-layer storage | Expected total |
| --- | ---: | ---: | ---: | ---: |
| `qnue-small` | 32,768 | 384 | 25.2 MB at int16 | 30-35 MB |
| `qnue-main` | 65,536 | 512 | 67.1 MB at int16 | 72-82 MB |
| `qnue-int8` | 65,536 | 512 | 33.6 MB at int8 | 40-50 MB |
| `tiny-cnn-baseline` | dense 4x4 planes | 64 channels | under 2 MB | under 5 MB |

The first production target should be `qnue-small`, because it is small enough
to iterate quickly. The stretch target is `qnue-main` below 100 MB with better
capacity.

## Training Data

Training should combine exact labels, search labels, and game outcomes:

| Source | Storage | Use |
| --- | --- | --- |
| Solved graph slices | SQLite source, exported to Parquet | High-confidence value labels. |
| MCTS observations | Parquet | Policy targets and value estimates. |
| Beam/minimax observations | Parquet | Tactical labels and refutations. |
| H2H games | Parquet | Outcome labels and calibration. |
| Opening annotations | SQLite or JSON overlay | Evaluation subsets and named-line tests. |

Observation rows should store dense `policy_visits[64]` for training, plus a
legal mask. Sparse JSONL remains the fixture format; Parquet is the bulk
training format.

## Targets

Policy target:

```text
\pi(a | s) = \frac{N(s,a)^{1/\tau}}{\sum_b N(s,b)^{1/\tau}}
```

where $N(s,a)$ is a search visit count and $\tau$ is a temperature.

Value target priority:

1. Exact solved value.
2. Retrograde bounded value with confidence.
3. Strong search root value.
4. Game outcome from self-play.

Confidence target:

```text
w(s) = max(source_confidence, normalized_search_budget, engine_agreement)
```

This can start as a heuristic and later become a calibrated target.

## Loss

Use a weighted multi-task loss:

```text
L =
  \lambda_p CE(\pi, p_\theta)
  + \lambda_v w (z - v_\theta)^2
  + \lambda_u (w - u_\theta)^2
  + \lambda_r ||\theta||_2^2
```

For exact positions, set $w$ near 1. For shallow observations, reduce $w$ so
the model does not overfit noisy search.

## Training Schedule

1. Supervised bootstrap from exact and high-confidence graph labels.
2. Policy distillation from MCTS and beam observations.
3. Mixed training with balanced sampling by ply, source, and value.
4. Quantization-aware fine-tuning.
5. Engine-in-the-loop evaluation.
6. Active learning: generate more observations where the model disagrees with
   deeper search.

This schedule avoids pure self-play cold start. Quantik already has generated
knowledge; the model should use it.

## Evaluation Gates

The model should not be accepted because validation loss looks good. It should
pass engine-facing tests:

| Gate | Measurement | Initial target |
| --- | --- | --- |
| Policy top-1 | Agreement with stronger search on held-out positions. | Better than static book fallback outside stored depth. |
| Policy top-3 | Strong move appears in first three recommendations. | High enough for UI recommender use. |
| Value error | MSE against exact solved holdout. | Beats handcrafted heuristic. |
| H2H strength | Fixed-budget model+search vs baseline search. | Positive score with confidence interval. |
| Node efficiency | Same strength using fewer searched nodes. | Measurable reduction. |
| Size | Checkpoint plus manifest. | Under 100 MB. |

For Elo proxy, if model+search scores $S$ against baseline under fixed
conditions:

```text
\Delta Elo = 400 \log_{10} \frac{S}{1-S}
```

The first useful milestone is not a huge rating gain. A repeatable +35 to +75
Elo proxy at equal compute would justify the architecture. A +100 or better
proxy would justify making the evaluator a first-class engine dependency.

## Runtime Integration

Engines should query knowledge in this order:

1. Exact terminal or tablebase-like probe.
2. Opening-book policy/value if the node is covered and confidence is high.
3. QNUE policy/value model.
4. Search backup value.

MCTS uses the policy head as prior. Beam search uses it for candidate ordering.
Minimax uses the value head at leaves and the policy head for move ordering.

The legal mask must always be enforced outside the model. The model may learn
legality, but legality remains a rules-engine responsibility.

## Checkpoint Contract Sketch

A future model manifest should include:

```json
{
  "schema": "model-checkpoint.v1",
  "model_id": "quantik-qnue-small",
  "contract_version": "1.1.0",
  "input_contracts": ["bitboard.v1", "action-index.v1"],
  "output_contract": "policy-value.v1",
  "feature_hash": "sha256:...",
  "weights_hash": "sha256:...",
  "quantization": "int16-accumulator/int8-dense",
  "size_bytes": 33554432,
  "training_data_manifest": "sha256:...",
  "calibration_report": "sha256:..."
}
```

The contracts repository should define the manifest and I/O semantics before it
standardizes training code.

## Why This Can Outperform A Larger Static Book

A static book only helps where it has coverage. A compact evaluator helps every
search leaf. The equation is:

```text
strength ~= exact probes + search depth + move ordering + leaf quality
```

A larger book improves the first term. A model improves the last two terms
across the whole game. That is the main expertise-per-byte argument for the
sub-100MB target.

## Risks

- The model may learn illegal-action shortcuts if legal masks are missing from
  training.
- Search labels may be biased toward the engine that produced them.
- Feature hashing may hide important rare tactical features.
- A small network may overfit depth-6/depth-7 openings and fail later in games.
- Quantization can damage policy calibration if it is added only after training.

Mitigations:

- Always store legal masks.
- Mix MCTS, beam, minimax, exact, and H2H sources.
- Keep exact solved holdouts by depth.
- Evaluate against engines not used for training labels.
- Use quantization-aware training before shipping a runtime checkpoint.

## References

- Official Stockfish NNUE PyTorch documentation:
  https://github.com/official-stockfish/nnue-pytorch/blob/master/docs/nnue.md
- Dominik Klein, "Neural Networks for Chess", arXiv:2209.01506:
  https://arxiv.org/abs/2209.01506
- David Silver et al., "Mastering Chess and Shogi by Self-Play with a General
  Reinforcement Learning Algorithm", arXiv:1712.01815:
  https://arxiv.org/abs/1712.01815
- Leela Chess Zero technical explanation:
  https://lczero.org/dev/wiki/technical-explanation-of-leela-chess-zero/
- Companion strategy note:
  [Doing Better Than A Larger Opening Book](2026-07-13-doing-better-than-a-larger-opening-book.md)
